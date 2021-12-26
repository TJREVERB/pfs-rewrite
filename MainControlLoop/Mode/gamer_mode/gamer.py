from MainControlLoop.Mode.mode import Mode
import time
import pickle
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Gamer(Mode):  # gamer mode before player picks game
    def __str__(self):
        return "Gamer"

    def start(self):
        super().start([self.sfr.vars.PRIMARY_RADIO])

    def suggested_mode(self):
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:
            return self.sfr.modes_list["Charging"](self.sfr, self)
        else:
            return self

    def execute_cycle(self) -> None:
        # transmit that it is in gamer mode, and prompts user to pick game
        pass
