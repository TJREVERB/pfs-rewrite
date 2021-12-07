from MainControlLoop.Mode.mode import Mode
import time


class Repeater(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)
        self.conditions = {
            "Low Battery": False
        }

    def __str__(self):
        return "Repeater"

    def start(self) -> None:
        super(Repeater, self).start()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")
        self.instruct["All Off"](exceptions=["Iridium", "APRS"])
        self.sfr.devices["APRS"].enable_digi()

    def check_conditions(self) -> bool:
        super(Repeater, self).check_conditions()

        return not self.conditions["Low Battery"]  # as long as the battery is still good

    # always returns charging. just read the comment in outreach mode's switch_mode, I don't feel like writing it here again
    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        return self.sfr.modes_list["Charging"]

    def update_conditions(self):
        super(Repeater, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD

    def execute_cycle(self) -> None:
        self.read_radio()
        self.transmit_radio()
        self.check_time()
        super(Repeater, self).execute_cycle()
        self.sfr.dump()  # Log changes

    def read_radio(self):
        super(Repeater, self).read_radio()
    
    def transmit_radio(self):
        return super(Repeater, self).transmit_radio()

    def check_time(self):
        return super(Repeater, self).check_time()

    def terminate_mode(self) -> None:
        self.sfr.devices["APRS"].disable_digi()
        super(Repeater, self).terminate_mode()
        pass
