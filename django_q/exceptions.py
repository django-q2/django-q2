import signal

class TimeoutException(SystemExit):
    """
    Exception for when a worker takes too long to complete a task
    Raising SystemExit will make sure the function terminates gracefully.
    """
    pass


class TimeoutHandler:
    def __init__(self, timeout: int):
        self._timeout = timeout

    def raise_timeout_exception(self, signum, frame):
        raise TimeoutException(f"Task exceeded maximum timeout value ({self._timeout} seconds)")

    def __enter__(self):
        if self._timeout == -1:
            return
        signal.signal(signal.SIGALRM, self.raise_timeout_exception)
        signal.alarm(self._timeout)

    def __exit__(self, exc_type, exc_value, traceback):
        if self._timeout == -1:
            return
        """When getting out of the timeout, reset the alarm, so it won't trigger"""
        signal.alarm(0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
