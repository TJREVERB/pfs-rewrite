import time, datetime
import threading
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.eps import EPS
#from MainControlLoop.antenna_deployer.antenna_deployer import AntennaDeployer
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer
from MainControlLoop.Drivers.iridium import Iridium
#from MainControlLoop.Drivers.lsm9ds1 import IMU, IMU_I2C
from MainControlLoop.Drivers.bno055 import IMU, IMU_I2C


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
        # If battery capacity is default value, recalculate based on Vbatt
        if self.sfr.BATTERY_CAPACITY_INT == self.sfr.BATTERY_CAPACITY_INT:
            self.sfr.BATTERY_CAPACITY_INT = self.sfr.volt_to_charge(self.eps.telemetry["VBCROUT"]())
        # If orbital data is default, set based on current position
        if self.sfr.LAST_DAYLIGHT_ENTRY is None:
            if self.sfr.eps.sun_detected():  # If we're in sunlight
                self.sfr.LAST_DAYLIGHT_ENTRY = time.time()  # Pretend we just entered sunlight
                self.sfr.LAST_ECLIPSE_ENTRY = time.time() - 45 * 60
            else:  # If we're in eclipse
                self.sfr.LAST_DAYLIGHT_ENTRY = time.time() - 45 * 60  # Pretend we just entered eclipse
                self.sfr.LAST_ECLIPSE_ENTRY = time.time()

    def run(self):  # Repeat main control loop forever
        current_time = time.time()
        while True:  # Iterate forever
            self.sfr.mode.start()  #TODO implement update conditions
            while self.sfr.mode.check_conditions():  # Iterate while we're supposed to be in this mode
                if current_time + 1 <= time.time():  # if waited 1 second or mode, update conditions dict in mode
                    self.sfr.mode.update_conditions()
                self.sfr.mode.execute_cycle()  # Execute single cycle of mode
                if self.sfr.manual_mode_override:  # if mode was changed via manual command
                    break
            if self.sfr.manual_mode_override:  # new manually changed mode will already be stored in sfr.mode
                self.sfr.manual_mode_override = False
            else:
                self.sfr.mode.terminate_mode()  # terminates current old mode
                self.sfr.mode = self.sfr.mode.switch_modes()  # decides which mode to switch to; returns mode object

