from enum import IntEnum


class TimerStatus(IntEnum):
    """
    Sentinel values for the countdown timer a worker shares with the sentinel.

    Any positive value is the number of seconds left before the sentinel
    considers the task timed out and reincarnates the worker.
    """

    TIMEOUT = 0  # task timed out, the worker has to be terminated
    IDLE = -1  # waiting for work, or working without a timeout
    RECYCLED = -2  # recycle limit reached, the worker stopped on its own
