import time
from lib.exceptions import wrap_errors, LogicalError


class Clock:
    @wrap_errors(LogicalError)
    def __init__(self, func: callable, delay: float = 0, conditions: list = None):
        """
        Run given function after given delay
        :param func: function to run
        :param delay: time to wait (seconds)
        :param conditions: list of conditions functions which all must return true for function to run
        """
        self.func, self.delay, self.last_iteration = func, delay, 0
        self.conditions = [True] if conditions is None else conditions

    @wrap_errors(LogicalError)
    def execute(self) -> bool:
        """
        Execute function if enough time has passed, otherwise update last iteration
        Conditions are checked IN ORDER!!! If condition 1 fails, condition 2 is not run
        """
        for i in self.conditions:  # Explicit loop so we can check conditions in order
            if not i():  # Check condition
                return False  # And return if a condition fails
        if t := time.time() > self.last_iteration + self.delay:  # If enough time has passed
            self.func()  # Run function
            self.last_iteration = t  # Update last iteration
            return True
        return False  # Return False if function was not run
