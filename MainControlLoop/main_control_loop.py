from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.lib.StateFieldRegistry.state_fields import StateField
from MainControlLoop.tests.random_number import RandomNumber
from MainControlLoop.aprs import APRS
from MainControlLoop.eps import EPS
from MainControlLoop.antenna_deployer.antenna_deployer import AntennaDeployer
from MainControlLoop.iridium import Iridium
from MainControlLoop.lib.StateFieldRegistry.state_field_logger import StateFieldLogger
import datetime
import time


class MainControlLoop:
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.THIRTY_MINUTES = 5  # 1800 seconds in 30 minutes
        self.LOWER_THRESHOLD = 6  # Lower battery voltage threshold for switching to CHARGING mode
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode
        self.state_field_registry = StateFieldRegistry()
        self.state_field_logger = StateFieldLogger(self.state_field_registry)
        self.aprs = APRS(self.state_field_registry)
        self.eps = EPS(self.state_field_registry)
        self.antenna_deployer = AntennaDeployer(self.state_field_registry)
        self.iridium = Iridium(self.state_field_registry)
        self.command_registry = {
            "TST": lambda: [i() for i in [[lambda: f.write("Hello"), lambda: f.close()]
                                          for f in [open("log.txt", "a")]][0]],  # Test method, logs "Hello"
            "BVT": lambda: self.aprs.write("TJ;" + str(self.eps.telemetry["VBCROUT"]())),
            # Reads and transmits battery voltage
            "CHG": lambda: [i() for i in [
                lambda: self.eps.commands["Pin Off"]("Iridium"),
                lambda: self.state_field_registry.update(StateField.MODE, "CHARGING")
            ]],  # Enters charging mode
            "SCI": lambda: [i() for i in [
                lambda: self.eps.commands["Pin On"]("Iridium"),
                lambda: self.state_field_registry.update(StateField.MODE, "SCIENCE")
            ]],  # Enters science mode
            "U": lambda threshold: setattr(self, "UPPER_THRESHOLD", threshold),  # Set upper threshold
            "L": lambda threshold: setattr(self, "LOWER_THRESHOLD", threshold),  # Set lower threshold
            "RST": lambda: [i() for i in [
                lambda: self.eps.commands["All Off"],
                lambda: time.sleep(.5),
                lambda: self.eps.commands["Bus Reset"](["Battery", "5V", "3.3V", "12V"])
            ]],  # Reset power to the entire satellite (!!!!)
            "IRI": lambda: None,  # Transmit message through Iridium to ground station NEEDS IMPLEMENTATION
            "PWR": lambda: self.aprs.write("TJ;" + str(self.eps.total_power())),
            # Calculate total power draw of connected components
        }
    
    def log(self):
        # run the state_field_logger; commented out during testing
        #self.state_field_logger.control()
        return

    def command_interpreter(self) -> bool:
        """
        This will take whatever is read, parse it, and then execute it
        :return: (bool) whether the control ran without error
        """
        raw_command: str = self.state_field_registry.get(
            StateField.RECEIVED_COMMAND)
        # If no command was received, don't do anything
        if raw_command == "":
            return True
        # Attempts to execute command
        try:
            # Extracts 3-letter code from raw message
            command = raw_command[raw_command.find("TJ;") + 3:raw_command.find("TJ;") + 6]
            # Executes command associated with code and logs result
            with open("log.txt", "a") as f:
                # Executes command
                if command[1:].isdigit():
                    result = self.command_registry[command[0]](int(command[1]) + float(command[2]) / 10)
                else:
                    result = self.command_registry[command]()
                # Timestamp + tab + code + tab + result of command execution + newline
                f.write(str(datetime.datetime.now().timestamp()) + "\t" + command + "\t" + result + "\n")
            return True
        except Exception:
            return False
    
    def on_start(self):
        # stay in STARTUP mode until antenna deploys
        while not self.state_field_registry.get(StateField.ANTENNA_DEPLOYED):
            self.log()
            # if 30 minutes have elapsed
            if time.time() - self.state_field_registry.get(StateField.START_TIME) > self.THIRTY_MINUTES:
                self.antenna_deployer.deploy()
                print("deployed")
                self.state_field_registry.update(StateField.ANTENNA_DEPLOYED, True)
        # Switch mode to either CHARGING or SCIENCE on exiting STARTUP, depending on battery voltage
        if self.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD:
            self.state_field_registry.update(StateField.MODE, "CHARGING")
        else:
            self.state_field_registry.update(StateField.MODE, "SCIENCE")

    def execute(self):
        """READ"""
        # Reads messages from APRS
        self.aprs.read()
        # Reads battery voltage from EPS
        battery_voltage = self.eps.telemetry["VBCROUT"]()

        """CONTROL"""
        # Runs command from APRS, if any
        self.command_interpreter()
        # Automatic mode switching
        # Enter charging mode if battery voltage < lower threshold
        if battery_voltage < self.LOWER_THRESHOLD and self.state_field_registry.get(StateField.MODE) == "SCIENCE":
            self.eps.commands["Pin Off"]("Iridium")  # Switch off iridium
            self.state_field_registry.update(StateField.MODE, "CHARGING")  # Set MODE to CHARGING
        # Enter science mode if battery has charged > upper threshold
        elif battery_voltage > self.UPPER_THRESHOLD and self.state_field_registry.get(StateField.MODE) == "CHARGING":
            self.eps.commands["Pin On"]("Iridium")  # Switch on iridium
            self.state_field_registry.update(StateField.MODE, "SCIENCE")  # Set MODE to SCIENCE
        
        """LOG"""
        self.log()  # On every iteration, run state_field_logger

    def run(self):  # Repeat main control loop forever
        # set the time that the pi first ran
        self.state_field_registry.update(StateField.START_TIME, time.time())
        if self.state_field_registry.get(StateField.MODE) == "STARTUP":  # Run only once
            self.on_start()
        while True:
            self.execute()
