from MainControlLoop.antenna_deployer.AntennaDeployer import AntennaDeployer
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.eps import EPS

sfr = StateFieldRegistry()
antenna = AntennaDeployer(sfr)
eps = EPS(sfr)
eps.commands["Pin On"]("Antenna Deployer")
print("Enabled:",antenna.enable())
print("Deployed:",antenna.deploy())