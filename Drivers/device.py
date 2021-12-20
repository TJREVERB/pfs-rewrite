from lib.exceptions import wrap_errors, LogicalError


class Device:
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        self.sfr = sfr

    # general check of the device, returns True if the device is confirmed to be (somewhat) working
    @wrap_errors(LogicalError)
    def functional(self):
        return True

    # runs after device pdm is turned on
    @wrap_errors(LogicalError)
    def start(self):
        pass

    # safely kills the device before pdm is turned off
    @wrap_errors(LogicalError)
    def __del__(self):
        pass

    @wrap_errors(LogicalError)
    def __str__(self):
        return ""
