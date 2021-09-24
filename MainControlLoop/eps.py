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

    def battery_voltage(self):
        with SMBusWrapper(1) as bus:
        #with SMBus(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x10, [0xE2, 0x80])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
            time.sleep(0.5)
            adc_count = (data[0] << 8 | data[1]) * .008993157
        return adc_count
