from __future__ import annotations
from datetime import datetime
from django_q.brokers import Broker
from django.utils import timezone
from django_q.signing import SignedPackage
from django_q.models import Success, Task
from django_q.utils import close_old_django_connections
import enum
from django_q import tasks
import inspect
import pydoc
from django import db

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union

from django_q.conf import Conf, logger


@dataclass
class QueueTask:
    class Status(enum.IntEnum):
        QUEUED = 0
        SUCCESS = 1
        FAILED = 2
        TIMEOUT = 3

    func: Union[Callable, str]
    name: str
    group: Optional[str] = None
    cluster: str = Conf.CLUSTER_NAME
    queued_at: Optional[datetime] = timezone.now()
    finished_at: Optional[datetime] = None
    ack_id: Optional[str] = None
    started_at: Optional[datetime] = None
    id: str = "-1"
    timeout: Optional[int] = Conf.TIMEOUT
    status: Optional[Status] = None
    result: Any = None
    save: bool = Conf.SAVE_LIMIT >= 0
    chain: Union[str, QueueTask] = ""
    cached: bool = Conf.CACHED
    sync: bool = Conf.SYNC
    hook: Optional[str] = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    ack_failure: bool = Conf.ACK_FAILURES
    iter_count: Optional[int] = None
    iter_cached: Optional[int] = None

    def callable_func(self):
        func = self.func
        if not callable(func):
            func = pydoc.locate(func)
        return func

    @property
    def has_succeeded(self):
        return self.status == self.Status.SUCCESS

    @property
    def has_timed_out(self):
        return self.status == self.Status.TIMEOUT

    @property
    def is_callable(self):
        return self.callable_func is not None

    @property
    def func_name(self):
        if inspect.isfunction(self.func):
            return f"{self.func.__module__}.{self.func.__name__}"
        elif inspect.ismethod(self.func) and hasattr(self.func.__self__, "__name__"):
            return (
                f"{self.func.__self__.__module__}." f"{self.func.__self__.__name__}.{self.func.__name__}"
            )
        else:
            return str(self.func)

    def save_to_db(self, broker: Broker):
        """
        Saves the task package to Django or the cache
        :param task: the task package
        :type broker: brokers.Broker
        """
        # SAVE LIMIT < 0 : Don't save success
        if not self.save and self.has_succeeded:
            return
        # enqueues next in a chain
        if self.chain:
            tasks.async_chain(
                self.chain,
                group=self.group,
                cached=self.cached,
                sync=self.sync,
                broker=broker,
            )
        close_old_django_connections()

        logger.debug(self.func_name)
        try:
            filters = {}
            if (
                Conf.SAVE_LIMIT_PER
                and Conf.SAVE_LIMIT_PER in {"group", "name", "func"}
                and Conf.SAVE_LIMIT_PER in self
            ):
                value = getattr(self, Conf.SAVE_LIMIT_PER)
                if Conf.SAVE_LIMIT_PER == "func":
                    value = self.func_name
                filters[Conf.SAVE_LIMIT_PER] = value

            with db.transaction.atomic(using=db.router.db_for_write(Success)):
                last = Success.objects.filter(**filters).select_for_update().last()
                if (
                    self.has_succeeded
                    and 0 < Conf.SAVE_LIMIT <= Success.objects.filter(**filters).count()
                ):
                    # delete the last entry if we are hitting the limit
                    last.delete()

            # check if this task has previous results
            existing_task, created = Task.objects.get_or_create(
                id=self.id,
                name=self.name,
                defaults={
                    'func': self.func_name,
                    'stopped': self.finished_at,
                    'hook': self.hook,
                    'args': self.args,
                    'kwargs': self.kwargs,
                    'cluster': self.cluster,
                    'started': self.started_at,
                    'result': self.result,
                    'group': self.group,
                    'success': self.has_succeeded,
                    'attempt_count': 1
                }
            )

            # only update the result if it hasn't succeeded yet
            if not created and not existing_task.success:
                existing_task.stopped = self.finished_at
                existing_task.result = self.result
                existing_task.success = self.has_succeeded
                existing_task.attempt_count += 1
                existing_task.save()

            if (
                Conf.MAX_ATTEMPTS > 0
                and existing_task.attempt_count >= Conf.MAX_ATTEMPTS
            ):
                broker.acknowledge(self.ack_id)

            return existing_task

        except Exception:
            logger.exception("Could not save task result")


    def save_cached(self, broker: Broker):
        task_key = f'{broker.list_key}:{self.id}'
        timeout = self.cached
        if timeout is True:
            timeout = None
        try:
            group = self.group
            iter_count = self.iter_count
            # if it's a group append to the group list
            if group:
                group_key = f"{broker.list_key}:{group}:keys"
                group_list = broker.cache.get(group_key) or []
                # if it's an iter group, check if we are ready
                if iter_count and len(group_list) == iter_count - 1:
                    group_args = f"{broker.list_key}:{group}:args"
                    # collate the results into a Task result
                    results = [
                        SignedPackage.loads(broker.cache.get(k)).result
                        for k in group_list
                    ]
                    results.append(self.result)
                    self.result = results
                    self.id = group
                    self.args = SignedPackage.loads(broker.cache.get(group_args))
                    self.iter_count = None
                    self.group = None
                    if self.iter_cached:
                        self.cached = self.iter_cached
                        self.save_cached(broker=broker)
                    else:
                        self.save_to_db(broker)
                    broker.cache.delete_many(group_list)
                    broker.cache.delete_many([group_key, group_args])
                    return
                # save the group list
                group_list.append(task_key)
                broker.cache.set(group_key, group_list, timeout)
                # async_task next in a chain
                if self.chain:
                    tasks.async_chain(
                        self.chain,
                        group=group,
                        cached=self.cached,
                        sync=self.sync,
                        broker=broker,
                    )
            # save the task
            broker.cache.set(task_key, SignedPackage.dumps(self), timeout)
        except Exception:
            logger.exception("Could not save task result")

