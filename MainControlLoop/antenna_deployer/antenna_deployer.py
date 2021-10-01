from MainControlLoop.lib.StateFieldRegistry import registry, state_fields
#from MainControlLoop.antenna_deployer.antenna_deploy import deploy, isisants
from MainControlLoop.antenna_deployer.antenna_deploy import isisants
import time


class AntennaDeployer:
    THIRTY_MINUTES = 5  # 1800 seconds in 30 minutes

    def __init__(self, state_field_registry: registry.StateFieldRegistry):
        self.state_field_registry = state_field_registry

    def deploy(self):
        # Initiate connection with the device
        isisants.py_k_ants_init(b"/dev/i2c-1", 0x31, 0x32, 4, 10)

        # Arms the device
        isisants.py_k_ants_disarm()
        isisants.py_k_ants_arm()
        #isisants.py_k_
        

        # Run the deploy methods
        ANT_1 = 0
        ANT_2 = 1
        ANT_3 = 2
        ANT_4 = 3
        isisants.py_k_ants_deploy(ANT_1, False, 5)
        isisants.py_k_ants_deploy(ANT_2, False, 5)
        isisants.py_k_ants_deploy(ANT_3, False, 5)
        isisants.py_k_ants_deploy(ANT_4, False, 5)

    def control(self):
        # if antenna is not deployed, see if we can deploy it
        if(self.state_field_registry.get(state_fields.StateField.ANTENNA_DEPLOYED) == False):
            # if 30 minutes have elapsed
            if(time.time() - self.state_field_registry.get(state_fields.StateField.START_TIME) > self.THIRTY_MINUTES):
                self.deploy()
                print("deployed")
                self.state_field_registry.update(
                    state_fields.StateField.ANTENNA_DEPLOYED, True)
