from MainControlLoop.Mode.mode import Mode
import time
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Gamer(Mode):
    def __init__(self, sfr):
        super().__init__(sfr)
        self.sfr = sfr
        self.ttt_board = 
        self.conditions = {
            "Low Battery": False
        }

    def __str__(self):
        return "Gamer"

    def start(self):
        super(Gamer, self).start()
        self.sfr.instruct["Pin On"]("Iridium")
        self.sfr.instruct["Pin On"]("APRS")
        self.sfr.instruct["All Off"](exceptions=["Iridium", "APRS"])

        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD

    def check_conditions(self) -> bool:
        super(Gamer, self).check_conditions()

        return not self.conditions["Low Battery"]

    def update_conditions(self) -> None:
        super(Gamer, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD

    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        return self.sfr.modes_list["Charging"]

    def tictactoe(self, human_move: str):

    def execute_cycle(self) -> None:
