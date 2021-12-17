from MainControlLoop.Mode.mode import Mode
import time
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


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
        super().start()
        # TODO: THIS LEAVES THE APRS ON DURING CHARGING MODE IF IT IS PRIMARY, IS THIS INTENTIONAL?
        self.sfr.instruct["Pin On"]("IMU")
        self.sfr.instruct["Pin On"](self.sfr.vars.PRIMARY_RADIO)  # turn on primary radio
        # turn off any not required devices
        self.sfr.instruct["All Off"](exceptions=[self.sfr.vars.PRIMARY_RADIO, "IMU", "Antenna Deployer"])

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT > self.sfr.vars.UPPER_THRESHOLD:
            return self.mode(self.sfr)
        return self
