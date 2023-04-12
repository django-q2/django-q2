from django_q.worker import WorkerProcess
from django_q.queue_task import QueueTask
from django_q.models import Task
from queue import Queue
from queue import Empty
from typing import Optional, Tuple
from django_q.brokers import get_broker
from django_q.process_manager import ProcessManager
from django_q.signals import post_execute
from django_q.conf import logger
from django.utils.translation import gettext_lazy as _
from multiprocessing import current_process

try:
    import setproctitle
except ModuleNotFoundError:
    setproctitle = None


class Monitor(ProcessManager):
    def __init__(self):
        super().__init__()
        self.task_queue = Queue()

    @staticmethod
    def save_task(task, broker=None) -> Tuple[QueueTask, Optional[Task]]:
        task_db_obj = None
        if broker is None:
            broker = get_broker()
        if task.cached:
            task.save_cached(broker)
        else:
            print("SAVE TO DB")
            task_db_obj = task.save_to_db(broker)
        # acknowledge result
        if task.ack_id and (task.has_succeeded or not task.ack_failure):
            broker.acknowledge(task.ack_id)
        # signal execution done
        post_execute.send(sender="django_q", task=task)
        return task, task_db_obj


    @property
    def is_done(self):
        return self.status.value == self.Status.IDLE.value and self.task_queue.empty()

    def get_target(self):
        return self.run_monitor

    def run_item(self):
        if self.is_idle:
            try:
                task = self.task_queue.get_nowait()
            except Empty:
                # if the queue is empty, then just stop
                return
            try:
                self.manager_pipe.send(task)
            except BrokenPipeError:
                # recycle process if pipe is broken
                self.status.value = ProcessManager.Status.RECYCLE.value

    def add_task(self, task):
        self.task_queue.put(task)

    def run_monitor(self, status, pipe) -> None:
        broker = get_broker()
        proc_name = current_process().name
        if setproctitle:
            setproctitle.setproctitle(f"qcluster {proc_name} monitor")
        logger.info(
                _("%(name)s monitoring at %(id)s") % {"name": proc_name, "id": current_process().pid}
                )
        status.value = self.Status.IDLE.value

        while True:
            task = pipe.recv()
            if task == "STOP":
                logger.info(f"Monitor {proc_name} shut down")
                break
            status.value = self.Status.BUSY.value
            # save the result
            task, __ = Monitor.save_task(task, broker=broker)
            # log the result
            if task.has_succeeded:
                # log success
                logger.info(
                        _("Processed '%(info_name)s' (%(task_name)s)")
                        % {"info_name": task.func_name, "task_name": task.name}
                        )
            else:
                # log failure
                logger.error(
                        _("Failed '%(info_name)s' (%(task_name)s) - %(task_result)s")
                        % {
                            "info_name": task.func_name,
                            "task_name": task.name,
                            "task_result": task.result,
                            }
                        )
            status.value = self.Status.IDLE.value
        logger.info(_("%(name)s stopped monitoring results") % {"name": proc_name})
