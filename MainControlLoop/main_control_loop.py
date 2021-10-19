from functools import partial
import time
import threading
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.aprs import APRS
from MainControlLoop.eps import EPS
from MainControlLoop.antenna_deployer.antenna_deployer import AntennaDeployer
from MainControlLoop.iridium import Iridium


class MainControlLoop:
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.THIRTY_MINUTES = 5  # 1800 seconds in 30 minutes
        self.LOWER_THRESHOLD = 6  # Lower battery voltage threshold for switching to CHARGING mode
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode
        self.ACKNOWLEDGEMENT = "Hello from TJ!"
        self.previous_time = 0  # previous time in seconds for integrating battery charge
        self.sfr = StateFieldRegistry()
        self.aprs = APRS(self.sfr)
        self.eps = EPS(self.sfr)
        self.antenna_deployer = AntennaDeployer(self.sfr)
        self.iridium = Iridium(self.sfr)
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
            "BVT": lambda: self.aprs.write("TJ;" + str(self.eps.telemetry["VBCROUT"]())),
            # Reads and transmits battery voltage
            "PWR": lambda: self.aprs.write("TJ;" + str(self.eps.total_power(3)[0])),
            # Transmit total power draw of connected components
        }
        self.command_registry = {
            # "TST": partial(self.aprs.write, "TJ;Hello"),  # Test method, transmits "Hello"
            "TST": lambda: self.aprs.write("TJ;Hello"),
            # "BVT": partial(self.aprs.write, "TJ;" + str(self.eps.telemetry["VBCROUT"]())),
            "BVT": lambda: self.aprs.write("TJ;" + str(self.eps.telemetry["VBCROUT"]())),
            # Reads and transmits battery voltage
            # "CHG": self.charging_mode(),  # Enters charging mode
            # "SCI": self.science_mode(),  # Enters science mode
            # "OUT": self.outreach_mode,  # Enters outreach mode
            "U": lambda value: setattr(self, "UPPER_THRESHOLD", value),  # Set upper threshold
            "L": lambda value: setattr(self, "LOWER_THRESHOLD", value),  # Set lower threshold
            "RST": lambda: [i() for i in [
                lambda: self.eps.commands["All Off"],
                lambda: time.sleep(.5),
                lambda: self.eps.commands["Bus Reset"], (["Battery", "5V", "3.3V", "12V"])
            ]],  # Reset power to the entire satellite (!!!!)
            "IRI": self.iridium.wave,
            # Transmit message through Iridium to ground station
            "PWR": lambda: self.aprs.write("TJ;" + str(self.eps.total_power(3)[0])),
            # Transmit total power draw of connected components
        }

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
        while not self.sfr.ANTENNA_DEPLOYED:
            self.log()
            # if 30 minutes have elapsed
            if time.time() - self.sfr.START_TIME > self.THIRTY_MINUTES:
                # Enable power to antenna deployer
                self.eps.commands["Pin On"]("Antenna Deployer")
                time.sleep(5)
                self.antenna_deployer.deploy()  # Deploy antenna
                print("deployed")
                self.sfr.ANTENNA_DEPLOYED = True
                self.log()  # Log state field registry change
        self.eps.commands["Pin Off"]("Antenna Deployer")  # Disable power to antenna deployer

    def systems_check(self) -> list:
        """
        Performs a complete systems check and returns a list of component failures
        DOES NOT SWITCH ON PDMS!!! SWITCH ON PDMS BEFORE RUNNING!!!
        TODO: implement system check of antenna deployer
        :return: list of component failures
        """
        result = []
        if not self.aprs.functional: result.append("APRS")
        if not self.iridium.functional: result.append("Iridium")
        return result

    def startup_mode(self):
        """
        Runs as soon as deployment switch is depressed.
        Only runs once.
        """
        # Systems check
        self.eps.commands["All On"]()
        self.sfr.FAILURES = self.systems_check()
        # Switch off all PDMs
        self.eps.commands["All Off"]()
        # Consider changing thread to asyncio later
        threading.Thread(target=self.antenna).start()  # Start timer to deploy antenna
        self.eps.commands["Pin On"]("Iridium")  # Switch on Iridium
        self.eps.commands["Pin On"]("UART-RS232")
        # Fields for iridium.wave()
        solar_generation = self.eps.solar_power()
        battery_voltage = self.eps.commands["VBCROUT"]()
        current_output = self.eps.total_power(4)
        last_contact_attempt = time.time()
        # Attempt to establish contact with ground
        self.iridium.wave(battery_voltage, solar_generation, current_output)
        # Repeat until acknowledgement is received
        while not self.sfr.IRIDIUM_RECEIVED_COMMAND.contains(self.ACKNOWLEDGEMENT):
            if self.eps.commands["VBCROUT"] < self.LOWER_THRESHOLD:  # If battery is drained
                self.charging_mode()  # Recharge battery and then continue trying to establish contact
            # Attempt first contact every 2 minutes
            if time.time() - last_contact_attempt >= 60 * 2:
                # Attempt to establish contact with ground
                solar_generation = self.eps.solar_power()
                battery_voltage = self.eps.commands["VBCROUT"]()
                current_output = self.eps.total_power(4)
                last_contact_attempt = time.time()
                self.iridium.wave(battery_voltage, solar_generation, current_output)
            self.iridium.listen()  # Listen for ground station response
        self.sfr.MODE = "SCIENCE"  # Enter SCIENCE mode to do research
        self.log()  # Log mode switch

    def science_mode(self):
        """
        Code to test initial operational capability of satellite.
        """
        self.eps.commands["Pin On"]("Iridium")  # Switch on Iridium
        self.eps.commands["Pin On"]("UART-RS232")  # Switch on Iridium serial converter
        # TODO: implement code to test Iridium over the orbit
        # Switch mode to either CHARGING or SCIENCE on exiting STARTUP, depending on battery voltage
        if self.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD:
            self.charging_mode()
        else:
            self.outreach_mode()

    def outreach_mode(self):
        """
        Satellite's control flow in OUTREACH mode.
        Enters OUTREACH mode, serves as outreach platform until charge depletes to LOWER_THRESHOLD
        Iridium and APRS are always on.
        """
        self.sfr.MODE = "OUTREACH"
        self.eps.commands["All On"]()
        while self.eps.telemetry["VBCROUT"]() > self.LOWER_THRESHOLD:
            self.iridium.listen()
            self.aprs.read()
            self.command_interpreter()
            self.log()
        self.sfr.MODE = "CHARGING"
        self.log()

    def charging_mode(self):
        """
        Satellite's control flow in CHARGING mode.
        Enters CHARGING mode, charges until UPPER_THRESHOLD, returns to initial mode.
        Iridium powered on when in sunlight.
        """
        initial_mode = self.sfr.MODE
        self.sfr.MODE = "CHARGING"
        self.eps.commands["Pin Off"]("APRS")  # Powers off APRS
        self.eps.commands["Pin Off"]("SPI-UART")
        self.eps.commands["Pin Off"]("USB-UART")
        while self.eps.telemetry["VBCROUT"] < self.UPPER_THRESHOLD:
            # Iridium power controls
            if self.eps.sun_detected():
                self.eps.commands["Pin On"]("Iridium")  # Switches on Iridium if in sunlight
                self.eps.commands["Pin On"]("UART-RS232")
                self.iridium.listen()  # Read and store received message
                self.command_interpreter()  # Execute command (if any)
            else:
                self.eps.commands["Pin Off"]("Iridium")  # Switches off Iridium if in eclipse
                self.eps.commands["Pin Off"]("UART-RS232")
            self.log()  # Log changes
        self.sfr.MODE = initial_mode
        self.log()

    def log(self):
        # run the state_field_logger; commented out during testing
        self.sfr.dump()
        return

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

    def command_interpreter(self) -> bool:
        """
        This will take whatever is read, parse it, and then execute it
        :return: (bool) whether the control ran without error
        """
        raw_command: str = self.sfr.IRIDIUM_RECEIVED_COMMAND
        raw_limited_command: str = self.sfr.APRS_RECEIVED_COMMAND
        self.sfr.IRIDIUM_RECEIVED_COMMAND = ""
        self.sfr.APRS_RECEIVED_COMMAND = ""
        return self.exec_command(raw_command, self.command_registry) and \
               self.exec_command(raw_limited_command, self.limited_command_registry)
        # if one of them is False, return False

    def execute(self):
        # Automatic mode switching
        battery_voltage = self.eps.telemetry["VBCROUT"]()  # Reads battery voltage from EPS
        # Enter charging mode if battery voltage < lower threshold
        if battery_voltage < self.LOWER_THRESHOLD and self.sfr.MODE == "OUTREACH":
            self.sfr.MODE = "CHARGING"  # Set MODE to CHARGING
        # Enter outreach mode if battery has charged > upper threshold
        elif battery_voltage > self.UPPER_THRESHOLD and self.sfr.MODE == "CHARGING":
            self.sfr.MODE = "OUTREACH"  # Set MODE to OUTREACH

        # Orbit Updates
        if self.eps.sun_detected():
            if self.sfr.LAST_DAYLIGHT_ENTRY < self.sfr.LAST_ECLIPSE_ENTRY:
                self.sfr.enter_sunlight()
        elif self.sfr.LAST_ECLIPSE_ENTRY < self.sfr.LAST_DAYLIGHT_ENTRY:
            self.sfr.enter_eclipse()

        # Control satellite depending on mode
        if self.sfr.MODE == "STARTUP":  # Run only once
            self.startup_mode()
        if self.sfr.MODE == "SCIENCE":
            self.science_mode()
        if self.sfr.MODE == "CHARGING":
            self.charging_mode()
        if self.sfr.MODE == "OUTREACH":
            self.outreach_mode()
        self.log()  # On every iteration, run sfr.dump to log changes
        self.integrate_charge()  # Integrate charge

    def run(self):  # Repeat main control loop forever
        # set the time that the pi first ran
        # iridium_msg = self.iridium.listen()
        # print(iridium_msg)
        self.sfr.START_TIME = time.time()
        print("Run started")
        try:
            while True:
                # self.execute()
                iridium_msg = self.iridium.listen()
                print(iridium_msg)
                time.sleep(1)
        except KeyboardInterrupt:
            print("quitting...")
            self.sfr.reset()
            exit(0)
