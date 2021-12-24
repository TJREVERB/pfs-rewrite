import time
from lib.exceptions import wrap_errors, LogicalError


class Clock:
    @wrap_errors(LogicalError)
    def __init__(self, func: callable, delay: float):
        """
        Run given function after given delay
        :param func: function to run
        :param delay: time to wait (seconds)
        """
        self.func = func
        self.delay = delay
        self.last_iteration = 0

    @wrap_errors(LogicalError)
    def execute(self) -> bool:
        """
        Execute function if enough time has passed, otherwise update last iteration
        Conditions are checked IN ORDER!!! If condition 1 fails, condition 2 is not run
        """
        if time.time() > self.last_iteration + self.delay:  # If enough time has passed
            result = self.func()  # Run function, return whether it ran
            self.last_iteration = time.time()  # Update last iteration
            return result
        return False
