from MainControlLoop.Mode.mode import Mode
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Repeater(Mode):
    @wrap_errors(LogicalError)
    def __str__(self):
        return "Repeater"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super().start()
        self.sfr.instruct["Pin On"]("IMU")
        self.sfr.instruct["Pin On"]("Iridium")
        self.sfr.instruct["Pin On"]("APRS")
        self.sfr.instruct["All Off"](exceptions=["Iridium", "APRS"])
        self.sfr.devices["APRS"].enable_digi()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:  # If low battery
            # Switch to charging, then outreach
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Outreach"])

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        super(Repeater, self).terminate_mode()
        self.sfr.devices["APRS"].disable_digi()
