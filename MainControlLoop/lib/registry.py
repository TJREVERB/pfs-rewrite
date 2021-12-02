import time
import pandas as pd
import numpy as np
import pickle
import json
from MainControlLoop.Drivers.eps import EPS
from MainControlLoop.Drivers.bno055 import IMU_I2C
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.outreach import Outreach
from MainControlLoop.Mode.repeater import Repeater
from MainControlLoop.lib.analytics import Analytics
from MainControlLoop.lib.command_executor import CommandExecutor
from MainControlLoop.lib.log import Logger

class StateFieldRegistry:
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

        self.eps = EPS(self)  # EPS never turns off
        self.imu = IMU_I2C(self)
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
        self.component_to_serial = {  # in sfr so command_executor can switch serial_converter of APRS if needed.
            "Iridium": "UART-RS232",
            "APRS": "SPI-UART"
        }
        self.modes_list = {
            "Startup": Startup,
            "Charging": Charging,
            "Science": Science,
            "Outreach": Outreach,
            "Repeater": Repeater,
        }
        self.serial_converters = {  # False if off, True if on
            "UART-RS232": False,  # Iridium Serial Converter
            "SPI-UART": False,  # APRS Serial Converter
            "USB-UART": False  # Alternate APRS Serial Converter
        }
        self.vars = self.load()
    
    class Registry:
        def __init__(self, eps, analytics):
            self.START_TIME = -1
            self.ANTENNA_DEPLOYED = False
            # Integral estimate of remaining battery capacity
            self.BATTERY_CAPACITY_INT = analytics.volt_to_charge(eps.telemetry["VBCROUT"]())
            self.FAILURES = []
            sun = eps.sun_detected()
            self.LAST_DAYLIGHT_ENTRY = [time.time() - 45 * 60, time.time()][sun]
            self.LAST_ECLIPSE_ENTRY = [time.time(), time.time() - 45 * 60][sun]
            self.ORBITAL_PERIOD = 90 * 60
            # TODO: UPDATE THIS THRESHOLD ONCE BATTERY TESTING IS DONE
            self.LOWER_THRESHOLD = 60000  # Switch to charging mode if battery capacity (J) dips below threshold
            self.MODE = Startup  # Stores mode class, mode is instantiated in mcl
            self.PRIMARY_RADIO = "Iridium"  # Primary radio to use for communications
            self.SIGNAL_STRENGTH_VARIABILITY = -1.0  # Science mode result
            self.MODE_LOCK = False  # Whether to lock mode switches
            self.LOCKED_DEVICES = {"Iridium": False, "APRS": False, "IMU": False, "Antenna Deployer": None}
            self.CONTACT_ESTABLISHED = False
            self.command_buffer = []  # tuple (3 char command str, argument, message number: int)
            self.outreach_buffer = []
            self.START_TIME = time.time()
    
    def load(self) -> Registry:
        defaults = self.Registry(self.eps, self.analytics)
        try:
            with open(self.log_path, "rb") as f:
                vars = pickle.load(f)
            # If all variable names are the same and all types of values are the same
            # Checks if log is valid and up-to-date
            if not [[i[0], type(i[1])] for i in vars.__dict__.items()] == \
                   [[i[0], type(i[1])] for i in defaults.__dict__.items()]:
                print("Invalid log, loading default sfr...")
                vars = defaults
            print("Loading sfr from log...")
        except Exception as e:
            print("Unknown error, loading default sfr...")
            print(e)
            vars = defaults
        return vars

    def dump(self) -> None:
        """
        Dump values of all state fields into state_field_log
        """
        with open(self.log_path, "wb") as f:
            pickle.dump(self.vars, f)
        with open(self.readable_log_path, "w") as f:
            json.dump(self.vars.__dict__, f)

    def enter_sunlight(self) -> None:
        """
        Update LAST_DAYLIGHT_ENTRY and log new data
        """
        self.LAST_DAYLIGHT_ENTRY = time.time()
        # Add data to dataframe
        df = pd.DataFrame([self.LAST_DAYLIGHT_ENTRY, "sunlight"], columns=["timestamp", "phase"])
        df.to_csv(self.orbit_log_path, mode="a", header=False)  # Append data to log

    def enter_eclipse(self) -> None:
        """
        Update LAST_ECLIPSE_ENTRY and log new data
        """
        self.LAST_ECLIPSE_ENTRY = time.time()
        # Add data to dataframe
        df = pd.DataFrame([self.LAST_DAYLIGHT_ENTRY, "eclipse"], columns=["timestamp", "phase"])
        df.to_csv(self.orbit_log_path, mode="a", header=False)  # Append data to log

    def log_iridium(self, location, signal, t=time.time()):
        """
        Logs iridium data
        :param location: current geolocation
        :param signal: iridium signal strength
        :param t: time to log, defaults to time method is called
        """
        data = np.array(t, location, signal)  # Concatenate arrays
        np.insert(data, 0, time.time())  # Add timestamp
        df = pd.DataFrame(data, columns=["timestamp", "geolocation", "signal"])  # Create dataframe from array
        df.to_csv(path_or_buf=self.iridium_data_path, mode="a", header=False)  # Append data to log
    
    def recent_power(self) -> list:
        """
        Returns list of buspower and power draws for all pdms
        :return: (list) [buspower, 0x01, 0x02... 0x0A]
        """
        return list(pd.read_csv(self.pwr_log_path, header=0)
            [["buspower"] + [f"0x0{str(hex(i))}_pwr" for i in range(1, 11)]][-1])
    
    def recent_gen(self) -> list:
        """
        Returns list of input power from all bcrs
        :return: (list) [bcr1, bcr2, bcr3]
        """
        return list(pd.read_csv(self.solar_log_path, header=0)["bcr1", "bcr2", "bcr3"][-1])
    
    def clear_logs(self):
        """
        WARNING: CLEARS ALL LOGGED DATA, ONLY USE FOR TESTING/DEBUG
        """
        for f in [self.pwr_log_path, self.solar_log_path, self.orbit_log_path, self.command_log_path]:
            headers = pd.read_csv(f, header=0).columns
            os.remove(f)
            with open(f, "w") as new:
                new.write(list(headers).join(","))
        os.remove(self.log_path)
        print("Logs cleared")

    def reset(self):
        """
        Resets state field registry log
        """
        with open(self.log_path, "w") as f:
            f.write("")
