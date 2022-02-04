import time
from lib.exceptions import wrap_errors, LogicalError


class Clock:
    @wrap_errors(LogicalError)
    def __init__(self, delay: float):
        """
        Runs a function on a time interval
        :param delay: time to wait (seconds)
        """
        self.delay = delay
        self.last_iteration = time.time()

    @wrap_errors(LogicalError)
    def time_elapsed(self) -> bool:
        """
        Notifies if enough time has passed for the function to be run
        :return: whether function can be run
        """
        return time.time() > self.last_iteration + self.delay

    @wrap_errors(LogicalError)
    def update_time(self):
        """
        Updates the last_iteration of this clock object
        """
        self.last_iteration = time.time()
