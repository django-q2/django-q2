from django_q.utils import localtime
import uuid
from django_q.models import Schedule
from django_q import tasks
import ast
from django_q.humanhash import humanize
from django import db
from time import sleep
from django_q.brokers import get_broker
from django.utils import timezone

from multiprocessing import Value, current_process
from django_q.utils import close_old_django_connections
from django.utils.translation import gettext_lazy as _
from django_q.conf import Conf, logger
from django_q.process_manager import ProcessManager



class Scheduler(ProcessManager):
    """The Scheduler is responsible for scheduling new tasks"""

    @staticmethod
    def schedule_tasks(broker=None):
        logger.debug("Start sheduling")
        if broker is None:
            broker = get_broker()
        q_default = db.models.Q(cluster__isnull=True) if Conf.CLUSTER_NAME == Conf.PREFIX else db.models.Q(pk__in=[])
        with db.transaction.atomic(using=db.router.db_for_write(Schedule)):
            for s in (
                Schedule.objects.select_for_update()
                .exclude(repeats=0)
                .filter(db.models.Q(next_run__lt=timezone.now()), q_default | db.models.Q(cluster=Conf.CLUSTER_NAME))
            ):
                args = s.parse_args()
                kwargs = s.parse_kwargs()
                q_options = kwargs.get("q_options", {})
                if s.intended_date_kwarg:
                    kwargs[s.intended_date_kwarg] = s.next_run.isoformat()
                if s.hook:
                    q_options["hook"] = s.hook
                # set up the next run time
                if s.schedule_type != s.ONCE:
                    next_run = s.calculate_next_run(s.next_run)
                    if not Conf.CATCH_UP:
                        while next_run <= localtime():
                            next_run = s.calculate_next_run(next_run)

                    s.next_run = next_run
                    s.repeats += -1
                # send it to the cluster; any cluster name is allowed in multi-queue scenarios
                # because `broker_name` is confusing, using `cluster` name is recommended and take
                q_options["cluster"] = s.cluster or q_options.get("cluster", q_options.pop("broker_name", None))
                if q_options['cluster'] is None or q_options['cluster'] == Conf.CLUSTER_NAME:
                    q_options["broker"] = broker

                q_options["group"] = q_options.get("group", s.name or s.id)
                kwargs["q_options"] = q_options

                s.task = tasks.async_task(s.func, *args, **kwargs)
                # log it
                if not s.task:
                    logger.error(
                        _(
                            "%(process_name)s failed to create a task from schedule "
                            "[%(schedule)s]"
                        )
                        % {
                            "process_name": current_process().name,
                            "schedule": s.name or s.id,
                        }
                    )
                else:
                    logger.info(
                        _(
                            "%(process_name)s created task %(task_name)s from schedule "
                            "[%(schedule)s]"
                        )
                        % {
                            "process_name": current_process().name,
                            "task_name": humanize(s.task),
                            "schedule": s.name or s.id,
                        }
                    )
                # default behavior is to delete a ONCE schedule
                if s.schedule_type == s.ONCE:
                    if s.repeats < 0:
                        s.delete()
                        continue
                    # but not if it has a positive repeats
                    s.repeats = 0
                # save the schedule
                s.save()

    def get_target(self):
        return self.run_scheduler

    def stop_scheduler(self) -> None:
        # send stop signal to worker
        try:
            self.manager_pipe.send("STOP")
        except BrokenPipeError:
            # recycle process if pipe is broken
            self.status.value = ProcessManager.Status.DONE.value

    def run_scheduler(self, status, pipe) -> None:
        self.process_name = current_process().name
        self.process_id = current_process().pid
        status.value = self.Status.BUSY.value
        logger.info(
            _("%(proc_name)s scheduling at %(id)s")
            % {"proc_name": self.process_name, "id": self.process_id}
        )
        while True:
            if pipe.poll() and pipe.recv() == "STOP":
                status.value = self.Status.DONE.value
                break
            broker = get_broker()
            close_old_django_connections()
            try:
                Scheduler.schedule_tasks(broker=broker)
            except Exception:
                logger.exception("Could not create task from schedule")
            # sleep 60 seconds for next schedule
            sleep(60)
