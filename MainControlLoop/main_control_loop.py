import time
import threading
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.eps import EPS
#from MainControlLoop.antenna_deployer.antenna_deployer import AntennaDeployer
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer
from MainControlLoop.Drivers.iridium import Iridium
from MainControlLoop.Drivers.imu import IMU_I2C


class MainControlLoop:
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.THIRTY_MINUTES = 5  # 1800 seconds in 30 minutes
        self.LOWER_THRESHOLD = 6  # Lower battery voltage threshold for switching to CHARGING mode
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode
        self.ACKNOWLEDGEMENT = "Hello from TJ!"  # Acknowledgement message from ground station
        self.NUM_DATA_POINTS = 90  # How many measurements to take in SCIENCE mode per orbit
        self.NUM_SCIENCE_MODE_ORBITS = 3  # Number of orbits to measure in SCIENCE mode
        self.previous_time = 0  # previous time in seconds for integrating battery charge
        self.sfr = StateFieldRegistry()
        self.aprs = APRS(self.sfr)
        self.eps = EPS(self.sfr)
        self.antenna_deployer = AntennaDeployer(self.sfr)
        self.iridium = Iridium(self.sfr)
        self.imu = IMU_I2C() 
        # If battery capacity is default value, recalculate based on Vbatt
        if self.sfr.BATTERY_CAPACITY_INT == self.sfr.defaults["BATTERY_CAPACITY_INT"]:
            self.sfr.BATTERY_CAPACITY_INT = self.sfr.volt_to_charge(self.eps.telemetry["VBCROUT"]())
        # If orbital data is default, set based on current position
        if self.sfr.LAST_DAYLIGHT_ENTRY is None:
            if self.eps.sun_detected():  # If we're in sunlight
                self.sfr.LAST_DAYLIGHT_ENTRY = time.time()  # Pretend we just entered sunlight
                self.sfr.LAST_ECLIPSE_ENTRY = time.time() - 45 * 60
            else:  # If we're in eclipse
                self.sfr.LAST_DAYLIGHT_ENTRY = time.time() - 45 * 60  # Pretend we just entered eclipse
                self.sfr.LAST_ECLIPSE_ENTRY = time.time()
        self.limited_command_registry = {
            # Reads and transmits battery voltage
            "BVT": lambda: self.aprs.write("TJ;" + str(self.eps.telemetry["VBCROUT"]())),
            # Transmit total power draw of connected components
            "PWR": lambda: self.aprs.write("TJ;" + str(self.eps.total_power(3)[0])),
            # Calculate and transmit Iridium signal strength variability
            "SSV": lambda: self.aprs.write("TJ;SSV:" + str(self.sfr.signal_strength_variability())),
            # Transmit current solar panel production
            "SOL": lambda: self.aprs.write("TJ;SOL:" + str(self.eps.solar_power())),
        }
        self.command_registry = {
            "TST": lambda: self.iridium.commands["Transmit"]("TJ;Hello"),  # Test method, transmits "Hello"
            # Reads and transmits battery voltage
            "BVT": lambda: self.iridium.commands["Transmit"]("TJ;" + str(self.eps.telemetry["VBCROUT"]())),
            "CHG": self.charging_mode(),  # Enters charging mode
            "SCI": self.science_mode(self.NUM_DATA_POINTS, self.NUM_SCIENCE_MODE_ORBITS),  # Enters science mode
            "OUT": self.outreach_mode,  # Enters outreach mode
            "U": lambda value: setattr(self, "UPPER_THRESHOLD", value),  # Set upper threshold
            "L": lambda value: setattr(self, "LOWER_THRESHOLD", value),  # Set lower threshold
            # Reset power to the entire satellite (!!!!)
            "RST": lambda: [i() for i in [
                lambda: self.eps.commands["All Off"],
                lambda: time.sleep(.5),
                lambda: self.eps.commands["Bus Reset"], (["Battery", "5V", "3.3V", "12V"])
            ]],
            # Transmit proof of life through Iridium to ground station
            "IRI": lambda: self.iridium.wave(self.eps.telemetry["VBCROUT"](),
                                            self.eps.solar_power(),
                                            self.eps.total_power()),
            # Transmit total power draw of connected components
            "PWR": lambda: self.iridium.commands["Transmit"]("TJ;" + str(self.eps.total_power(3)[0])),
            # Calculate and transmit Iridium signal strength variability
            "SSV": lambda: self.iridium.commands["Transmit"]("TJ;SSV:" + str(self.sfr.signal_strength_variability())),
            # Transmit current solar panel production
            "SOL": lambda: self.iridium.commands["Transmit"]("TJ;SOL:" + str(self.eps.solar_power())),
            "TBL": lambda: self.aprs.write("TJ;" + self.imu.getTumble()) #Test method, transmits tumble value
        }
        # self.mode_devices = {  #this could be a dict containing which devices to turn on in each mode, all other devices will be turned off
        #     "STARTUP":
        #     "SCIENCE":
        #     "OUTREACH":
        #     "CHARGING":
        # }

    def integrate_charge(self):
        """
        Integrate charge in Joules
        """
        draw = self.eps.total_power(4)[0]
        gain = self.eps.solar_power()
        self.sfr.BATTERY_CAPACITY_INT -= (draw - gain) * (time.perf_counter() - self.previous_time)
        self.previous_time = time.perf_counter()

    def antenna(self):
        """
        Deploy the antenna asynchronously with the rest of the pfs
        """
        if not self.sfr.ANTENNA_DEPLOYED:
            self.log()
            # if 30 minutes have elapsed
            if time.time() - self.sfr.START_TIME > self.THIRTY_MINUTES:
                # Enable power to antenna deployer
                self.eps.commands["Pin On"]("Antenna Deployer")
                time.sleep(5)
                if self.antenna_deployer.deploy():  # Deploy antenna
                    print("deployed")
                else:
                    raise RuntimeError("ANTENNA FAILED TO DEPLOY")  # TODO: handle this somehow
                self.log()  # Log state field registry change
        self.eps.commands["Pin Off"]("Antenna Deployer")  # Disable power to antenna deployer

    def systems_check(self) -> list:
        """
        Performs a complete systems check and returns a list of component failures
        DOES NOT SWITCH ON PDMS!!! SWITCH ON PDMS BEFORE RUNNING!!!
        TODO: implement system check of antenna deployer
        TODO: account for different exceptions in .functional() and attempt to troubleshoot
        :return: list of component failures
        """
        result = []
        if not self.aprs.functional: result.append("APRS")
        if not self.iridium.functional: result.append("Iridium")
        return result


    def exec_command(self, raw_command, registry) -> bool:
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
                    result = registry[command[0]](int(command[1]) + float(command[2]) / 10)
                else:
                    result = registry[command]()
                # Timestamp + tab + code + tab + result of command execution + newline
                f.write(str(time.time()) + "\t" + command + "\t" + result + "\n")
            return True
        except Exception:
            return False

    def run(self):  # Repeat main control loop forever
        while True:  # Iterate forever
            mode = self.sfr.MODE()  # Instantiate mode object based on sfr
            while mode == self.sfr.MODE and mode.check_conditions():  # Iterate while we're supposed to be in this mode
                mode.execute_cycle()  # Execute single cycle of mode
            # command_execute
            #exits while loop if we get a message that says exit mode or if the conditions are not satisfied
            if(mode != self.sfr.defaults["MODE"]):  # if we exited the mode because we got a command, we can't call mode.switch_modes
                mode.terminate_mode()
            else:
                new_mode = mode.switch_modes()  # Switch to next mode (update sfr)
                mode.terminate_mode()
                del mode
            #mode.terminate_mode()  # Delete memory-intensive objects
