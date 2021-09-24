from MainControlLoop.lib.StateFieldRegistry import registry, state_fields
from serial import Serial


class APRS:
    """
    Class for APRS
    """
    PORT = '/dev/ttyACM0'
    DEVICE_PATH = '/sys/devices/platform/soc/20980000.usb/buspower'
    BAUDRATE = 19200

    def __init__(self, state_field_registry: registry.StateFieldRegistry):
        self.state_field_registry = state_field_registry

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

    def read(self) -> str:
        """
        Reads in as many available bytes as it can if timeout permits (terminating at a \n).
        :return: (str) message read ("" if no message read)
        """
        if not self.functional():  # see if aprs is properly working
            return ""
        output = bytes()  # create an output variable
        for loop in range(50):
            try:
                next_byte = self.serial.read(size=1)
            except:
                return ""
            if next_byte == bytes():
                break
            output += next_byte  # append next_byte to output
            # stop reading if it reaches a newline
            if next_byte == '\n'.encode('utf-8'):
                break
        message = output.decode('utf-8')
        self.state_field_registry.update(
            state_fields.StateField.RECEIVED_COMMAND, message)  # store message in statefield
        return message
