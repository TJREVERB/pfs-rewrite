from MainControlLoop.Mode.mode import Mode
import time
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Repeater(Mode):  # TODO: IMPLEMENT
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        super().__init__(sfr)
        self.conditions = {
            "Low Battery": False
        }

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Repeater"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super(Repeater, self).start()
        self.conditions["Low Battery"] = self.sfr.battery.telemetry["VBAT"]() < self.LOWER_THRESHOLD
        self.sfr.instruct["Pin On"]("Iridium")
        self.sfr.instruct["Pin On"]("APRS")
        self.sfr.instruct["All Off"](exceptions=["Iridium", "APRS"])
        self.sfr.devices["APRS"].enable_digi()

    @wrap_errors(LogicalError)
    def check_conditions(self) -> bool:
        super(Repeater, self).check_conditions()

        return not self.conditions["Low Battery"]  # as long as the battery is still good

    # always returns charging. just read the comment in outreach mode's switch_mode, I don't feel like writing it
    # here again
    @wrap_errors(LogicalError)
    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        return self.sfr.modes_list["Charging"]

    @wrap_errors(LogicalError)
    def update_conditions(self):
        super(Repeater, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.battery.telemetry["VBAT"]() < self.LOWER_THRESHOLD

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        self.read_radio()
        self.transmit_radio()
        self.check_time()
        super(Repeater, self).execute_cycle()
        self.sfr.dump()  # Log changes

    @wrap_errors(LogicalError)
    def read_radio(self):
        super(Repeater, self).read_radio()

    @wrap_errors(LogicalError)
    def transmit_radio(self):
        return super(Repeater, self).transmit_radio()

    @wrap_errors(LogicalError)
    def check_time(self):
        return super(Repeater, self).check_time()

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        self.sfr.devices["APRS"].disable_digi()
        super(Repeater, self).terminate_mode()
        pass
