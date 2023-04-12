from copy import Error
from django_q.worker import WorkerProcess
from django_q.monitor import Monitor
from django_q.models import Task
from typing import Optional, Sequence, Tuple
from django_q.conf import logger
from django_q.queue_task import QueueTask
from django_q.puller import Puller
from django_q.scheduler import Scheduler


def run_scheduler_once(broker=None) -> None:
    Scheduler.schedule_tasks(broker)

def get_scheduled_tasks(broker=None) -> Sequence[QueueTask]:
    try:
        return Puller.get_tasks_from_broker(broker=broker)
    except ValueError:
        logger.exception("Couldn't get items from broker")
        return []

def run_task(task=None) -> QueueTask:
    if task is None:

        scheduled_tasks = get_scheduled_tasks()
        if not len(scheduled_tasks):
            raise ValueError("No tasks scheduled and no task given to run for worker")
        task = scheduled_tasks[0]

    return WorkerProcess.run_task(task)

def save_task(task, broker=None) -> Tuple[QueueTask, Optional[Task]]:
    return Monitor.save_task(task, broker)

def run_cluster_once(workers, tasks=[], broker=None) -> None:
    if not len(tasks):
        run_scheduler_once(broker=broker)
        tasks = get_scheduled_tasks(broker=broker)

    for idx, worker in enumerate(range(workers)):
        if len(tasks) >= idx + 1:
            task = run_task(tasks[idx])
            save_task(task, broker=broker)
