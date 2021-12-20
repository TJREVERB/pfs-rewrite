from lib.exceptions import wrap_errors, LogicalError


class Device:
    SERIAL_CONVERTERS = []

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        does all necessary boot stuff for the device
        precondition: pdm is on
        """
        self.sfr = sfr

    @wrap_errors(LogicalError)
    def functional(self):
        """
        general check of the device, returns True if the device is confirmed to be (somewhat) working
        """
        return True

    @wrap_errors(LogicalError)
    def __del__(self):
        """
        safely kills the device before pdm is turned off
        """
        pass

    @wrap_errors(LogicalError)
    def __str__(self):
        return ""
