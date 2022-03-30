import traceback


def get_traceback() -> str:
    """
    Removes wrapper lines from traceback for readability
    :return: traceback
    :rtype: str
    """
    tb = traceback.format_exc().split("\n")
    result = ""
    while len(tb) > 0:
        # Include parts of traceback which don't originate from wrapper
        if (line := tb[0].strip(" ")).startswith("File"):
            if not line.endswith("in wrapper"):
                result += tb.pop(0) + "\n" + tb.pop(0) + "\n"
            else:
                tb = tb[2:]
        else:  # If this line isn't part of traceback, add
            result += tb.pop(0) + "\n"
    return result


class CustomException(Exception):
    def __init__(self, exception: Exception = None, details: str = None):
        self.exception = exception
        self.details = details

    def __repr__(self):
        if self.exception is not None:
            if self.details is not None:
                return repr(self.exception) + ": " + self.details + "\nTraceback:\n" + get_traceback()
            return repr(self.exception)
        elif self.details is not None:
            return self.details + "\nTraceback:\n" + get_traceback()
        return ""


class AntennaError(CustomException):
    def __repr__(self):
        return "AntennaError: " + repr(super().__repr__())


class APRSError(CustomException):
    def __repr__(self):
        return "APRSError: " + repr(super().__repr__())


class IridiumError(CustomException):
    def __repr__(self):
        return "IridiumError: " + repr(super().__repr__())


class EPSError(CustomException):
    def __repr__(self):
        return "EPSError: " + repr(super().__repr__())


class IMUError(CustomException):
    def __repr__(self):
        return "IMUError: " + repr(super().__repr__())


class BatteryError(CustomException):
    def __repr__(self):
        return "BatteryError: " + repr(super().__repr__())


class CommandExecutionException(CustomException):
    def __init__(self, details: str, exception: Exception = None):
        super().__init__(exception, details)

    def __repr__(self):
        return "CommandExecutionException: " + repr(super().__repr__())


class InvalidCommandException(CustomException):
    def __init__(self, details, exception: Exception = None):
        super().__init__(exception, details)

    def __repr__(self):
        return "InvalidCommandException: " + repr(super().__repr__())


class NoSignalException(CustomException):
    def __repr__(self):
        return "NoSignalException: " + repr(super().__repr__())


class HighPowerDrawError(CustomException):
    def __repr__(self):
        return "HighPowerDrawError: " + repr(super().__repr__())


class LogicalError(CustomException):
    def __repr__(self):
        return "LogicalError: " + repr(super().__repr__()) + get_traceback()


def wrap_errors(exception: callable) -> callable:
    """
    Decorator to catch all errors which aren't CustomExceptions
    And re-raise wrapped by a given CustomException
    :param exception: exception to wrap errors with
    :return: (callable) decorator
    """
    def decorator(func: callable) -> callable:
        """
        Dynamically generate a decorator depending on argument
        :param func: function to wrap
        :return: (callable) decorated function
        """

        def wrapper(*args, **kwargs) -> callable:
            """
            Attempt to run function
            If CustomException is caught, raise it up to MissionControl
            If another exception is caught, wrap it with given exception
            """
            try:  # Attempt to run function
                return func(*args, **kwargs)
            except CustomException:  # If the exception was already wrapped
                raise  # Don't wrap again
            except Exception as e:  # If the exception wasn't wrapped
                raise exception(e)  # Wrap with given exception

        return wrapper

    return decorator
