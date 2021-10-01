from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.tests.random_number import RandomNumber
from MainControlLoop.aprs import APRS
from MainControlLoop.eps import EPS
import datetime


class MainControlLoop:
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.LOWER_THRESHOLD = 6
        self.UPPER_THRESHOLD = 8
        self.state_field_registry: StateFieldRegistry = StateFieldRegistry()
        self.randnumber = RandomNumber(self.state_field_registry)
        self.aprs = APRS(self.state_field_registry)
        self.eps = EPS(self.state_field_registry)
        self.command_registry = {
            "TST": (self.log, "Hello"),  # Test method
            "BVT": (self.aprs.write, "TJ;" + str(self.eps.battery_voltage())),  # Reads and transmit battery voltage
            "CHG": (self.charging_mode, None),  # Enters charging mode
            "SCI": (self.science_mode, None),  # Enters science mode
            "U": self.set_upper,  # Set upper threshold
            "L": self.set_lower,  # Set lower threshold
        }

    def set_lower(self, threshold):
        self.LOWER_THRESHOLD = threshold

    def set_upper(self, threshold):
        self.UPPER_THRESHOLD = threshold

    def log(self, string) -> None:
        """
        Logs string
        """
        with open("log.txt", "a") as f:
            f.write(string + "\n")

    def command_interpreter(self) -> bool:
        """
        This will take whatever is read, parse it, and then execute it
        :return: (bool) whether the control ran without error
        """
        try:
            raw_command: str = self.state_field_registry.RECEIVED_COMMAND
        except AttributeError:
            return False
        # If no command was received, don't do anything
        if raw_command == "":
            return True
        self.state_field_registry.RECEIVED_COMMAND = ""
        # Attempts to execute command
        try:
            # Extracts 3-letter code from raw message
            command = raw_command[raw_command.find("TJ;")+3:raw_command.find("TJ;")+6]
            # Executes command associated with code and logs result
            with open("log.txt", "a") as f:
                # Executes command
                if command[1:].isdigit():
                    result = self.command_registry[command[0]](int(command[1]) + float(command[2]) / 10)
                else:
                    result = self.command_registry[command][0](self.command_registry[command][1])
                # Timestamp + tab + code + tab + result of command execution + newline
                f.write(str(datetime.datetime.now().timestamp()) + "\t" + command + "\t" + result + "\n")
            return True
        except Exception:
            return False
    
    def charging_mode(self) -> bool:
        """
        Enter charging mode, with Iridium off
        :return: (bool) whether or not mode switch was successful
        """
        return self.eps.pin_off("Iridium")
    
    def science_mode(self) -> bool:
        """
        Enter science mode, with Iridium on
        :return: (bool) whether or not mode switch was successful
        """
        return self.eps.pin_on("Iridium")

    def execute(self):
        """READ"""
        #self.state_field_registry.RECEIVED_COMMAND = "TJ;BTS"
        # Reads messages from APRS
        self.aprs.read()
        # Reads battery voltage from EPS
        battery_voltage = self.eps.battery_voltage()

        """CONTROL"""
        # Runs command from APRS, if any
        self.command_interpreter()
        # Automatic mode switching
        if battery_voltage < self.LOWER_THRESHOLD:
            # Enter charging mode if battery voltage < 4
            self.charging_mode()
        elif battery_voltage > self.UPPER_THRESHOLD:
            # Enter science mode if battery has charged > 6
            self.science_mode()

    def run(self):  # Repeat main control loop forever
        #self.state_field_registry.RECEIVED_COMMAND = "TJ;BVT"
        while True:
            self.execute()
