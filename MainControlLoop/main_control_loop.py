from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.tests.random_number import RandomNumber
from aprs import APRS
from eps import EPS
import datetime


class MainControlLoop:
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.state_field_registry: StateFieldRegistry = StateFieldRegistry()
        self.randnumber = RandomNumber(self.state_field_registry)
        self.aprs = APRS(self.state_field_registry)
        self.eps = EPS(self.state_field_registry)
        self.command_registry = {
            "TST": (print, "Hello"),  # Test method
            "BVT": (self.aprs.write, "TJ;" + str(self.eps.battery_voltage())),  # Reads and transmit battery voltage
        }

    def command_interpreter(self) -> bool:
        """
        This will take whatever is read, parse it, and then execute it
        :return: (bool) whether the control ran without error
        """
        raw_command: str = self.state_field_registry.RECEIVED_COMMAND
        # If no command was received, don't do anything
        if raw_command == "":
            return True
        # Attempts to execute command
        try:
            # Extracts 3-letter code from raw message
            command = raw_command[raw_command.find("TJ;")+3:raw_command.find("TJ;")+6]
            # Executes command associated with code and logs result
            with open("log.txt", "a") as f:
                # Executes command
                result = self.command_registry[command][0](self.command_registry[command][1])
                # Timestamp + tab + code + tab + result of command execution + newline
                f.write(str(datetime.datetime.now().timestamp()) + "\t" + command + "\t" + result + "\n")
            return True
        except Exception:
            return False

    def execute(self):
        """READ"""
        self.randnumber.read()
        self.aprs.read()

        """CONTROL"""
        self.randnumber.control()
        self.randnumber.actuate()
        self.command_interpreter()

    def run(self):  # Repeat main control loop forever
        while True:
            self.execute()
