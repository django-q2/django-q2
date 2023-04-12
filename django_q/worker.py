import multiprocessing
from queue import Queue
from queue import Empty
from typing import Optional, Tuple, Union
from django_q.queue_task import QueueTask
from django.utils import timezone
import traceback

from multiprocessing import Process, Value, current_process
from django_q.utils import close_old_django_connections
from django.utils.translation import gettext_lazy as _
from django_q.conf import Conf, logger, setproctitle, error_reporter, resource, psutil
from django_q.signals import pre_execute
from django_q.exceptions import TimeoutException, TimeoutHandler
from django_q.process_manager import ProcessManager



class Worker(ProcessManager):

    def spawn_process(self) -> Process:
        """
        :type target: function or class
        """
        self.status = Value("i", Worker.Status.IDLE.value)
        self.manager_pipe, worker_process_pipe = multiprocessing.Pipe(duplex=True)
        p = WorkerProcess(args=(self.status, worker_process_pipe))
        p.daemon = Conf.DAEMONIZE_WORKERS
        p.start()
        return p

    def start_task(self, task) -> None:
        # send task to worker
        try:
            self.manager_pipe.send(task)
        except BrokenPipeError:
            # recycle process if pipe is broken
            self.status.value = ProcessManager.Status.RECYCLE.value


class Pool:
    """This will manager the individual workers"""
    def __init__(self, workers=Conf.WORKERS):
        self.amount_workers = workers
        self.workers = []
        self.task_queue = Queue()
        self.start_workers()

    def start_workers(self):
        for __ in range(self.amount_workers):
            self.workers.append(Worker())

    def get_worker(self, id) -> Optional[Worker]:
        worker = next((worker for worker in self.workers if worker.id == id), None)
        if worker is None:
            logger.error("Couldn't find worker")
            return
        return worker

    @property
    def is_healthy(self):
        """Checks if all workers are still operating"""
        return all(worker.is_alive for worker in self.workers)

    @property
    def is_idle(self):
        """Checks if all workers are idle"""
        return all(worker.is_idle for worker in self.workers)

    @property
    def is_done(self):
        """Checks if all workers are idle and task queue is empty"""
        return self.is_idle and self.task_queue.empty()

    def reincarnate_stopped_workers(self):
        """Reincarnates workers that are not alive anymore"""
        stopped_workers = [worker for worker in self.workers if not worker.is_alive]
        for worker in stopped_workers:
            worker.reincarnate_process()

    def add_task(self, task):
        self.task_queue.put(task)

    def get_done_workers(self):
        """Worker tasks that have been completed, but need to be saved to cache/db - to be processed by monitor worker"""
        return [worker for worker in self.workers if worker.is_done]

    def mark_workers_idle(self, worker_ids):
        """Mark workers idle when they are ready to be used again"""
        for worker_id in worker_ids:
            # We are going to process the result, mark them idle, so they can be used for a different task
            worker = self.get_worker(id=worker_id)
            if worker is not None:
                worker.mark_idle()

    def delegate_tasks(self):
        available_workers = [worker for worker in self.workers if worker.is_idle]
        for worker in available_workers:
            try:
                task = self.task_queue.get_nowait()
            except Empty:
                # if the queue is empty, then just stop
                break
            worker.start_task(task)


class WorkerProcess(Process):

    @staticmethod
    def run_task(task) -> Tuple[QueueTask, bool]:
        # signal execution
        pre_execute.send(sender="django_q", func=task.func, task=task)
        task.started_at = timezone.now()
        try:
            with TimeoutHandler(timeout=task.timeout):
                func = task.callable_func()
                res = func(*task.args, **task.kwargs)
                result = res
        except (TimeoutException, Exception) as e:
            if isinstance(e, TimeoutException):
                task.status = QueueTask.Status.TIMEOUT
            else:
                task.status = QueueTask.Status.FAILED
            result = f"{e} : {traceback.format_exc()}"

            if error_reporter:
                error_reporter.report()
            if task.sync:
                raise
            return task
        else:
            # succeeded
            task.status = QueueTask.Status.SUCCESS
        finally:
            task.result = result
            task.finished_at = timezone.now()
        return task

    def __init__(self, group=None, name=None, args=(), kwargs={}, daemon=None):
        target = self.processing_tasks
        super().__init__(group=group, target=target, name=name, args=args, kwargs=kwargs, daemon=daemon)

    def mark_ready(self):
        self.process_name = current_process().name
        self.process_id = current_process().pid
        self.task_count = 0
        logger.info(
            _("%(proc_name)s ready for work at %(id)s")
            % {"proc_name": self.process_name, "id": self.process_id}
        )


    def mark_start_task(self, task):
        # Log task creation and set process name
        task_desc = (
            _("%(proc_name)s processing %(task_name)s '%(func_name)s'")
            % {
                "proc_name": self.process_name,
                "func_name": task.func_name,
                "task_name": task.name,
            }
        )
        if task.group is not None:
            task_desc += f" [{task.group}]"
        logger.info(task_desc)

        if setproctitle:
            proc_title = f"qcluster {self.process_name} processing {task.name} '{task.func_name}'"
            if task.group is not None:
                proc_title += f" [{task.group}]"
            setproctitle.setproctitle(proc_title)

    def processing_tasks(self, status: Value, pipe):
        self.mark_ready()
        while True:
            task = pipe.recv()
            if task == "STOP":
                logger.info(f"Worker {self.process_name} stopped processing")
                break
            # got a new task, let's mark it starting
            self.mark_start_task(task)

            # make sure the function actually exists, before we try to run it
            try:
                if not task.is_callable:
                    raise ValueError(f"Function {task.func_name} is not defined")
            except Exception as e:
                result = (f"{e} : {traceback.format_exc()}", False)
                if error_reporter:
                    error_reporter.report()
                if task.sync:
                    raise
                # stop here, move on to the next one
                continue

            close_old_django_connections()

            status.value = ProcessManager.Status.BUSY.value
            task = WorkerProcess.run_task(task)
            # Add task towards total
            self.task_count += 1

            # Set to DONE so main process can pick it up
            status.value = ProcessManager.Status.DONE.value
            if setproctitle:
                setproctitle.setproctitle(f"qcluster {self.process_name} completed with task")

            # Recreate a new process if this task has had the max amount of runs or exceeded resources
            if self.task_count == Conf.RECYCLE or self.rss_check():
                status.value = ProcessManager.Status.RECYCLE
                break

            pipe.send(task)

    def rss_check(self):
        if Conf.MAX_RSS:
            if resource:
                return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss >= Conf.MAX_RSS
            elif psutil:
                return psutil.Process().memory_info().rss >= Conf.MAX_RSS * 1024
        return False
