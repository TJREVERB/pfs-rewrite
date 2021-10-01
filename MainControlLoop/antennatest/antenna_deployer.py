from MainControlLoop.lib.StateFieldRegistry import registry, state_fields
from MainControlLoop.antennatest.antenna_deploy import deploy, isisants
import time


class AntennaDeployer:
    THIRTY_MINUTES = 5  # 1800 seconds in 30 minutes

    def __init__(self, state_field_registry: registry.StateFieldRegistry):
        self.state_field_registry = state_field_registry

    def antenna_deploy(self):
        pass

    def control(self):
        # if antenna is not deployed, see if we can deploy it
        if(self.state_field_registry.get(state_fields.StateField.ANTENNA_DEPLOYED) == False):
            # if 30 minutes have elapsed
            if(time.time() - self.state_field_registry.get(state_fields.StateField.START_TIME) > self.THIRTY_MINUTES):
                print("deployed")
                self.deploy()
                self.state_field_registry.update(
                    state_fields.StateField.ANTENNA_DEPLOYED, True)
