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
            "Test": 'AT',  # Tests connection to Iridium
            "Geolocation": 'AT-MSGEO',
            "Active Config": 'AT+V',
            "Check Registration": 'AT+SBDREG?',
            "Phone Model": 'AT+CGMM',
            "Phone Revision": 'AT+CGMR',
            "Phone IMEI": 'AT+CSGN',
            "Check Network": 'AT-MSSTM',
            "Shut Down": 'AT*F',
            "Signal Quality": 'AT+CSQ',  # Returns strength of satellite connection

            # FIXME: cannot be tested until patch antenna is working
            # following commands probably need to be retested once patch antenna is fixed

            "Send SMS": 'AT+CMGS=',
            "SBD Ring Alert On": 'AT+SBDMTA=1',
            "SBD Ring Alert Off": 'AT+SBDMTA=0',
            "Battery Check": 'AT+CBC=?',
            "Call Status": 'AT+CLCC=?',
            "Soft Reset": 'ATZn',
        }

    def functional(self) -> bool:
        """
        Checks the state of the serial port (initializing it if needed) and verifies that AT returns OK
        :return: (bool) serial connection is working
        """
        if self.serial is None:
            try:
                self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
            except:
                return False
        if not self.serial.is_open:
            try:
                self.serial.open()
            except:
                return False
        self.serial.flush()
        self.write(self.commands["Test"])
        if self.read().find("OK") != -1:
            return True
        return False

    def request(self, command: str) -> str:
        """
        Requests information from Iridium and returns parsed response
        :param command: Command to send
        :return: (str) Response from Iridium
        """
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
