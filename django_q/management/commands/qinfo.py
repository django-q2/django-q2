from datetime import timedelta
from django_q.brokers import get_broker
from django_q.models import Failure, Schedule, Success
from django_q.status import Stat
from django.db.models import F, Sum
from django.db import connection
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django.utils import timezone

from django_q import VERSION
from django_q.conf import Conf


class Command(BaseCommand):
    # Translators: help text for qinfo management command
    help = _("General information over all clusters.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--config",
            action="store_true",
            dest="config",
            default=False,
            help="Print current configuration.",
        )
        parser.add_argument(
            "--ids",
            action="store_true",
            dest="ids",
            default=False,
            help="Print cluster task ID(s) (PIDs).",
        )

    def handle(self, *args, **options):
        if options.get("ids", True):
            stat = Stat.get_all()
            if not stat:
                print(_("No clusters appear to be running."))

            for s in stat:
                print(s.cluster_id)

        elif options.get("config", False):
            hide = [
                "conf",
                "IDLE",
                "STOPPING",
                "STARTING",
                "WORKING",
                "SIGNAL_NAMES",
                "STOPPED",
                "SECRET_KEY",
            ]
            settings = [
                a for a in dir(Conf) if not a.startswith("__") and a not in hide
            ]
            self.stdout.write(f"VERSION: {'.'.join(str(v) for v in VERSION)}")
            for setting in settings:
                value = getattr(Conf, setting)
                if value is not None:
                    self.stdout.write(f"{setting}: {value}")
        else:
            broker = get_broker()

            broker.ping()

            stats = Stat.get_all(broker=broker)
            clusters = len(stats)
            workers = 0
            reincarnations = 0
            for cluster in stats:
                workers += len(cluster.workers)
                reincarnations += cluster.reincarnations

            # calculate tasks pm and avg exec time
            tasks_per = 0
            per = _("day")
            exec_time = 0
            last_tasks = Success.objects.filter(
                stopped__gte=timezone.now() - timedelta(hours=24)
            )
            tasks_per_day = last_tasks.count()
            if tasks_per_day > 0:
                # average execution time over the last 24 hours
                if connection.vendor != "sqlite":
                    exec_time = last_tasks.aggregate(
                        time_taken=Sum(F("stopped") - F("started"))
                    )
                    exec_time = exec_time["time_taken"].total_seconds() / tasks_per_day
                else:
                    # can't sum timedeltas on sqlite
                    for t in last_tasks:
                        exec_time += t.time_taken()
                    exec_time = exec_time / tasks_per_day
                # tasks per second/minute/hour/day in the last 24 hours
                if tasks_per_day > 24 * 60 * 60:
                    tasks_per = tasks_per_day / (24 * 60 * 60)
                    per = _("second")
                elif tasks_per_day > 24 * 60:
                    tasks_per = tasks_per_day / (24 * 60)
                    per = _("minute")
                elif tasks_per_day > 24:
                    tasks_per = tasks_per_day / 24
                    per = _("hour")
                else:
                    tasks_per = tasks_per_day

            print(
                _("-- %(prefix)s %(version)s on %(info)s --")
                % {
                    "prefix": Conf.PREFIX.capitalize(),
                    "version": ".".join(str(v) for v in VERSION),
                    "info": broker.info(),
                }
            )
            print(_("Clusters: %(clusters)s") % {"clusters": clusters})
            print(_("Workers: %(workers)s") % {"workers": workers})
            print(_("Restarts: %(restarts)s") % {"restarts": reincarnations})

            print("")
            print(_("Queued: %(queue_size)s") % {"queue_size": str(broker.queue_size())})
            print(_("Successes: %(success_count)s") % {"success_count": str(Success.objects.count())})
            print(_("Failures: %(failure_count)s") % {"failure_count": str(Failure.objects.count())})

            print("")
            print(_("Schedules: %(schedules_count)s") % {"schedules_count": str(Schedule.objects.count())})
            print(_("Tasks/%(per)s: %(amount)s") % {"per": per, "amount": f"{tasks_per:.2f}"})
            print(_("Avg time: %(time)s") % {"time": f"{exec_time:.4f}"})
