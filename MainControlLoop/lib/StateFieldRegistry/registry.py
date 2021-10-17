import time


class StateFieldRegistry:
    LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/state_field_log.txt"

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

    def reset(self):
        with open(self.LOG_PATH, "w") as f:
            f.write("")
