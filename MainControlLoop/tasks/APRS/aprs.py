from MainControlLoop.lib.StateFieldRegistry import registry, state_fields

from smbus2 import SMBusWrapper
import time


class Aprs:
    """
    Class for APRS
    """

    def __init__(self, state_field_registry: registry.StateFieldRegistry):
        self.state_field_registry = state_field_registry
        # Registry of all commands we can be sent
        self.command_registry = {
            "TST": [print, "Hello"],
            "BVT": [self.return_battery_voltage, None]
        }
    
    def return_battery_voltage(self):
        try:
            EPS_ADDRESS = 0x2b
            with SMBusWrapper(1) as bus:
                bus.write_i2c_block_data(EPS_ADDRESS, 0x10, [0xE2, 0x80])
                time.sleep(0.5)
                data = bus.read_i2c_block_data(EPS_ADDRESS, 0, 2)
                time.sleep(0.5)
                adc_count = (data[0]<<8 | data[1])*.008993157
            return adc_count
        except Exception:
            return "Failed"
        
    def read(self): # Reads from APRS and updates state field registry
        # replace with something that actually reads, this is for testing
        self.state_field_registry.RECEIVED_COMMAND = "leseoisdlkjfeilsdkTJ;BVTlksdjfleijskdfjlesj"
    
    def control(self): #this will take whatever is read, parse it, and then execute it
        raw_command = self.state_field_registry.RECEIVED_COMMAND
        # Extracts 3-letter command from long raw command
        command = raw_command[raw_command.find("TJ;")+3:raw_command.find("TJ;")+6]
        with open("output.txt", "a") as f:
            f.write(self.command_registry[command][0](self.command_registry[command][1]) + "\n")
