# DO NOT RUN!!!
# Use exec(open("reset.py").read()) in python shell to avoid corrupting file
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.eps import EPS


sfr = StateFieldRegistry()
eps = EPS(sfr)
sfr.reset()
eps.commands["Bus Reset"](["Battery", "5V", "3.3V", "12V"])
