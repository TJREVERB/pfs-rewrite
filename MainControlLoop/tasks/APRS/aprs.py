from MainControlLoop.lib.StateFieldRegistry import registry, state_fields
from serial import Serial

from smbus2 import SMBusWrapper
import time


class APRS:
    PORT = '/dev/ttyACM0'
    DEVICE_PATH = '/sys/devices/platform/soc/20980000.usb/buspower'
    BAUDRATE = 19200

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
            #self.transmit("TJ;" + adc_count)
        except Exception:
            return "Failed"
    
    def transmit(self, str):
        pass
        
    def functional(self) -> bool:
        """
        Checks the state of the serial port (initializing it if needed)
        :return: (bool) serial connection is working
        """
        if self.serial is None:  # if serial has not been connected yet
            try:
                self.serial = Serial(
                    port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
                self.serial.flush()
                return True
            except:
                return False

        try:  # try to open the serial, and return whether it worked
            self.serial.open()
            self.serial.flush()
            return True
        except:
            return False

    def read(self):
        """
        Reads in as many available bytes as it can if timeout permits (terminating at a \n).
        :return: whether it was able to read a message
        """

        if not self.functional():  # see if aprs is properly working
            return False

        output = bytes()  # create an output variable
        for loop in range(50):
            try:
                next_byte = self.serial.read(size=1)
            except:
                return False

            if next_byte == bytes():
                break

            output += next_byte  # append next_byte to output
            # stop reading if it reaches a newline
            if next_byte == '\n'.encode('utf-8'):
                break

        message = output.decode('utf-8')
        self.state_field_registry.update(
            state_fields.StateField.RECEIVED_COMMAND, message)  # store message in statefield
        return True

    
    def control(self): #this will take whatever is read, parse it, and then execute it
        raw_command = self.state_field_registry.RECEIVED_COMMAND
        # Extracts 3-letter command from long raw command
        command = raw_command[raw_command.find("TJ;")+3:raw_command.find("TJ;")+6]
        with open("output.txt", "a") as f:
            f.write(self.command_registry[command][0](self.command_registry[command][1]) + "\n")
        self.serial = None

   