import time
import pandas as pd
import numpy as np
from MainControlLoop.Drivers.iridium import Iridium
from MainControlLoop.Drivers.eps import EPS
from MainControlLoop.Drivers.imu import IMU
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.outreach import Outreach
from MainControlLoop.Mode.repeater import Repeater



def line_eq(a: tuple, b: tuple) -> callable:
    slope = (b[1] - a[1]) / (b[0] - a[1])
    y_int = a[1] - slope * a[0]
    return lambda x: slope * x + y_int


class StateFieldRegistry:
    def __init__(self):
        """
        Defines all the StateFields present in the state registry
        """
        self.LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/state_field_log.txt"
        self.PWR_LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/pwr_draw_log.csv"
        self.SOLAR_LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/solar_generation_log.csv"
        self.VOLT_ENERGY_MAP_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/volt-energy-map.csv"
        self.ORBIT_LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/orbit_log.csv"
        self.IRIDIUM_DATA_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/iridium_data.csv"

        self.eps = EPS(self)  # EPS never turns off
        self.mode = Startup  # not object instance, just type (will be init in mcl)

        self.defaults = {
            "APRS_RECEIVED_COMMAND": "\"\"",
            "IRIDIUM_RECEIVED_COMMAND": [], # tup (command, timestamp)
            "START_TIME": -1,
            "ANTENNA_DEPLOYED": False,
            # Integral estimate of remaining battery capacity
            "BATTERY_CAPACITY_INT": self.volt_to_charge(self.eps.telemetry_request["VBCROUT"]()),
            "FAILURES": [],
            "LAST_DAYLIGHT_ENTRY": None,
            "LAST_ECLIPSE_ENTRY": None,
            "ORBITAL_PERIOD": 90 * 60,
            "PRIMARY_RADIO": "Iridium",
            "LOWER_THRESHOLD": 5 #minimum battery needed to operate, if it's lower it should switch to charging mode
        }
        self.type_dict = {
            "APRS_RECEIVED_COMMAND": str,
            "IRIDIUM_RECEIVED_COMMAND": str,
            "START_TIME": float,
            "ANTENNA_DEPLOYED": bool,
            "FAILURES": list,
            "LAST_DAYLIGHT_ENTRY": int,
            "LAST_ECLIPSE_ENTRY": int,
            "ORBITAL_PERIOD": int,
            "PRIMARY_RADIO": str
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
        self.devices = {  # None if off, object if on
            "Iridium": None,
            "APRS": None,
            "IMU": None,
            "Antenna Deployer": None,
        }

        self.serial_converters = {  # False if off, True if on
            "UART-RS232": False,  # Iridium Serial Converter
            "SPI-UART": False,  # APRS Serial Converter
            "USB-UART": False  # Alternate APRS Serial Converter
        }

        self.pwr_draw_log_headers = pd.read_csv(self.PWR_LOG_PATH, header=0).columns
        self.solar_generation_log_headers = pd.read_csv(self.SOLAR_LOG_PATH, header=0).columns
        self.voltage_energy_map = pd.read_csv(self.VOLT_ENERGY_MAP_PATH, header=0).astype(float)
        with open(self.LOG_PATH, "r") as f:
            lines = f.readlines()
            if len(lines) == len(self.defaults):
                for line in lines:
                    line = line.strip("\n ").split(":")
                    # IS THIS STILL NECESSARY WITH SETATTR?
                    if self.type_dict[line[0]] == str and line[1] == "":  # Corrects empty string for exec
                        line[1] = "\"\""
                    # This only allows for one argument for each sfr variable
                    setattr(self, line[0], self.type_dict[line[0]](line[1])) #assigns the instance variable with name line[0] to have value of everything else on that line
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
                if self.type_dict[key] == bool and not val:
                    f.write(f"{key}:\n")
                else:
                    f.write(f"{key}:{val}\n")  # Save the variables in the log

    def volt_to_charge(self, voltage: float) -> float:
        """
        Map volts to remaining battery charge in Joules
        :param voltage: battery voltage
        :return: (float) estimated charge in Joules
        """
        max_index = len(self.voltage_energy_map["voltage"]) - 1
        for i in range(len(self.voltage_energy_map["voltage"])):
            if self.voltage_energy_map["voltage"][i] > voltage:
                max_index = i
        min_index = max_index - 1
        line = line_eq((self.voltage_energy_map["voltage"][min_index], self.voltage_energy_map["energy"][min_index]),
                       (self.voltage_energy_map["voltage"][max_index], self.voltage_energy_map["energy"][max_index]))
        return line(voltage)

    def log_pwr(self, pdm_states, pwr, t=time.time()) -> None:
        """
        Logs the power draw of every pdm
        :param pdm_states: array of 1 and 0 representing state of all pdms. [0, 0, 1...]
        :param pwr: array of power draws from each pdm, in W. [1.3421 W, 0 W, .42123 W...]
        :param t: time to log data, defaults to time method is called
        """
        # Format data into pandas series
        data = pd.concat([pd.Series([t]), pd.Series(pdm_states), pd.Series(pwr)])
        data.to_frame().to_csv(path_or_buf=self.PWR_LOG_PATH, mode="a", header=False)  # Append data to log

    def log_solar(self, gen, t=time.time()) -> None:
        """
        Logs the solar power generation from each panel (sum of A and B)
        :param gen: array of power inputs from each panel, in W.
        :param t: time to log data, defaults to time method is called
        """
        data = np.array(gen)
        np.insert(data, 0, t)  # Add timestamp to data
        df = pd.DataFrame(data, columns=self.solar_generation_log_headers)  # Create dataframe from array
        df.to_csv(path_or_buf=self.SOLAR_LOG_PATH, mode="a", header=False)  # Append data to log

    def predicted_consumption(self, pdm_states: list, duration: int) -> tuple:
        """
        Uses empirical data to estimate how much energy we'd consume
        with a particular set of pdms enabled over a duration.
        Accounts for change over time in power draw of components.
        :param pdm_states: list containing states of all pdms as 1 or 0
        :param duration: time, in seconds, to remain in state
        :return: (tuple) (predicted amount of energy consumed, standard deviation)
        """
        df = pd.read_csv(self.PWR_LOG_PATH, header=0).tail(50)
        pdms = ["0x01", "0x02", "0x03", "0x04", "0x05", "0x06", "0x07", "0x08", "0x09", "0x0A"]
        pdms_on = [pdms[i] for i in range(len(pdms)) if pdm_states[i] == 1]  # Filter out pdms which are off
        # Add either the last 50 datapoints or entire dataset for each pdm which is on
        total = pd.DataFrame([df.loc[df[i + "_state"] == 1][i + "_pwr"].astype(float) for i in pdms_on]).sum(axis=1)
        return total.mean() * duration, total.stdev()

    def predicted_generation(self, duration) -> tuple:
        """
        Predict how much power will be generated by solar panels over given duration
        Assumes simulation will start at current orbital position
        :param duration: time in s to simulate for
        :return: (tuple) (estimated power generation, standard deviation of data, oldest data point)
        """
        current_time = time.time()  # Set current time
        panels = ["panel1", "panel2", "panel3", "panel4"]  # List of panels to average
        solar = pd.read_csv(self.SOLAR_LOG_PATH, header=0).tail(51)  # Read solar power log
        orbits = pd.read_csv(self.ORBIT_LOG_PATH, header=0).tail(51)  # Read orbits log
        # Calculate sunlight period
        sunlight_period = pd.Series([orbits["timestamp"].iloc[i + 1] - orbits["timestamp"].iloc[i]
                                     for i in range(orbits.shape[0] - 1)
                                     if orbits["phase"].iloc[i] == "sunlight"]).mean()
        # Calculate orbital period
        orbital_period = sunlight_period + pd.Series([orbits["timestamp"].iloc[i + 1] -
                                                      orbits["timestamp"].iloc[i] for i in range(orbits.shape[0] - 1)
                                                      if orbits["phase"].iloc[i] == "eclipse"]).mean()
        # Filter out all data points which weren't taken in sunlight
        in_sun = pd.DataFrame([solar.iloc[i] for i in range(solar.shape[0])
                               if orbits.loc[solar["timestamp"].iloc[i] -
                                             orbits["timestamp"] > 0]["phase"].iloc[-1] == "sunlight"])
        solar_gen = in_sun[panels].sum(axis=1).mean()  # Calculate average solar power generation
        # Function to calculate energy generation over a given time since entering sunlight
        energy_over_time = lambda t: int(t / orbital_period) * sunlight_period * solar_gen + \
                                     min([t % orbital_period, sunlight_period]) * solar_gen
        # Set start time for simulation
        start = current_time - orbits.loc[orbits["phase"] == "sunlight"]["timestamp"].iloc[-1]
        # Calculate and return total energy production over duration
        return energy_over_time(start + duration) - energy_over_time(start)

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

    def calc_orbital_period(self) -> int:
        """
        Calculate orbital period over last 50 orbits
        :return: average orbital period over last 50 orbits
        """
        df = pd.read_csv(self.ORBIT_LOG_PATH, header=0)  # Reads in data
        # Calculates on either last 50 points or whole dataset
        sunlight = df.loc[df["phase"] == "sunlight"]
        deltas = np.array([sunlight[i + 1] - sunlight[i] for i in range(-2, -1 * min([len(sunlight), 50]), -1)])
        eclipse = df.loc[df["phase"] == "eclipse"]
        deltas = np.concatenate((deltas,  # Appends eclipse data to deltas
                                 np.array([eclipse[i + 1] - eclipse[i] for i in range(
                                     -2, -1 * min([len(eclipse), 50]), -1)])))
        self.ORBITAL_PERIOD = np.sum(deltas) / np.shape(deltas)[0]
        return self.ORBITAL_PERIOD

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

    def signal_strength_variability(self) -> float:
        """
        Calculates and returns signal strength variability based on Iridium data
        :return: (float) standard deviation of signal strength
        """
        df = pd.read_csv(self.IRIDIUM_DATA_PATH, header=0)
        return df["signal"].std()

    def reset(self):
        """
        Resets state field registry log
        """
        with open(self.LOG_PATH, "w") as f:
            f.write("")
