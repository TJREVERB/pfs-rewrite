import time
import pandas as pd
import numpy as np


def line_eq(a: tuple, b: tuple) -> callable:
    slope = (b[1] - a[1]) / (b[0] - a[1])
    y_int = a[1] - slope * a[0]
    return lambda x: slope * x + y_int


class StateFieldRegistry:
    LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/state_field_log.txt"
    PWR_LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/pwr_draw_log.csv"
    VOLT_ENERGY_MAP_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/volt-energy-map.csv"
    IRIDIUM_DATA_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/iridium_data.csv"

    # after how many iterations should the state field logger save the state field

    def __init__(self):
        """
        Defines all the StateFields present in the state registry
        """
        self.defaults = {
            "APRS_RECEIVED_COMMAND": "\"\"",
            "IRIDIUM_RECEIVED_COMMAND": "\"\"",
            "START_TIME": -1,
            "ANTENNA_DEPLOYED": False,
            "MODE": "\"STARTUP\"",
            "BATTERY_CAPACITY_INT": 80 * 3600,  # Integral estimate of remaining battery capacity
            "FAILURES": [],
        }
        self.type_dict = {
            "APRS_RECEIVED_COMMAND": str,
            "IRIDIUM_RECEIVED_COMMAND": str,
            "START_TIME": float,
            "ANTENNA_DEPLOYED": bool,
            "MODE": str,
            "FAILURES": list,
        }
        self.pwr_draw_log_headers = pd.read_csv(self.PWR_LOG_PATH, header=0).columns
        self.voltage_energy_map = pd.read_csv(self.VOLT_ENERGY_MAP_PATH, header=0).astype(float)
        try:
            f = open(self.LOG_PATH, "r")
            if len(f.readlines()) != len(self.defaults):
                self.load_defaults()  # Create default fields
            else:
                for line in f.readlines():
                    line = line.strip().split(':')
                    key = line[0]
                    val = line[1]
                    try:
                        # Create new field for each field in log and assign log's value
                        exec(f"self.{key} = {self.type_dict[key](val)}")
                    except:
                        self.load_defaults()
                        break
        except FileNotFoundError:
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

    def log_pwr(self, pdm_states, pwr) -> None:
        """
        Logs the power draw of every pdm
        """
        data = np.concatenate((pdm_states, pwr))  # Concatenate arrays
        np.insert(data, 0, time.time())  # Add timestamp
        df = pd.DataFrame(data, columns=self.pwr_draw_log_headers)  # Create dataframe from array
        df.to_csv(path_or_buf=self.PWR_LOG_PATH, mode="a", header=False)  # Append data to log

    def predicted_consumption(self, pdm_states: list, duration: int) -> tuple:
        """
        Uses empirical data to estimate how much energy we'd consume
        with a particular set of pdms enabled over a duration.
        Accounts for change over time in power draw of components.
        :param pdm_states: list containing states of all pdms as 1 or 0
        :param duration: time, in seconds, to remain in state
        :return: (tuple) (predicted amount of energy consumed, standard deviation, oldest data point)
        """
        df = pd.read_csv(self.PWR_LOG_PATH, header=0)
        pdms = ["0x01", "0x02", "0x03", "0x04", "0x05", "0x06", "0x07", "0x08", "0x09", "0x0A"]
        pwr_draw = 0
        total_variance = 0
        oldest_data_point = time.time()
        for i in pdms:
            if pdm_states[pdms.index(i)] == 0:  # Skip if pdm is intended to be off
                continue
            filtered_data = df.loc[df[i + "_state"] == "1"]  # Filters out data where pdm is powered off
            if len(filtered_data[i + "_state"]) == "0":  # If no data exists with pdm powered on
                # TODO: implement default power draw values for each pdm to use in calculations
                continue
            filtered_data[i + "_pwr"] = filtered_data[i + "_pwr"].astype(float)  # Convert strings to floats
            # Last 50 data points or whole dataset, whichever is smaller
            length = min([len(filtered_data[i + "_pwr"]), 50])
            # Calculates average power draw of selected data
            pwr_draw += filtered_data[i + "_pwr"][-1 * length:-1].sum() / length
            # Calculates variance of selected data
            # Variances are added when distributions are added, refer to RS2 course material
            total_variance += filtered_data.var()[i + "_pwr"]
            # Updates oldest data point
            oldest_data_point = min([oldest_data_point, filtered_data["timestamp"][-1 * length]])
        consumption = pwr_draw * duration  # pwr_draw in W, duration in s, consumption in J
        stdev = pow(total_variance, .5)  # Standard deviation from total variance
        return consumption, stdev, oldest_data_point

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
