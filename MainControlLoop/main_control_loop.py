from functools import partial
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.aprs import APRS
from MainControlLoop.eps import EPS
from MainControlLoop.antenna_deployer.antenna_deployer import AntennaDeployer
from MainControlLoop.iridium import Iridium
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
        self.sfr = StateFieldRegistry()
        self.aprs = APRS(self.sfr)
        self.eps = EPS(self.sfr)
        self.antenna_deployer = AntennaDeployer(self.sfr)
        #self.iridium = Iridium(self.sfr)
        self.command_registry = {
            #"TST": partial([i() for i in [[partial(f.write, "Hello"), partial(f.close)]
            #                              for f in [open("log.txt", "a")]][0]]),  # Test method, logs "Hello"
            "BVT": partial(self.aprs.write, "TJ;" + str(self.eps.telemetry["VBCROUT"]())),
            # Reads and transmits battery voltage
            "CHG": self.charging_mode,  # Enters charging mode
            "SCI": self.science_mode,  # Enters science mode
            "U": partial(setattr, obj=self, name="UPPER_THRESHOLD"),  # Set upper threshold
            "L": partial(setattr, obj=self, name="LOWER_THRESHOLD"),  # Set lower threshold
            "RST": lambda: [i() for i in [
                lambda: self.eps.commands["All Off"],
                lambda: time.sleep(.5),
                lambda: self.eps.commands["Bus Reset"], (["Battery", "5V", "3.3V", "12V"])
            ]],  # Reset power to the entire satellite (!!!!)
            "IRI": self.iridium.wave,  
            # Transmit message through Iridium to ground station
            "PWR": partial(self.aprs.write, "TJ;" + str(self.eps.total_power())),
            # Transmit total power draw of connected components
        }
    
    def charging_mode(self):
        """
        Enter CHARGING mode, switch off Iridium
        """
        #del self.iridium  # Disconnect serial port
        self.eps.commands["Pin Off"]("Iridium")  # Switch off iridium
        self.sfr.MODE = "CHARGING"  # Set MODE to CHARGING
    
    def science_mode(self):
        """
        Enter SCIENCE mode, switch on Iridium
        """
        self.eps.commands["Pin On"]("Iridium")  # Switch on iridium
        #time.sleep(5)
        #self.iridium = Iridium(self.sfr)  # Reconnect serial port
        self.sfr.MODE = "SCIENCE"  # Set MODE to SCIENCE
    
    def log(self):
        # run the state_field_logger; commented out during testing
        self.sfr.dump()
        return

    def command_interpreter(self) -> bool:
        """
        This will take whatever is read, parse it, and then execute it
        :return: (bool) whether the control ran without error
        """
        raw_command: str = self.sfr.RECEIVED_COMMAND
        self.sfr.RECEIVED_COMMAND = ""
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
                f.write(str(time.time()) + "\t" + command + "\t" + result + "\n")
            return True
        except Exception:
            return False
    
    def on_start(self):
        """
        Runs as soon as deployment switch is depressed.
        Only runs once.
        """
        # Switch off all PDMs
        self.eps.commands["All Off"]()
        # stay in STARTUP mode until antenna deploys
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
        self.eps.commands["Pin On"]("APRS")  # Enable power to APRS
        # Wait for battery to charge to upper threshold
        print(self.aprs.functional())
        while self.eps.telemetry["VBCROUT"]() < self.UPPER_THRESHOLD:
            print("test")
            self.aprs.read()  # Listen for and execute ground station commands
            self.command_interpreter()
        self.sfr.MODE = "IOC"  # Enter IOC mode to test initial functionality
        self.log()  # Log mode switch
    
    def ioc(self):
        """
        Code to test initial operational capability of satellite.
        """
        self.eps.commands["Pin On"]("Iridium")  # Switch on Iridium
        self.eps.commands["Pin On"]("Iridium Serial Converter")  # Switch on Iridium serial converter
        time.sleep(5)
        print("iridium.functional: " + str(self.iridium.functional()))  # Debugging
        self.iridium.wave()  # Test Iridium
        # Switch mode to either CHARGING or SCIENCE on exiting STARTUP, depending on battery voltage
        if self.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD:
            self.charging_mode()
        else:
            self.science_mode()

    def execute(self):
        """READ"""
        # Reads messages from APRS
        self.aprs.read()
        # Reads battery voltage from EPS
        battery_voltage = self.eps.telemetry["VBCROUT"]()
        print(battery_voltage)

        """CONTROL"""
        # Runs command from APRS, if any
        self.command_interpreter()
        # Automatic mode switching
        # Enter charging mode if battery voltage < lower threshold
        if battery_voltage < self.LOWER_THRESHOLD and self.sfr.MODE == "SCIENCE":
            self.charging_mode()
        # Enter science mode if battery has charged > upper threshold
        elif battery_voltage > self.UPPER_THRESHOLD and self.sfr.MODE == "CHARGING":
            self.science_mode()
        
        """LOG"""
        self.log()  # On every iteration, run sfr.dump

    def run(self):  # Repeat main control loop forever
        # set the time that the pi first ran
        self.sfr.START_TIME = time.time()
        try:
            if self.sfr.MODE == "STARTUP":  # Run only once
                self.on_start()
            if self.sfr.MODE == "IOC":  # Run only once, initial operations test
                self.ioc()
            if self.sfr.MODE == "CHARGING":
                self.charging_mode()
            if self.sfr.MODE == "SCIENCE":
                self.science_mode()
            while True:
                self.execute()
        except KeyboardInterrupt:
            print("quitting...")
            self.sfr.reset()
            exit(0)
