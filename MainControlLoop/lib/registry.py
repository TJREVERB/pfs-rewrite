import time
import pandas as pd
import numpy as np
import json
import pickle
from MainControlLoop.Drivers.eps import EPS
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.outreach import Outreach
from MainControlLoop.Mode.repeater import Repeater
from MainControlLoop.lib.analytics import Analytics
from MainControlLoop.command_executor import CommandExecutor


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
        self.analytics = Analytics(self)
        self.command_executor = CommandExecutor(self)
        
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
            self.IRIDIUM_RECEIVED_COMMAND = []
            self.APRS_RECEIVED_COMMAND = []
            self.START_TIME = time.time()
    
    def load(self) -> Registry:
        defaults = self.Registry(self.eps, self.analytics)
        try:
            with open(self.log_path, "rb") as f:
                vars = pickle.load(f)
            # If all variable names are the same and all types of values are the same
            # Checks if log is valid and up-to-date
            if not [tuple(i[0], type(i[1])) for i in self.vars.__dict__.items()] == \
                   [tuple(i[0], type(i[1])) for i in defaults.__dict__.items()]:
                print("Invalid log, loading default sfr...")
                vars = defaults
            print("Loading sfr from log...")
        except Exception:
            print("Unknown error, loading default sfr...")
            vars = defaults
        return vars

    def dump(self) -> None:
        """
        Dump values of all state fields into state_field_log
        """
        pickle.dump(self.vars, open(self.log_path, "wb"))
        json.dump(self.vars.__dict__, open(self.readable_log_path, "w"))

    def log_pwr(self, pdm_states, pwr, t=0) -> None:
        """
        Logs the power draw of every pdm
        :param pdm_states: array of 1 and 0 representing state of all pdms. [0, 0, 1...]
        :param pwr: array of power draws from each pdm, in W. [1.3421 W, 0 W, .42123 W...]
        :param t: time to log data, defaults to time method is called
        """
        if t == 0:
            t = time.time()
        print("Power: ", t, pdm_states, pwr)
        # Format data into pandas series
        data = pd.concat([pd.Series([t]), pd.Series(pdm_states), pd.Series(pwr)])
        data.to_frame().to_csv(path_or_buf=self.pwr_log_path, mode="a", header=False)  # Append data to log

    def log_solar(self, gen, t=0) -> None:
        """
        Logs the solar power generation from each panel (sum of A and B)
        :param gen: array of power inputs from each panel, in W.
        :param t: time to log data, defaults to time method is called
        """
        if t == 0:
            t = time.time()
        print("Solar: ", t, gen)
        data = pd.concat([pd.Series([t]), pd.Series(gen)])  # Format data into pandas series
        data.to_frame().to_csv(path_or_buf=self.solar_log_path, mode="a", header=False)  # Append data to log

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

    def reset(self):
        """
        Resets state field registry log
        """
        with open(self.log_path, "w") as f:
            f.write("")
