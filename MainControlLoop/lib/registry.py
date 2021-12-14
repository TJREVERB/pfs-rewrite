import time
import os
import pandas as pd
import numpy as np
import pickle, json
from MainControlLoop.Drivers.eps import EPS
from MainControlLoop.Drivers.battery import Battery
from MainControlLoop.Drivers.bno055 import IMU_I2C, IMU
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.outreach import Outreach
from MainControlLoop.Mode.repeater import Repeater
from MainControlLoop.lib.analytics import Analytics
from MainControlLoop.lib.command_executor import CommandExecutor
from MainControlLoop.lib.log import Logger
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError
from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.iridium import Iridium
from MainControlLoop.Drivers.rtc import RTC
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer


class StateFieldRegistry:
    modes_list = {
        "Startup": Startup,
        "Charging": Charging,
        "Science": Science,
        "Outreach": Outreach,
        "Repeater": Repeater,
    }
    component_to_serial = {  # in sfr so command_executor can switch serial_converter of APRS if needed.
        "Iridium": "UART-RS232",
        "APRS": "SPI-UART"
    }
    components = [
        "APRS",
        "Iridium",
        "IMU",
        "Antenna Deployer",
        "EPS",
        "RTC",
        "UART-RS232",  # Iridium Serial Converter
        "SPI-UART",  # APRS Serial Converter
        "USB-UART"
    ]

    component_to_class = {  # returns class from component name
        "Iridium": Iridium,
        "APRS": APRS,
        "IMU": IMU,
        "Antenna Deployer": AntennaDeployer
    }

    @wrap_errors(LogicalError)
    def __init__(self):
        """
        Variables common across our pfs
        Vars in the "vars" object get logged
        """
        self.log_path = "./MainControlLoop/lib/data/state_field_log.pkl"
        self.readable_log_path = "./MainControlLoop/lib/data/state_field_log.json"
        self.pwr_log_path = "./MainControlLoop/lib/data/pwr_draw_log.csv"
        self.solar_log_path = "./MainControlLoop/lib/data/solar_generation_log.csv"
        self.volt_energy_map_path = "./MainControlLoop/lib/data/volt-energy-map.csv"
        self.orbit_log_path = "./MainControlLoop/lib/data/orbit_log.csv"
        self.iridium_data_path = "./MainControlLoop/lib/data/iridium_data.csv"
        self.imu_log_path = "./MainControlLoop/lib/data/imu_data.csv"  # Scuffed implementation
        self.command_log_path = "./MainControlLoop/lib/data/command_log.csv"
        self.transmission_log_path = "./MainControlLoop/lib/data/transmission_log.csv"

        self.eps = EPS(self)  # EPS never turns off
        self.battery = Battery()
        self.imu = IMU_I2C(self)
        self.rtc = RTC()
        self.analytics = Analytics(self)
        self.command_executor = CommandExecutor(self)
        self.logger = Logger(self)

        # Data for power draw and solar generation logs
        self.pwr_draw_log_headers = pd.read_csv(self.pwr_log_path, header=0).columns
        self.solar_generation_log_headers = pd.read_csv(self.solar_log_path, header=0).columns
        self.voltage_energy_map = pd.read_csv(self.volt_energy_map_path)

        self.devices = {
            "Iridium": None,
            "APRS": None,
            "Antenna Deployer": None,
        }
        self.serial_converters = {  # False if off, True if on
            "UART-RS232": False,  # Iridium Serial Converter
            "SPI-UART": False,  # APRS Serial Converter
            "USB-UART": False  # Alternate APRS Serial Converter
        }
        self.vars = self.load()
        self.vars.LAST_STARTUP = time.time()

    class Registry:
        @wrap_errors(LogicalError)
        def __init__(self, eps, analytics):
            self.ANTENNA_DEPLOYED = False
            # Integral estimate of remaining battery capacity
            self.BATTERY_CAPACITY_INT = analytics.volt_to_charge(eps.telemetry["VBCROUT"]())
            self.FAILURES = []
            self.LAST_DAYLIGHT_ENTRY = time.time() - 45 * 60 if (sun := eps.sun_detected()) else time.time()
            self.LAST_ECLIPSE_ENTRY = time.time() if sun else time.time() - 45 * 60
            self.ORBITAL_PERIOD = 90 * 60
            # Switch to charging mode if battery capacity (J) dips below threshold. 30% of max capacity
            self.LOWER_THRESHOLD = 133732.8 * 0.3
            self.UPPER_THRESHOLD = 999999  # TODO: USE REAL VALUE
            # self.MODE = Startup  # Stores mode class, mode is instantiated in mcl
            self.MODE = Science  # DEBUG!!!
            self.PRIMARY_RADIO = "Iridium"  # Primary radio to use for communications
            self.SIGNAL_STRENGTH_VARIABILITY = -1.0  # Science mode result
            self.MODE_LOCK = False  # Whether to lock mode switches
            self.LOCKED_DEVICES = {"Iridium": False, "APRS": False, "IMU": False, "Antenna Deployer": None}
            self.CONTACT_ESTABLISHED = False
            self.transmit_buffer = []
            self.command_buffer = []
            self.outreach_buffer = []
            self.START_TIME = time.time()
            self.LAST_COMMAND_RUN = time.time()
            self.LAST_MODE_SWITCH = time.time()
            self.LAST_STARTUP = 0

        @wrap_errors(LogicalError)
        def encode(self):
            return [
                int(self.ANTENNA_DEPLOYED),
                self.BATTERY_CAPACITY_INT,
                sum([2 ** StateFieldRegistry.components.index(i) for i in self.FAILURES]),
                self.LAST_DAYLIGHT_ENTRY,
                self.LAST_ECLIPSE_ENTRY,
                self.ORBITAL_PERIOD,
                self.LOWER_THRESHOLD,
                self.UPPER_THRESHOLD,
                list(StateFieldRegistry.modes_list.keys()).index(self.MODE.__name__),
                StateFieldRegistry.components.index(self.PRIMARY_RADIO),
                self.SIGNAL_STRENGTH_VARIABILITY,
                int(self.MODE_LOCK),
                sum([2 ** StateFieldRegistry.components.index(i) for i in list(self.LOCKED_DEVICES.keys())
                     if self.LOCKED_DEVICES[i]]),
                int(self.CONTACT_ESTABLISHED),
                self.START_TIME,
                self.LAST_COMMAND_RUN,
                self.LAST_MODE_SWITCH,
            ]

        @wrap_errors(LogicalError)
        def to_dict(self):
            """
            Converts vars to dictionary with encoded values
            """
            encoded = self.encode()
            result = {}
            for i in vars(self):
                if not i.startswith("__") and i.isupper():
                    result[i] = encoded[0]  # encoded.pop(0)
            return result

    @wrap_errors(LogicalError)
    def load(self) -> Registry:
        """
        Load sfr fields from log
        :return: (Registry) loaded registry
        """
        defaults = self.Registry(self.eps, self.analytics)
        return defaults  # DEBUG
        try:
            with open(self.log_path, "rb") as f:
                fields = pickle.load(f)
            if list(fields.to_dict().keys()) == list(defaults.to_dict().keys()):
                print("Loading sfr from log...")
                return fields
            print("Invalid log, loading default sfr...")
            return defaults
        except Exception as e:
            print("Unknown error, loading default sfr...")
            print(e)
            return defaults

    @wrap_errors(LogicalError)
    def dump(self) -> None:
        """
        Dump values of all state fields into state_field_log and readable log
        """
        with open(self.log_path, "wb") as f:
            pickle.dump(self.vars, f)
        with open(self.readable_log_path, "w") as f:
            json.dump(self.vars.to_dict(), f)

    @wrap_errors(LogicalError)
    def enter_sunlight(self) -> None:
        """
        Update LAST_DAYLIGHT_ENTRY and log new data
        """
        self.vars.LAST_DAYLIGHT_ENTRY = time.time()
        # Add data to dataframe
        df = pd.DataFrame(data={"daylight": self.vars.LAST_DAYLIGHT_ENTRY}, columns=["timestamp", "phase"])
        df.to_csv(self.orbit_log_path, mode="a", header=False)  # Append data to log

    @wrap_errors(LogicalError)
    def enter_eclipse(self) -> None:
        """
        Update LAST_ECLIPSE_ENTRY and log new data
        """
        self.vars.LAST_ECLIPSE_ENTRY = time.time()
        # Add data to dataframe
        df = pd.DataFrame(data={"eclipse": self.vars.LAST_ECLIPSE_ENTRY}, columns=["timestamp", "phase"])
        df.to_csv(self.orbit_log_path, mode="a", header=False)  # Append data to log

    @wrap_errors(LogicalError)
    def log_iridium(self, location, signal):
        """
        Logs iridium data
        :param location: current geolocation
        :param signal: iridium signal strength
        :param t: time to log, defaults to time method is called
        """
        with open(self.iridium_data_path, "a") as f:
            f.write(str(time.time()) + "," + ",".join(map(str, location)) + "," + str(signal) + "\n")

    @wrap_errors(LogicalError)
    def recent_power(self) -> list:
        """
        Returns list of buspower and power draws for all pdms
        :return: (list) [buspower, 0x01, 0x02... 0x0A]
        """
        if len(df := pd.read_csv(self.pwr_log_path, header=0)) == 0:
            return [self.eps.bus_power()] + self.eps.raw_pdm_draw()[1]
        cols = ["buspower"] + [f"0x0{str(hex(i))[2:].upper()}_pwr" for i in range(1, 11)]
        return df[cols].iloc[-1].tolist()

    @wrap_errors(LogicalError)
    def recent_gen(self) -> list:
        """
        Returns list of input power from all bcrs
        :return: (list) [bcr1, bcr2, bcr3]
        """
        if len(df := pd.read_csv(self.solar_log_path, header=0)) == 0:
            return self.eps.raw_solar_gen()
        cols = ["bcr1", "bcr2", "bcr3"]
        return df[cols].iloc[-1].tolist()

    @wrap_errors(LogicalError)
    def clear_logs(self):
        """
        WARNING: CLEARS ALL LOGGED DATA, ONLY USE FOR TESTING/DEBUG
        """
        for f in [self.pwr_log_path, self.solar_log_path, self.orbit_log_path]:
            headers = pd.read_csv(f, header=0).columns
            os.remove(f)
            with open(f, "w") as new:
                new.write(",".join(list(headers)) + "\n")
        if os.path.exists(self.log_path):
            os.remove(self.log_path)
        print("Logs cleared")

    @wrap_errors(LogicalError)
    def reset(self):
        """
        Resets state field registry log
        """
        with open(self.log_path, "w") as f:
            f.write("")
