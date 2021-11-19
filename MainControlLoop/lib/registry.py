import time
import pandas as pd
import numpy as np
from MainControlLoop.Drivers.eps import EPS
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.outreach import Outreach
from MainControlLoop.Mode.repeater import Repeater
from MainControlLoop.lib.analytics import Analytics


class StateFieldRegistry:
    def __init__(self):
        """
        Defines all the StateFields present in the state registry
        """
        self.LOG_PATH = "./MainControlLoop/lib/data/state_field_log.txt"
        self.PWR_LOG_PATH = "./MainControlLoop/lib/data/pwr_draw_log.csv"
        self.SOLAR_LOG_PATH = "./MainControlLoop/lib/data/solar_generation_log.csv"
        self.VOLT_ENERGY_MAP_PATH = "./MainControlLoop/lib/data/volt-energy-map.csv"
        self.ORBIT_LOG_PATH = "./MainControlLoop/lib/data/orbit_log.csv"
        self.IRIDIUM_DATA_PATH = "./MainControlLoop/lib/data/iridium_data.csv"

        self.eps = EPS(self)  # EPS never turns off
        self.analytics = Analytics(self)
        # Data for power draw and solar generation logs
        self.pwr_draw_log_headers = pd.read_csv(self.PWR_LOG_PATH, header=0).columns
        self.solar_generation_log_headers = pd.read_csv(self.SOLAR_LOG_PATH, header=0).columns
        self.voltage_energy_map = pd.read_csv(self.VOLT_ENERGY_MAP_PATH)

        self.defaults = {
            "START_TIME": "-1",
            "ANTENNA_DEPLOYED": "False",
            # Integral estimate of remaining battery capacity
            "BATTERY_CAPACITY_INT": str(self.analytics.volt_to_charge(self.eps.telemetry["VBCROUT"]())),
            "FAILURES": "[]",
            "LAST_DAYLIGHT_ENTRY": "None",
            "LAST_ECLIPSE_ENTRY": "None",
            "ORBITAL_PERIOD": "90 * 60",
            # TODO: UPDATE THIS THRESHOLD ONCE BATTERY TESTING IS DONE
            "LOWER_THRESHOLD": "60000",  # Switch to charging mode if battery capacity (J) dips below threshold
            "MODE": "Startup",  # Stores mode class, mode is instantiated in mcl
            "PRIMARY_RADIO": "\"Iridium\"",  # Primary radio to use for communications
            "SIGNAL_STRENGTH_VARIABILITY": "-1.0",  # Science mode result
            "MODE_LOCK": "False",  # Whether to lock mode switches
            "CONTACT_ESTABLISHED": "False",
            "LOCKED_DEVICES": "[]",
            "IRIDIUM_RECEIVED_COMMAND": "[]",
            "APRS_RECEIVED_COMMAND": "\"\"",
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
        with open(self.LOG_PATH, "r") as f:
            lines = f.readlines()
            # If every field in the log is in defaults and every key in defaults is in the log
            # Protects against incomplete or outdated log files
            if all([i.strip("\n ").split(":")[0] in self.defaults for i in lines]) and \
                    all([i in [j.strip("\n ").split(":")[0] for j in lines] for i in [*self.defaults]]):
                # Iterate through fields
                for line in lines:
                    line = line.strip("\n ").split(":")
                    if self.defaults[line[0]].startswith("\""):
                        line[1] = "\"" + line[1] + "\""
                    # Changed it back because this allows us to store objects other than string and int
                    exec(f"self.{line[0]} = {line[1]}")
            else:
                self.load_defaults()  # Create default fields
        self.START_TIME = time.time()  # specifically set the time; it is better if the antenna deploys late than early

    def load_defaults(self) -> None:
        """
        Loads default state field values
        """
        for key, val in self.defaults.items():
            exec(f"self.{key} = {val}")  # Create default fields

    def to_dict(self) -> dict:
        """
        Converts state fields into dictionary
        :return: dictionary of state fields
        """
        result = {}
        for i in [i for i in dir(self) if not i.startswith("__")]:  # Iterate through class variables only
            result[i] = getattr(self, i)  # Get the value of the variable from a string name
        return result

    def dump(self) -> None:
        """
        Dump values of all state fields into state_field_log
        """
        with open(self.LOG_PATH, "w") as f:
            for key, val in self.to_dict().items():
                if type(self.defaults[key]) == bool and not val:
                    f.write(f"{key}:False\n")
                else:
                    f.write(f"{key}:{val}\n")  # Save the variables in the log

    def log_pwr(self, pdm_states, pwr, t=0) -> None:
        """
        Logs the power draw of every pdm
        :param pdm_states: array of 1 and 0 representing state of all pdms. [0, 0, 1...]
        :param pwr: array of power draws from each pdm, in W. [1.3421 W, 0 W, .42123 W...]
        :param t: time to log data, defaults to time method is called
        """
        if t == 0:
            t = time.time()
        # Format data into pandas series
        data = pd.concat([pd.Series([t]), pd.Series(pdm_states), pd.Series(pwr)])
        data.to_frame().to_csv(path_or_buf=self.PWR_LOG_PATH, mode="a", header=False)  # Append data to log

    def log_solar(self, gen, t=0) -> None:
        """
        Logs the solar power generation from each panel (sum of A and B)
        :param gen: array of power inputs from each panel, in W.
        :param t: time to log data, defaults to time method is called
        """
        if t == 0:
            t = time.time()
        data = pd.concat([pd.Series([t]), pd.Series(gen)])  # Format data into pandas series
        data.to_frame().to_csv(path_or_buf=self.SOLAR_LOG_PATH, mode="a", header=False)  # Append data to log

    def enter_sunlight(self) -> None:
        """
        Update LAST_DAYLIGHT_ENTRY and log new data
        """
        self.LAST_DAYLIGHT_ENTRY = time.time()
        # Add data to dataframe
        df = pd.DataFrame([self.LAST_DAYLIGHT_ENTRY, "sunlight"], columns=["timestamp", "phase"])
        df.to_csv(self.ORBIT_LOG_PATH, mode="a", header=False)  # Append data to log

    def enter_eclipse(self) -> None:
        """
        Update LAST_ECLIPSE_ENTRY and log new data
        """
        self.LAST_ECLIPSE_ENTRY = time.time()
        # Add data to dataframe
        df = pd.DataFrame([self.LAST_DAYLIGHT_ENTRY, "eclipse"], columns=["timestamp", "phase"])
        df.to_csv(self.ORBIT_LOG_PATH, mode="a", header=False)  # Append data to log

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
        df.to_csv(path_or_buf=self.IRIDIUM_DATA_PATH, mode="a", header=False)  # Append data to log

    def reset(self):
        """
        Resets state field registry log
        """
        with open(self.LOG_PATH, "w") as f:
            f.write("")
