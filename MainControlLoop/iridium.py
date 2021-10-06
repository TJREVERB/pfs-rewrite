import time
from serial import Serial
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry


class Iridium:
    PORT = '/dev/serial0'
    BAUDRATE = 19200

    def __init__(self, state_field_registry: StateFieldRegistry):
        self.sfr = state_field_registry
        self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        while not self.serial.is_open:
            time.sleep(0.5)
        self.commands = {
            "Test": self.functional(),  # Tests connection to Iridium
            "Geolocation": lambda: self.request("AT-MSGEO"),  # Current geolocation
            "Active Config": lambda: self.request("AT+V"),
            "Check Registration": lambda: self.request("AT+SBDREG?"),
            "Phone Model": lambda: self.request("AT+CGMM"),
            "Phone Revision": lambda: self.request("AT+CGMR"),
            "Phone IMEI": lambda: self.request("AT+CSGN"),
            "Check Network": lambda: self.request("AT-MSSTM"),
            "Shut Down": lambda: self.write("AT*F"),
            "Signal Quality": lambda: self.request("AT+CSQ"),  # Returns strength of satellite connection
            "Send SMS": lambda message: self.write("AT+CMGS=" + message),
            "SBD Ring Alert On": lambda: self.write("AT+SBDMTA=1"),
            "SBD Ring Alert Off": lambda: self.write("AT+SBDMTA=0"),
            "Battery Check": lambda: self.request("AT+CBC=?"),
            "Call Status": lambda: self.request("AT+CLCC=?"),
            "Soft Reset": lambda: self.write("ATZn"),
            "Transmit": lambda message: self.write("AT+SBDWT=" + message)
        }
    
    def __del__(self):
        self.serial.close()

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
        self.write("AT")
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
    
    def wave(self) -> bool:
        """
        Transmits test message to ground station to verify Iridium works in space
        :return: (bool) Whether write worked
        """
        return self.commands["Transmit"]("TJ;Hello from outer space!")

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
