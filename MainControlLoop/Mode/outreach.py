from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError


class Outreach(Mode):
    @wrap_errors(LogicalError)
    def __str__(self):
        return "Outreach"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super().start([self.sfr.vars.PRIMARY_RADIO, "APRS"])

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:
            return self.sfr.modes_list["Charging"](self.sfr, type(self))
        else:
            return self
