from MainControlLoop.lib.StateFieldRegistry import registry, state_fields
from serial import Serial
import time


class APRS:
    """
    Class for APRS
    """
    PORT = '/dev/ttyACM0'
    DEVICE_PATH = '/sys/devices/platform/soc/20980000.usb/buspower'
    BAUDRATE = 19200

    def __init__(self, state_field_registry: registry.StateFieldRegistry):
        self.state_field_registry = state_field_registry
        self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        while not self.serial.is_open:
            time.sleep(0.5)

    def functional(self) -> bool:
        """
        Checks the state of the serial port (initializing it if needed)
        Calls powered_on() to check whether APRS is on and working
        TODO: EXCEPTION HANDLING TO DIFFERENTIATE BETWEEEN SERIAL FAILURE (which is likely mission end) AND APRS FAILURE (possibly recoverable)
        :return: (bool) APRS and serial connection are working
        """
        if self.serial is None:
            try:
                self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)
            except:
                return False
        if not self.serial.is_open():
            try:
                self.serial.open()
            except:
                return False
        self.serial.flush()
        self.serial.write((chr(27) + chr(27) + chr(27) + "\n").encode("utf-8"))
        self.serial.write((chr(27) + chr(27) + chr(27) + "\n").encode("utf-8"))
        self.serial.write((chr(27) + chr(27) + chr(27) + "\n").encode("utf-8"))
        """time.sleep(.3)
        self.write("MYCALL")
        try:
            # For now, just reads first byte, and if byte exists and isn't empty.
            byte = self.serial.read(size=1)
            # Can be updated to match what the message actually is and match it to an expected value
            # once we get a good idea of what we expect from MYCALL
        except:
            return False
        if byte == bytes():
            return False
        self.serial.flush()
        self.serial.write(("\n").encode("utf-8"))
        time.sleep(.3)
        self.serial.write("QUIT\n".encode("utf-8"))
        time.sleep(.5)"""
        return True

    def clear_data_lines(self) -> None:
        with open("/sys/devices/platform/soc/20980000.usb/buspower", "w") as f:
            f.write(str(0))
        time.sleep(15)
        with open("/sys/devices/platform/soc/20980000.usb/buspower", "w") as f:
            f.write(str(1))
        time.sleep(5)

    def write(self, message: str) -> bool:
        """
        Writes the message to the APRS radio through the serial port
        :param message: (str) message to write
        :return: (bool) whether or not the write worked
        """
        try:
            self.serial.write((message + "\n").encode("utf-8"))
            self.serial.flush()
            return True
        except:
            return False

    def read(self) -> str:
        """
        Reads in as many available bytes as it can if timeout permits (terminating at a \n).
        :return: (str) message read ("" if no message read)
        """
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
