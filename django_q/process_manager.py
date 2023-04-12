from abc import ABC
from django_q.conf import Conf, logger
from django_q.humanhash import humanize
import uuid
from django_q.conf import Conf
import enum
from django import db
from typing import Callable
from django.utils.translation import gettext_lazy as _
import multiprocessing
from multiprocessing import Process, Value

class ProcessManager(ABC):
    class Status(enum.IntEnum):
        IDLE = 1
        BUSY = 2
        DONE = 3
        RECYCLE = 4

    target = None

    def get_target(self) -> Callable:
        if self.target is None:
            raise ValueError("Process must have target specified")
        return self.target

    def __init__(self):
        self.status = Value("i", self.Status.IDLE.value)
        self.process = self.spawn_process()
        self.name = humanize(uuid.uuid4().hex)

    def spawn_process(self) -> Process:
        self.manager_pipe, process_pipe = multiprocessing.Pipe(duplex=True)
        p = Process(target=self.get_target(), args=(self.status, process_pipe))
        p.start()
        return p

    def reincarnate_process(self):
        # kill connections before killing the process
        logger.critical(_("reincarnated worker %(name)s after death") % {"name": self.process.name})
        if not Conf.SYNC:
            db.connections.close_all()
        self.process.kill()
        self.process = self.spawn_process()
        self.mark_idle()

    @property
    def has_results(self):
        # poll puller pipe for new tasks
        return self.manager_pipe.poll()

    def get_result(self):
        # get the puller pipe task object back from the worker
        return self.manager_pipe.recv()

    @property
    def is_alive(self):
        # get the puller status
        return self.process.is_alive()

    @property
    def is_done(self):
        return self.status.value == self.Status.DONE.value

    @property
    def is_idle(self):
        return self.status.value == self.Status.IDLE.value

    @property
    def is_recycle(self):
        # worker needs to be recycled/reincarnated
        return self.status.value == self.Status.RECYCLE.value

    def mark_idle(self):
        self.status.value = self.Status.IDLE.value
