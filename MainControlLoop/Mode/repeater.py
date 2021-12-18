from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError


class Repeater(Mode):
    @wrap_errors(LogicalError)
    def __str__(self):
        return "Repeater"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super().start([self.sfr.vars.PRIMARY_RADIO, "APRS"])
        self.sfr.devices["APRS"].enable_digi()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:  # If low battery
            # Switch to charging, then outreach
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Outreach"])
        return self

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        super(Repeater, self).terminate_mode()
        self.sfr.devices["APRS"].disable_digi()
