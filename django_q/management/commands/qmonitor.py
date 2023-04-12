import curses
from django_q.brokers import get_broker
from django_q.models import Failure, Success
from django_q.conf import Conf
from django_q.status import Stat
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django.utils import timezone
import time

import signal


class Command(BaseCommand):
    # Translators: help text for qmonitor management command
    help = _("Monitors Q Cluster activity")

    def add_arguments(self, parser):
        parser.add_argument(
            "--run-once",
            action="store_true",
            dest="run_once",
            default=False,
            help="Run once and then stop.",
        )

    def handle(self, *args, **options):
        memory_stats = MonitorTerminalStats(
            run_once=options.get("run_once", False),
        )
        curses.wrapper(memory_stats.start)


class MonitorTerminalStats:
    stop_writing = False
    table_cell_size = 20

    def __init__(self, run_once=False):
        self.run_once = run_once

    def start(self, stdscr):
        self.show_stats()

    def on_exit(self, signum, frame):
        # exit clean
        self.stop_writing = True

    def get_table_cell(self, data):
        spaces = self.table_cell_size - len(str(data))
        return data + " " * spaces + "//  "

    def show_stats(self):
        signal.signal(signal.SIGTERM, self.on_exit)
        signal.signal(signal.SIGINT, self.on_exit)
        scr = curses.initscr()

        broker = get_broker()

        broker.ping()

        stats = Stat.get_all(broker=broker)

        if not stats:
            scr.addstr(1, 0, "Cluster is not running")
            scr.refresh()

        while not self.stop_writing:
            data = []
            table_headers = [
                _("Host"),
                _("Id"),
                _("State"),
                _("Pool"),
                _("TQ"),
                _("RQ"),
                _("RC"),
                _("Up"),
            ]

            data.append("".join([self.get_table_cell(header) for header in table_headers]))

            for stat in stats:
                tasks = str(stat.task_q_size)

                if stat.task_q_size > 0:
                    tasks = str(stat.task_q_size)
                    if Conf.QUEUE_LIMIT and stat.task_q_size == Conf.QUEUE_LIMIT:
                        tasks += " (at maximum size)"
                results = stat.done_q_size
                if results > 0:
                    results = str(results)
                # color workers
                workers = len(stat.workers)
                # format uptime
                uptime = (timezone.now() - stat.tob).total_seconds()
                hours, remainder = divmod(uptime, 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime = "%d:%02d:%02d" % (hours, minutes, seconds)
                # print to the terminal
                stat_values = [
                    str(stat.host),
                    str(stat.cluster_id)[-8:],
                    str(stat.status),
                    str(workers),
                    str(tasks),
                    str(results),
                    str(stat.reincarnations),
                    str(uptime),
                ]

                data.append("".join([self.get_table_cell(val) for val in stat_values]))

            data.append("")
            queue_size = broker.queue_size()
            lock_size = broker.lock_size()
            if lock_size:
                queue_size = f"{queue_size}({lock_size})"


            data.append("")
            data.append(_("info: %(broker_info)s") % {"broker_info": broker.info()})
            data.append("")
            data.append(_("Queued: %(queue_size)s") % {"queue_size": str(broker.queue_size())})
            data.append(_("Successes: %(success_count)s") % {"success_count": str(Success.objects.count())})
            data.append(_("Failures: %(failure_count)s") % {"failure_count": str(Failure.objects.count())})

            for idx, item in enumerate(data):
                scr.addstr(idx, 0, item)

            scr.refresh()
            time.sleep(0.5)
            if self.run_once:
                return
