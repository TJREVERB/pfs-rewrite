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
        self.func, self.delay, self.last_iteration = func, delay, 0

    @wrap_errors(LogicalError)
    def execute(self) -> bool:
        """
        Execute function if enough time has passed, otherwise update last iteration
        Conditions are checked IN ORDER!!! If condition 1 fails, condition 2 is not run
        """
        if t := time.time() > self.last_iteration + self.delay:  # If enough time has passed
            self.last_iteration = t  # Update last iteration
            return self.func()  # Run function, return whether it ran
        return False  # Return False if function was not run
