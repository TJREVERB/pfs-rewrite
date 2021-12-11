class CustomException(Exception):
    def __init__(self, exception: Exception = None):
        self.exception = exception


class APRSError(CustomException): pass


class IridiumError(CustomException): pass


class EPSError(CustomException): pass


class RTCError(CustomException): pass


class IMUError(CustomException): pass


class BatteryError(CustomException): pass


class CommandExecutionError(CustomException):
    def __init__(self, details, exception: Exception = None):
        super().__init__(exception)
        self.details = details


class LogicalError(CustomException): pass


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
            try:
                return func(*args, **kwargs)
            except CustomException:
                raise
            except Exception as e:
                raise exception(e)
        return wrapper
    return decorator
