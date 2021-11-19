from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer
from MainControlLoop.lib.registry import StateFieldRegistry
from MainControlLoop.Drivers.eps import EPS

sfr = StateFieldRegistry()
antenna = AntennaDeployer(sfr)
eps = EPS(sfr)
eps.commands["All On"]()
print("Enabled:",antenna.enable())
print("Deployed:",antenna.deploy())