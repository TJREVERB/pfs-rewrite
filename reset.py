from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.eps import EPS


sfr = StateFieldRegistry()
sfr.reset()
eps = EPS(sfr)
eps.commands["Bus Reset"](["Battery", "5V", "3.3V", "12V"])
exit(0)
