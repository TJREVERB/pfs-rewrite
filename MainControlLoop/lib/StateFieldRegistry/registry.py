import time
import pandas as pd
import numpy as np


class StateFieldRegistry:
    LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/state_field_log.txt"
    PWR_LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/pwr_draw_log.csv"

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
        }
        self.type_dict = {
            "APRS_RECEIVED_COMMAND": str,
            "IRIDIUM_RECEIVED_COMMAND": str,
            "START_TIME": float,
            "ANTENNA_DEPLOYED": bool,
            "MODE": str,
            "BATTERY_CAPACITY_INT": float,
        }
        self.pwr_draw_log_headers = pd.read_csv(self.PWR_LOG_PATH).columns
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

    def load_defaults(self):
        for key, val in self.defaults.items():
            exec(f"self.{key} = {val}")  # Create default fields

    def to_dict(self) -> dict:
        result = {}
        for i in [i for i in dir(self) if not i.startswith("__")]:  # Iterate through class variables only
            result[i] = getattr(self, i)  # Get the value of the variable from a string name
        return result

    def dump(self):
        with open(self.LOG_PATH, "w") as f:
            for key, val in self.to_dict().items():
                if self.type_dict[key] == bool and not val:
                    f.write(f"{key}:\n")
                else:
                    f.write(f"{key}:{val}\n")  # Save the variables in the log

    def volt_to_charge(self, voltage):
        """
        Map volts to remaining battery capacity in Joules
        """
        return 80*3600  # placeholder

    def log_pwr(self, pdm_states, pwr):
        """
        Logs the power draw of every pdm
        """
        data = np.stack(np.array(pdm_states, pwr))
        df = pd.DataFrame(data, columns=self.pwr_draw_log_headers)
        df.to_csv(path_or_buf=self.PWR_LOG_PATH, mode="a", header=False)

    def reset(self):
        with open(self.LOG_PATH, "w") as f:
            f.write("")
