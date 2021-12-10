class CustomException(Exception):
    def __init__(self, exception:Exception=None):
        self.exception = exception


class APRSError(CustomException): pass
class IridiumError(CustomException): pass
class EPSError(CustomException): pass
class RTCError(CustomException): pass
class IMUError(CustomException): pass
class BatteryError(CustomException): pass
class CommandExecutionError(CustomException):
    def __init__(self, details, exception:Exception=None):
        super().__init__(exception)
        self.details = details
class SystemError(CustomException): pass


def wrap_errors(exception: CustomException) -> callable:
    """
    Decorator to catch all errors which aren't CustomExceptions
    And re-raise wrapped by a given CustomException
    :param func: function to wrap
    :param exception: exception to wrap errors with
    :return: (callable) wrapped function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CustomException:
                raise
            except Exception as e:
                raise exception(e)
        return wrapper
    return decorator


def decorate_all_callables(obj: object, exception: CustomException) -> None:
    """
    Automatically decorate all callable attributes of a class at runtime with specified exception
    This allows for decoration of lambda functions defined in __init__
    MUST BE CALLED IN __init__ OF CLASS TO BE DECORATED!!!
    MUST DECORATE __init__ SEPARATELY WITH @wrap_errors(CustomException)!!!
    :param obj: instance of the class to decorate
    :param exception: exception to wrap all raised exceptions from this class with
    """
    for attr in obj.__dict__:  # there's propably a better way to do this
        # Decorate all attributes which are functions and not __init__
        # __init__ MUST BE DECORATED BY wrap_errors IN DRIVER FILE!!!
        if callable(func := getattr(obj, attr)) and func.__name__ != "__init__":
            setattr(obj, attr, wrap_errors(exception)(func))
    return obj
