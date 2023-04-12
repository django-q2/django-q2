import curses
from django_q.conf import Conf
import signal

import time
from django_q.status import Stat
from django_q.brokers import get_broker
from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _
from django.utils import timezone
import curses

try:
    import psutil
except ImportError:
    psutil = None


class Command(BaseCommand):
    # Translators: help text for qmemory management command
    help = _("Monitors Q Cluster memory usage")

    def add_arguments(self, parser):
        parser.add_argument(
            "--run-once",
            action="store_true",
            dest="run_once",
            default=False,
            help="Run once and then stop.",
        )
        parser.add_argument(
            "--workers",
            action="store_true",
            dest="workers",
            default=False,
            help="Show each worker's memory usage.",
        )

    def handle(self, *args, **options):
        memory_stats = MemoryTerminalStats(
            run_once=options.get("run_once", False),
            workers=options.get("workers", False),
        )
        curses.wrapper(memory_stats.start)


def get_process_mb(pid):
    try:
        process = psutil.Process(pid)
        mb_used = round(process.memory_info().rss / 1024**2, 2)
    except psutil.NoSuchProcess:
        mb_used = "NO_PROCESS_FOUND"
    return mb_used


class MemoryTerminalStats:
    stop_writing = False

    def __init__(self, run_once=False, workers=False):
        self.run_once = run_once
        self.workers = workers

    def start(self, stdscr):
        self.show_stats()

    def on_exit(self, signum, frame):
        # exit clean
        self.stop_writing = True

    def show_stats(self):
        signal.signal(signal.SIGTERM, self.on_exit)
        signal.signal(signal.SIGINT, self.on_exit)
        scr = curses.initscr()

        if not broker:
            broker = get_broker()

        broker.ping()
        if not psutil:
            scr.addstr(0, 0, 'Cannot start "qmemory" command. Missing "psutil" library.')
            scr.refresh()
            return

        MEMORY_AVAILABLE_LOWEST_PERCENTAGE = 100.0
        MEMORY_AVAILABLE_LOWEST_PERCENTAGE_AT = timezone.now()

        stats = Stat.get_all(broker=broker)

        if not stats:
            scr.addstr(1, 0, "Cluster is not running")
            scr.refresh()
        while not self.stop_writing:
            data = []
            for stat in stats:
                # memory available (%)
                memory_available_percentage = round(
                    psutil.virtual_memory().available
                    * 100
                    / psutil.virtual_memory().total,
                    2,
                )
                # memory available (MB)
                memory_available = round(
                    psutil.virtual_memory().available / 1024**2, 2
                )
                if memory_available_percentage < MEMORY_AVAILABLE_LOWEST_PERCENTAGE:
                    MEMORY_AVAILABLE_LOWEST_PERCENTAGE = memory_available_percentage
                    MEMORY_AVAILABLE_LOWEST_PERCENTAGE_AT = timezone.now()

                data.append(f"Host: {str(stat.host)}")
                data.append(f"ID: {str(stat.cluster_id)[-8:]}")
                data.append(f"Available (%): {memory_available_percentage}")
                data.append(f"Available (MB): {memory_available}")
                data.append(f"Total (MB): {round(psutil.virtual_memory().total / 1024**2, 2)}")
                data.append(f"Sentinel (MB): {get_process_mb(stat.sentinel)}")
                data.append(f"Monitor (MB): {get_process_mb(getattr(stat, 'monitor', None))}")

                if self.workers:
                    data.append("")
                    for worker_num in range(Conf.WORKERS):
                        data.append(f"Worker #{worker_num+1} (MB): {get_process_mb(stat.workers[worker_num])}")

                data.append("")
                data.append(_("Available lowest: %(memory_percent)s (%(at)s)")
                % {
                    "memory_percent": str(MEMORY_AVAILABLE_LOWEST_PERCENTAGE),
                    "at": MEMORY_AVAILABLE_LOWEST_PERCENTAGE_AT.strftime(
                        "%Y-%m-%d %H:%M:%S+00:00"
                    ),
                })


            for idx, item in enumerate(data):
                scr.addstr(idx, 0, item)

            scr.refresh()
            time.sleep(0.5)
            if self.run_once:
                return
