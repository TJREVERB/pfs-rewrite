from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.eps import EPS


class Reset:
    def __init__(self):
        self.sfr = StateFieldRegistry()
        self.eps = EPS(self.sfr)
    def reset(self):
        self.sfr.reset()
        self.eps.commands["Bus Reset"](["Battery", "5V", "3.3V", "12V"])
        exit(0)
