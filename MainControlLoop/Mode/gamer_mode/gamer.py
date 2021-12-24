from MainControlLoop.Mode.mode import Mode
import time
import pickle
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Gamer(Mode):
    def __init__(self, sfr):
        super().__init__(sfr)
        self.next_human_move = None
        self.sfr = sfr
        self.board_obj = None
        self.conditions = {
            "Low Battery": False
        }

    def __str__(self):
        return "Gamer"

    def load_game(self):
        with open("game_file.pkl", "rb") as f:
            self.board_obj = pickle.load(f)

    def start(self):
        super().start([self.sfr.vars.PRIMARY_RADIO])
    def suggested_mode(self):
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:
            return self.sfr.modes_list["Charging"](self.sfr, self)
        else:
            return self
    def check_conditions(self) -> bool:
        super().check_conditions()
        return not self.conditions["Low Battery"]

    def update_conditions(self) -> None:
        super(Gamer, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD

    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        return self.sfr.modes_list["Charging"]

    def execute_cycle(self) -> None:
