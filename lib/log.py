import time
import os
import pandas as pd
import json
import pickle
from lib.exceptions import wrap_errors, LogicalError, HighPowerDrawError
from lib.clock import Clock


class Log:
    @wrap_errors(LogicalError)
    def __init__(self, path: str, sub):
        """
        Common routines for every log
        :param path: path to log
        :type path: str
        :param sub: subclass instance to use for common operations
        :type sub: Log
        """
        self.path = path
        self.sub = sub
        if not os.path.exists(self.path):  # If log doesn't exist on filesystem, create it
            self.sub.clear()

    @wrap_errors(LogicalError)
    def access_wrap(func: callable) -> callable:
        """
        Decorator which wraps log interactions and handles log corruption
        :param func: function to wrap
        :type func: callable
        :return: decorated function
        :rtype: callable
        """
        def wrapped(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                print(f"Error in handling log of type {type(self.sub).__name__}: {e}", file = open("pfs-output.txt", "a"))
                print("Assuming corruption, attempting to proceed by clearing log", file = open("pfs-output.txt", "a"))
                self.sub.clear()
                return func(*args, **kwargs)  # Attempt to run function again, raises error if still fails
        return wrapped

    @wrap_errors(LogicalError)
    def clear(self, func):
        """
        IMPLEMENTED IN SUBCLASSES
        """

    @wrap_errors(LogicalError)
    def write(self, data):
        """
        IMPLEMENTED IN SUBCLASSES
        """

    @wrap_errors(LogicalError)
    def read(self):
        """
        IMPLEMENTED IN SUBCLASSES
        """


class JSONLog(Log):
    @wrap_errors(LogicalError)
    def __init__(self, path: str):
        """
        Create a new json Log
        """
        super().__init__(path, self)

    @wrap_errors(LogicalError)
    def clear(self):
        if os.path.exists(self.path):  # If file exists
            os.remove(self.path)  # Delete
        open(self.path, "x").close()  # Create empty file

    @Log.access_wrap
    def write(self, data: dict):
        """
        Append one line of data to a csv log or dump to a pickle or json log
        :param data: dictionary of the form {"field": float_val}
        """
        with open(self.path, "w") as f:
            json.dump(data, f)  # Dump to file

    @Log.access_wrap
    def read(self) -> dict:
        """
        Read and return entire log
        :return: dictionary stored in log
        """
        with open(self.path, "r") as f:
            return json.load(f)  # Return dict if json


class PKLLog(Log):
    @wrap_errors(LogicalError)
    def __init__(self, path: str):
        """
        Create a new pkl Log
        """
        super().__init__(path, self)

    @wrap_errors(LogicalError)
    def clear(self):
        if os.path.exists(self.path):  # If file exists
            os.remove(self.path)  # Delete

    @Log.access_wrap
    def write(self, data: object):
        """
        Append one line of data to a csv log or dump to a pickle or json log
        :param data: object
        """
        with open(self.path, "wb") as f:
            pickle.dump(data, f)  # Dump to file

    @Log.access_wrap
    def read(self) -> object:
        """
        Read and return entire log
        :return: object stored in log
        """
        with open(self.path, "rb") as f:
            return pickle.load(f)


class CSVLog(Log):
    @wrap_errors(LogicalError)
    def __init__(self, path: str, headers: list):
        """
        Create a new csv Log
        """
        self.headers = headers
        super().__init__(path, self)
        if pd.read_csv(self.path).columns.tolist() != self.headers:
            self.clear()  # Clear log if columns don't match up (out of date log)
        
    @wrap_errors(LogicalError)
    def clear(self):
        with open(self.path, "w") as f:  # Open file
            f.write(",".join(self.headers) + "\n")  # Write headers + newline

    @Log.access_wrap
    def write(self, data: dict) -> None:
        """
        Append one line of data to a csv log or dump to a pickle or json log
        :param data: dictionary of the form {"column_name": value}
        """
        if list(data.keys()) != self.headers:  # Raise error if keys are wrong
            raise LogicalError(details="Incorrect keys for logging")
        new_row = pd.DataFrame.from_dict({k: [v] for (k, v) in data.items()})  # DataFrame from dict
        if len(df := self.read()) > 100000:  # If this log is extremely long
            # Remove first row and append to log
            df.iloc[1:].append(new_row).to_csv(self.path, mode="w", header=True, index=False)
        else:
            new_row.to_csv(self.path, mode="a", header=False, index=False)  # Append to log

    @Log.access_wrap
    def read(self) -> pd.DataFrame:
        """
        Read and return entire log
        :return: dataframe of entire log
        """
        return pd.read_csv(self.path, header=0)

    @Log.access_wrap
    def truncate(self, n):
        """
        Remove n rows from csv log
        """
        if len(df := self.read()) <= n:
            self.clear()
        else:
            df.iloc[:-n].to_csv(self.path, mode="w", header=True, index=False)


class NonWritableCSV(CSVLog):
    """
    A special log type which is read-only
    """
    @wrap_errors(LogicalError)
    def clear(self):
        """
        Do nothing because log shouldn't ever be touched
        """

    @wrap_errors(LogicalError)
    def write(self):
        """
        Do nothing because log shouldn't ever be touched
        """

    @wrap_errors(LogicalError)
    def truncate(self):
        """
        Do nothing because log shouldn't ever be touched
        """


class Logger:
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        self.sfr = sfr
        self.clocks = {
            "sfr": (Clock(0), self.sfr.dump),
            "imu": (Clock(10), self.log_imu),
            "power": (Clock(30), self.log_power_full),
            "integrate": (Clock(0), self.integrate_charge),
            "orbits": (Clock(60), self.update_orbits),
        }

    @wrap_errors(LogicalError)
    def log_pwr(self, buspower: float, pwr: list) -> None:
        """
        Logs the power draw of every pdm

        :param buspower: power draw of bus
        :type buspower: float
        :param pwr: array of power draws from each pdm, in W. [1.3421 W, 0 W, .42123 W...]
        :type pwr: list
        """
        print("Power: ", int(t := time.time()), buspower := round(buspower, 3), pwr := [round(i, 3) for i in pwr], file = open("pfs-output.txt", "a"))
        self.sfr.logs["power"].write({
            "ts0": t // 100000 * 100000, "ts1": int(t % 100000),
            "buspower": buspower,
        } | {self.sfr.PDMS[i]: pwr[i] for i in range(len(pwr))})  # "|" is a dictionary merge

    @wrap_errors(LogicalError)
    def log_solar(self, gen: list) -> None:
        """
        Logs the solar power generation from each panel (sum of A and B)
        :param gen: array of power inputs from each panel, in Watts
        :type gen: list
        """
        print("Solar: ", int(t := time.time()), gen := [round(i, 3) for i in gen], file = open("pfs-output.txt", "a"))
        self.sfr.logs["solar"].write({
            "ts0": t // 100000 * 100000, "ts1": int(t % 100000),
        } | {self.sfr.PANELS[i]: gen[i] for i in range(len(gen))})

    @wrap_errors(LogicalError)
    def log_imu(self) -> None:
        """
        Logs IMU data
        """
        if self.sfr.devices["IMU"] is None:
            return
        print("Imu: ", int(t := time.time()), tbl := [round(i, 3) for i in self.sfr.devices["IMU"].get_tumble()[0]], file = open("pfs-output.txt", "a"))
        self.sfr.logs["imu"].write({
            "ts0": t // 100000 * 100000, "ts1": int(t % 100000),
            "xgyro": tbl[0], "ygyro": tbl[1], "zgyro": tbl[2],
        })

    def log_power_full(self) -> None:
        """
        Calls log_power and log_solar
        """
        # Log total power, store values into variables
        self.log_pwr(self.sfr.eps.bus_power(), self.sfr.eps.raw_pdm_draw()[1])
        # Log solar generation, store list into variable gen
        self.log_solar(self.sfr.eps.raw_solar_gen())

    @wrap_errors(LogicalError)
    def integrate_charge(self) -> None:
        """
        Integrate battery charge in Joules
        """
        delta = (power := self.sfr.battery.charging_power()) * \
                (time.time() - self.clocks["integrate"][0].last_iteration)
        # If we're drawing/gaining absurd amounts of power
        if abs(power) > 1000: # 10W
            # Verify we're actually drawing an absurd amount of power
            total_draw = []
            for i in range(5):
                total_draw.append(self.sfr.eps.bus_power() + sum(self.sfr.eps.raw_pdm_draw()[1]))
                time.sleep(1)
            if (avg_draw := sum(total_draw) / 5) >= 10: 
                raise HighPowerDrawError(details="Average Draw: " + str(avg_draw))  # Raise exception
        else:
            # Add delta * time to BATTERY_CAPACITY_INT
            self.sfr.vars.BATTERY_CAPACITY_INT += delta

    @wrap_errors(LogicalError)
    def update_orbits(self) -> None:
        """
        Update orbits log when sun is detected
        """
        if (sun := self.sfr.sun_detected()) and self.sfr.vars.LAST_DAYLIGHT_ENTRY < self.sfr.vars.LAST_ECLIPSE_ENTRY:
            self.sfr.enter_sunlight()
        elif not sun and self.sfr.vars.LAST_DAYLIGHT_ENTRY > self.sfr.vars.LAST_ECLIPSE_ENTRY:
            self.sfr.enter_eclipse()
        self.sfr.vars.ORBITAL_PERIOD = self.sfr.analytics.calc_orbital_period()

    @wrap_errors(LogicalError)
    def log(self) -> None:
        """
        Calls :class:'lib.clock.Clock' of all logging functions
        """
        for i in self.clocks.keys():
            if self.clocks[i][0].time_elapsed():
                self.clocks[i][1]()
                self.clocks[i][0].update_time()
