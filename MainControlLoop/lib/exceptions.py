class CustomException(Exception):
    def __init__(self, exception: Exception = None, details: str = None):
        self.exception = exception
        self.details = details

    def __repr__(self):
        if self.exception is not None:
            if self.details is not None:
                return repr(self.exception) + ": " + self.details
            return repr(self.exception)
        elif self.details is not None:
            return self.details
        return ""


class AntennaError(CustomException):
    def __repr__(self):
        return "AntennaError: " + super().__repr__()


class APRSError(CustomException):
    def __repr__(self):
        return "AntennaError: " + super().__repr__()


class IridiumError(CustomException): 
    def __repr__(self):
        return "AntennaError: " + super().__repr__()


class SignalStrengthException(CustomException): 
    def __repr__(self):
        return "AntennaError: " + super().__repr__()


class EPSError(CustomException): 
    def __repr__(self):
        return "AntennaError: " + super().__repr__()


class RTCError(CustomException): 
    def __repr__(self):
        return "AntennaError: " + super().__repr__()


class IMUError(CustomException): 
    def __repr__(self):
        return "AntennaError: " + super().__repr__()


class BatteryError(CustomException): 
    def __repr__(self):
        return "AntennaError: " + super().__repr__()


class CommandExecutionException(CustomException):
    def __init__(self, details, exception: Exception = None):
        super().__init__(exception, details)


class InvalidCommandException(CustomException):
    def __init__(self, details, exception: Exception = None):
        super().__init__(exception, details)


class NoSignalException(CustomException): pass


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
            try:  # Attempt to run function
                return func(*args, **kwargs)
            except CustomException:  # If the exception was already wrapped
                raise  # Don't wrap again
            except Exception as e:  # If the exception wasn't wrapped
                raise exception(e)  # Wrap with given exception

        return wrapper

    return decorator
