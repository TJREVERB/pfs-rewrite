from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.lib.StateFieldRegistry.state_fields import StateField
from MainControlLoop.tests.random_number import RandomNumber
# from MainControlLoop.aprs import APRS
# from MainControlLoop.eps import EPS
# from MainControlLoop.antenna_deployer.antenna_deployer import AntennaDeployer
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
        self.LOWER_THRESHOLD = 6
        self.UPPER_THRESHOLD = 8
        self.state_field_registry: StateFieldRegistry = StateFieldRegistry()
        self.randnumber = RandomNumber(self.state_field_registry)
        self.state_field_logger = StateFieldLogger(self.state_field_registry)
        # self.aprs = APRS(self.state_field_registry)
        # self.eps = EPS(self.state_field_registry)
        # self.antenna_deployer = AntennaDeployer(self.state_field_registry)
        # self.iridium = Iridium(self.state_field_registry)
        self.command_registry = {
            "TST": (self.log, "Hello"),  # Test method
            # "BVT": (self.aprs.write, "TJ;" + str(self.eps.battery_voltage())),  # Reads and transmit battery voltage
            "CHG": (self.charging_mode, None),  # Enters charging mode
            "SCI": (self.science_mode, None),  # Enters science mode
            "U": self.set_upper,  # Set upper threshold
            "L": self.set_lower,  # Set lower threshold
            # Reset power to the entire satellite (!!!!)
            "RST": (self.reset_power, None),
            # Transmit message through Iridium to ground station
            "IRI": (self.iridium_test, None),
        }

    def iridium_test(self) -> bool:
        """
        Transmit message through iridium to ground station to test functionality
        """
        pass

    def reset_power(self) -> None:
        """
        Reset Power to the entire cubesat
        """
        self.eps.command(self.eps.command_args["All Off"])
        time.sleep(0.5)
        self.eps.bus_reset([sum([i[0] for i in self.eps.pcm_busses.values()])])

    def set_lower(self, threshold) -> None:
        """
        Set lower threshold for entering charging mode
        """
        self.LOWER_THRESHOLD = threshold

    def set_upper(self, threshold) -> None:
        """
        Set upper threshold for entering science mode
        """
        self.UPPER_THRESHOLD = threshold

    def log(self, string) -> None:
        """
        Logs string in file "log.txt"
        """
        with open("log.txt", "a") as f:
            f.write(string + "\n")

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
            command = raw_command[raw_command.find(
                "TJ;")+3:raw_command.find("TJ;")+6]
            # Executes command associated with code and logs result
            with open("log.txt", "a") as f:
                # Executes command
                if command[1:].isdigit():
                    result = self.command_registry[command[0]](
                        int(command[1]) + float(command[2]) / 10)
                else:
                    result = self.command_registry[command][0](
                        self.command_registry[command][1])
                # Timestamp + tab + code + tab + result of command execution + newline
                f.write(str(datetime.datetime.now().timestamp()) +
                        "\t" + command + "\t" + result + "\n")
            return True
        except Exception:
            return False

    def charging_mode(self) -> bool:
        """
        Enter charging mode, with Iridium off
        :return: (bool) whether or not mode switch was successful
        """
        return self.eps.component_command(self.eps.component_command_args("Pin Off"), "Iridium")

    def science_mode(self) -> bool:
        """
        Enter science mode, with Iridium on
        :return: (bool) whether or not mode switch was successful
        """
        return self.eps.component_command(self.eps.component_command_args("Pin On"), "Iridium")

    def execute(self):
        self.state_field_logger.control()  # run the state_field_logger at the beginning of each iteration

        """READ"""
        # Reads messages from APRS
        # self.aprs.read()
        # Reads battery voltage from EPS
        # battery_voltage = self.eps.battery_voltage()

        """CONTROL"""
        # Deploys antenna if 30 minute timer has passed and antenna not already deployed
        # self.antenna_deployer.control()
        # Runs command from APRS, if any
        # self.command_interpreter()
        # Automatic mode switching
        # if battery_voltage < self.LOWER_THRESHOLD:
        # Enter charging mode if battery voltage < lower threshold
        # self.charging_mode()
        # elif battery_voltage > self.UPPER_THRESHOLD:
        # Enter science mode if battery has charged > upper threshold
        # self.science_mode()
        self.randnumber.read()
        self.randnumber.control()
        self.randnumber.actuate()

    def run(self):  # Repeat main control loop forever
        # set the time that the pi first ran
        self.state_field_registry.update(StateField.START_TIME, time.time())
        while True:
            self.execute()
