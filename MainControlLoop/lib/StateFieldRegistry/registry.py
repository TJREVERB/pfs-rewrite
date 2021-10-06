import time


class StateFieldRegistry:
    LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/state_field_log.txt"
    # after how many iterations should the state field logger save the state field

    def __init__(self):
        """
        Defines all the StateFields present in the state registry
        """
        defaults = {
            "RECEIVED_COMMAND": "",
            "START_TIME": -1,
            "ANTENNA_DEPLOYED": False,
            "MODE": "STARTUP",
        }
        try:
            f = open(self.LOG_PATH, "r")
            if len(f.readlines()) != len(defaults):
                for key, val in defaults.items():
                    exec(f"self.{key} = {val}")  # Create default fields
            else:
                for line in f.readlines():
                    line = line.strip().split(':')
                    key = line[0]
                    val = line[1]
                    exec(f"self.{key} = {val}")  # Create new field for each field in log and assign log's value
        except FileNotFoundError:
            for key, val in defaults.items():
                exec(f"self.{key} = {val}")  # Create default fields
        self.START_TIME = time.time()  # specifically set the time; it is better if the antenna deploys late than early

    def to_dict(self) -> dict:
        result = {}
        for i in [i for i in dir(self) if not i.startswith("__")]:  # Iterate through class variables only
            result[i] = getattr(self, i)  # Get the value of the variable from a string name
        return result

    def dump(self):
        with open(self.LOG_PATH, "w") as f:
            for key, val in self.to_dict():
                f.write(f"{key}:{val}\n")  # Save the variables in the log

    def reset(self):
        with open(self.LOG_PATH, "w") as f:
            f.write("")
