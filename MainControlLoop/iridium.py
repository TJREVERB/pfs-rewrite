import time
from serial import Serial
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry


class Iridium:
    PORT = '/dev/serial0'
    BAUDRATE = 19200

    def __init__(self, state_field_registry: StateFieldRegistry):
        self.state_field_registry: state_field_registry = state_field_registry
        self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        while not self.serial.is_open:
            time.sleep(0.5)
        self.commands = {
            "TEST_IRIDIUM": 'AT',
            "GEOLOCATION": 'AT-MSGEO',
            "ACTIVE_CONFIG": 'AT+V',
            "CHECK_REGISTRATION": 'AT+SBDREG?',
            "PHONE_MODEL": 'AT+CGMM',
            "PHONE_REVISION": 'AT+CGMR',
            "PHONE_IMEI": 'AT+CSGN',
            "CHECK_NETWORK": 'AT-MSSTM',
            "SHUT_DOWN": 'AT*F',
            "SIGNAL_QUAL": 'AT+CSQ',

            # FIXME: cannot be tested until patch antenna is working
            # following commands probably need to be retested once patch antenna is fixed

            "SEND_SMS": 'AT+CMGS=',
            "SIGNAL": 'AT+CSQ',
            "SBD_RING_ALERT_ON": 'AT+SBDMTA=1',
            "SBD_RING_ALERT_OFF": 'AT+SBDMTA=0',
            "BATTERY_CHECK": 'AT+CBC=?',
            "CALL_STATUS": 'AT+CLCC=?',
            "SOFT_RESET": 'ATZn',
        }
        self.responses = {
            "OK": [b'O', b'K'],
            "ERROR": [b'E', b'R', b'R', b'O', b'R'],
        }

    def flush(self):
        """
        Clears the serial buffer
        :return: (None)
        """
        self.serial.flushInput()
        self.serial.flushOutput()

    def functional(self) -> bool:
        """
        Checks the state of the serial port (initializing it if needed)
        :return: (bool) serial connection is working
        """
        if self.serial is None:
            try:
                self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)
                self.serial.flush()
                return True
            except:
                return False

        if self.serial.is_open:
            return True

        try:
            self.serial.open()
            self.serial.flush()
            return True
        except:
            return False

    def request(self, command: str) -> str:
        self.write(command)
        result = self.read()
        index = result.find(":")+1
        return result[index:result[index:].find("\n")+len(result[:index])].lstrip(" ")

    def write(self, command: str) -> bool:
        """
        Write a command to the serial port.
        :param command: (str) Command to write
        :return: (bool) if the serial write worked
        """
        command = command + "\r\n"
        try:
            self.serial.write(command.encode("UTF-8"))
        except:
            return False
        return True

    def read(self) -> str:
        """
        Reads in as many available bytes as it can if timeout permits.
        :return: (str) string read from iridium
        """
        output = bytes()
        for loop in range(50):
            try:
                next_byte = self.serial.read(size=1)
            except:
                break
            if next_byte == bytes():
                break
            output += next_byte
        return output.decode("utf-8")
