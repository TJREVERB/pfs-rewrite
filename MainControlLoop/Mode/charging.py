from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError


class Charging(Mode):
    @wrap_errors(LogicalError)
    def __init__(self, sfr, mode: type):
        super().__init__(sfr)
        self.mode = mode

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Charging"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super().start([self.sfr.vars.PRIMARY_RADIO])

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT > self.sfr.vars.UPPER_THRESHOLD:
            return self.mode(self.sfr)
        return self
