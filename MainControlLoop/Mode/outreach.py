from MainControlLoop.Mode.mode import Mode
import time
from MainControlLoop.lib.exceptions import decorate_all_callables, wrap_errors, LogicalError


class Outreach(Mode):
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        super().__init__(sfr)

        self.conditions = {
            "Low Battery": False
        }
        decorate_all_callables(self, LogicalError)

    def __str__(self):
        return "Outreach"

    def start(self) -> None:
        super(Outreach, self).start()
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")
        self.instruct["All Off"](exceptions=["Iridium", "APRS"])

    def check_conditions(self) -> bool:
        super(Outreach, self).check_conditions()

        return not (self.conditions["Low Battery"]) #as long as the battery is not low, we stay

    # This will always return charging mode, regardless of the conditions... even if check_conditions was previously true
    # If this is ever called when check_conditions was still true, there is probably a reason, so return a DIFFERENT mode
    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        return self.sfr.modes_list["Charging"]  # suggest charging

    def update_conditions(self) -> None:
        super(Outreach, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() > self.sfr.vars.LOWER_THRESHOLD

    def execute_cycle(self) -> None:
        self.read_radio()
        self.transmit_radio()
        self.check_time()
        super(Outreach, self).execute_cycle()

    def read_radio(self):
        super(Outreach, self).read_radio()
    
    def transmit_radio(self):
        return super(Outreach, self).transmit_radio()

    def check_time(self):
        return super(Outreach, self).check_time()
    
    def terminate_mode(self) -> None:
        super(Outreach, self).terminate_mode()
        pass
