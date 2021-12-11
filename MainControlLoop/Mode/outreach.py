from MainControlLoop.Mode.mode import Mode
import time
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Outreach(Mode):
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        super().__init__(sfr)

        self.conditions = {
            "Low Battery": False
        }

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Outreach"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super(Outreach, self).start()
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")
        self.instruct["All Off"](exceptions=["Iridium", "APRS"])

    @wrap_errors(LogicalError)
    def check_conditions(self) -> bool:
        super(Outreach, self).check_conditions()

        return not (self.conditions["Low Battery"])  # as long as the battery is not low, we stay

    # This will always return charging mode, regardless of the conditions... even if check_conditions was previously
    # true If this is ever called when check_conditions was still true, there is probably a reason, so return a
    # DIFFERENT mode
    @wrap_errors(LogicalError)
    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        return self.sfr.modes_list["Charging"]  # suggest charging

    @wrap_errors(LogicalError)
    def update_conditions(self) -> None:
        super(Outreach, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() > self.sfr.vars.LOWER_THRESHOLD

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        self.read_radio()
        self.transmit_radio()
        self.check_time()
        super(Outreach, self).execute_cycle()

    @wrap_errors(LogicalError)
    def read_radio(self):
        super(Outreach, self).read_radio()

    @wrap_errors(LogicalError)
    def transmit_radio(self):
        return super(Outreach, self).transmit_radio()

    @wrap_errors(LogicalError)
    def check_time(self):
        return super(Outreach, self).check_time()

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        super(Outreach, self).terminate_mode()
