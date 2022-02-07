from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError


class Charging(Mode):
    @wrap_errors(LogicalError)
    def __init__(self, sfr, mode: type):
        super().__init__(sfr)
        self.mode = mode

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns mode name as string

        :return: mode name
        :rtype: str
        """
        return "Charging"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        """
        Runs initial setup for a mode. Turns on and off devices for a specific mode.
        """
        return super().start([self.sfr.vars.PRIMARY_RADIO])

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        """
        Checks all conditions and returns which mode the current mode believes we should be in
        If we don't want to switch, return same mode
        If we do, return the mode we want to switch to
        :return: instantiated mode object to switch to
        :rtype: :class: 'Mode'
        """
        super().suggested_mode()
        if self.sfr.check_upper_threshold():
            return self.mode(self.sfr)
        return self
