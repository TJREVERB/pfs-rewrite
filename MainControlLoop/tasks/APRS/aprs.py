from MainControlLoop.lib.StateFieldRegistry import registry, state_fields
from serial import Serial
#from smbus2 import SMBusWrapper
from smbus2 import SMBus
import time
import datetime


class APRS:
    """
    Class for APRS
    """
    PORT = '/dev/ttyACM0'
    DEVICE_PATH = '/sys/devices/platform/soc/20980000.usb/buspower'
    BAUDRATE = 19200

    def __init__(self, state_field_registry: registry.StateFieldRegistry):
        self.state_field_registry = state_field_registry
        # Registry of all commands we can be sent
        self.command_registry = {
            "TST": [print, "Hello"],  # Test method
            "BVT": [self.return_battery_voltage, None],  # Reads and transmit battery voltage
        }

    def return_battery_voltage(self) -> bool:
        """
        Gets battery voltage from EPS
        :return: (bool) whether or not the battery voltage was read and transmitted successfully
        """
        try:
            EPS_ADDRESS = 0x2b
            # with SMBusWrapper(1) as bus:
            with SMBus(1) as bus:
                bus.write_i2c_block_data(EPS_ADDRESS, 0x10, [0xE2, 0x80])
                time.sleep(0.5)
                data = bus.read_i2c_block_data(EPS_ADDRESS, 0, 2)
                time.sleep(0.5)
                adc_count = (data[0] << 8 | data[1]) * .008993157
            #return adc_count
            return self.write("TJ;" + str(adc_count))
        except Exception:
            return False

    def write(self, message: str) -> bool:
        """
        Writes the message to the APRS radio through the serial port
        :param message: (str) message to write
        :return: (bool) whether or not the write worked
        """
        if not self.functional():
            return False
        try:
            self.serial.write((message + "\n").encode("utf-8"))
            return True
        except:
            return False
        
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

    def read(self) -> bool:
        """
        Reads in as many available bytes as it can if timeout permits (terminating at a \n).
        :return: (bool) whether it was able to read a message
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

    def control(self) -> bool:
        """
        This will take whatever is read, parse it, and then execute it
        :return: (bool) whether the control ran without error
        """
        raw_command: str = self.state_field_registry.RECEIVED_COMMAND
        # If no command was received, don't do anything
        if raw_command is None:
            return True
        # Attempts to execute command
        try:
            # Extracts 3-letter code from raw message
            command = raw_command[raw_command.find("TJ;")+3:raw_command.find("TJ;")+6]
            # Executes command associated with code and logs result
            with open("log.txt", "a") as f:
                # Timestamp + tab + code + tab + result of command execution + newline
                f.write(str(datetime.datetime.now().timestamp()) + "\t" + command + "\t" +
                        self.command_registry[command][0](self.command_registry[command][1]) + "\n")
            return True
        except Exception:
            return False
   