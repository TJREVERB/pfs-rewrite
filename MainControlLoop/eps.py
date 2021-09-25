from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from smbus2 import SMBusWrapper
#from smbus2 import SMBus
import time


class EPS:
    """
    Class for EPS
    """
    def __init__(self, state_field_registry):
        self.EPS_ADDRESS: hex = 0x2b
        self.state_field_registry: state_field_registry = state_field_registry
        self.components = {  # List of components and their associated pins
            "APRS": [0x04],
            "Iridium": [0x03],
            "AntennaDeployer": ""
        }

    def battery_voltage(self) -> float:
        """
        Reads and returns current battery voltage
        :return: (float) battery voltage
        """
        with SMBusWrapper(1) as bus:
        #with SMBus(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x10, [0xE2, 0x80])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
            time.sleep(0.5)
            adc_count = (data[0] << 8 | data[1]) * .008993157
        return adc_count
    
    def pin_on(self, component: str) -> bool:
        """
        Enable component
        :param component: Component to enable
        :return: (bool) whether enable component succeeded
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x50, self.components[component])

    def pin_off(self, component: str) -> bool:
        """
        Disable component
        :param component: Component to disable
        :return: (bool) whether disable component succeeded
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x51, self.components[component])
