from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.mode import Outreach
from MainControlLoop.Mode.mode import Charging
import gc


class Repeater(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)

        self.conditions = {
            "CHARGE_LOW": False
        }


    def __str__(self):
        return "Repeater"

    def start(self) -> None:
        super(Repeater, self).start()
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")

    def check_conditions(self) -> bool:
        self.conditions["CHARGE_LOW"] = self.sfr.eps.telemetry["VBCROUT"]() > self.LOWER_THRESHOLD
        if self.conditions["CHARGE_LOW"]:  # if voltage is less than upper limit
            return False
        else:
            return True

    def execute_cycle(self) -> None:
        super(Repeater, self).execute_cycle()
        self.sfr.devices[self.sfr.PRIMARY_RADIO].listen()
        self.sfr.dump()  # Log changes

    def switch_modes(self) -> None:
        super(Repeater, self).switch_modes()  # Run switch_modes of superclass

        if self.conditions["CHARGE_LOW"]:  # if the battery is low, switch to charging mode
            return Charging
        
        return Outreach #if this is called even though the conditions are met, this just returns itself

    def terminate_mode(self) -> None:
        # TODO: write to APRS to turn off digipeating
        self.instruct["Pin Off"]("Iridium")
        self.instruct["Pin Off"]("APRS")


