from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.mode import Outreach
from MainControlLoop.Mode.mode import Charging
import gc


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
        
    def check_conditions(self) -> bool:
        if not self.conditions["Low Battery"]:  # if not low batter
            return True  # keep in current mode
        else:
            return False  # switch modes

    def update_conditions(self):
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD
        
    def execute_cycle(self) -> None:
        super(Repeater, self).execute_cycle()
        self.sfr.devices[self.sfr.PRIMARY_RADIO].listen()
        self.sfr.dump()  # Log changes

    def switch_modes(self) -> None:
        super(Repeater, self).switch_modes()  # Run switch_modes of superclass
        return Charging(self.sfr)

    def terminate_mode(self) -> None:
        # TODO: write to APRS to turn off digipeating
        super(Repeater, self).terminate_mode()
        pass


