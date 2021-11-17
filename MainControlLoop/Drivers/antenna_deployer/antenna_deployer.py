from MainControlLoop.Drivers.antenna_deployer.antenna_deploy import isisants


class AntennaDeployer:

    def __init__(self, state_field_registry):
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
