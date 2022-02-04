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
        :param sub: log subclass whose clear function to use
        """
        self.path = path
        if not os.path.exists(self.path):  # If log doesn't exist on filesystem, create it
            sub.clear()

    @wrap_errors(LogicalError)
    def clear(self):
        """
        IMPLEMENTED IN SUBCLASSES
        """

    @wrap_errors(LogicalError)
    def write(self):
        """
        IMPLEMENTED IN SUBCLASSES
        """

    @wrap_errors(LogicalError)
    def read(self):
        """
        IMPLEMENTED IN SUBCLASSES
        """


class JSONLog(Log):
    def __init__(self, path: str):
        """
        Create a new json Log
        """
        super().__init__(path, self)

    @wrap_errors(LogicalError)
    def clear(self):
        if os.path.exists(self.path):  # IF file exists
            os.remove(self.path)  # Delete
        open(self.path, "x").close()  # Create empty file

    @wrap_errors(LogicalError)
    def write(self, data):
        """
        Append one line of data to a csv log or dump to a pickle or json log
        :param data: dictionary of the form {"field": float_val}
        """
        with open(self.path, "w") as f:
            json.dump(data, f)  # Dump to file

    @wrap_errors(LogicalError)
    def read(self):
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
        os.remove(self.path)  # Delete

    def write(self, data: object):
        """
        Append one line of data to a csv log or dump to a pickle or json log
        :param data: object
        """
        with open(self.path, "wb") as f:
            pickle.dump(data, f)  # Dump to file

    @wrap_errors(LogicalError)
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
        super().__init__(path, self)
        self.headers = headers
        if pd.read_csv(self.path).columns.tolist() != self.headers:
            self.clear()  # Clear log if columns don't match up (out of date log)

    @wrap_errors(LogicalError)
    def clear(self):
        with open(self.path, "w") as f:  # Open file
            f.write(",".join(self.headers) + "\n")  # Write headers + newline

    @wrap_errors(LogicalError)
    def write(self, data: dict) -> None:
        """
        Append one line of data to a csv log or dump to a pickle or json log
        :param data: dictionary of the form {"column_name": value}
        """
        if list(data.keys()) != self.headers:  # Raise error if keys are wrong
            raise LogicalError(details="Incorrect keys for logging")
        new_row = pd.DataFrame.from_dict({k: [v] for (k, v) in data.items()})  # DataFrame from dict
        if len(df := self.read()) > 1000000:  # If this log is extremely long
            # Remove first row and append to log
            df.iloc[1:].append(new_row).to_csv(self.path, mode="w", header=True, index=False)
        else:
            new_row.to_csv(self.path, mode="a", header=False, index=False)  # Append to log

    @wrap_errors(LogicalError)
    def read(self) -> pd.DataFrame:
        """
        Read and return entire log
        :return: dataframe of entire log
        """
        return pd.read_csv(self.path, header=0)

    @wrap_errors(LogicalError)
    def truncate(self, n):
        """
        Remove n rows from csv log
        """
        if len(df := self.read()) <= n:
            self.clear()
        else:
            df.iloc[:-n].to_csv(self.path, mode="w", header=True, index=False)


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
        print("Power: ", int(t := time.time()), buspower, pwr := [round(i, 3) for i in pwr])
        self.sfr.logs["power"].write({
            "ts0": t // 100000 * 100000,
            "ts1": int(t % 100000),
            "buspower": str(buspower),
        } | {self.sfr.PDMS[i]: pwr[i] for i in range(len(pwr))})

    @wrap_errors(LogicalError)
    def log_solar(self, gen: list) -> None:
        """
        Logs the solar power generation from each panel (sum of A and B)
        :param gen: array of power inputs from each panel, in Watts
        :type gen: list
        """
        print("Solar: ", int(t := time.time()), gen := [round(i, 3) for i in gen])
        self.sfr.logs["solar"].write({
            "ts0": t // 100000 * 100000,
            "ts1": int(t % 100000),
        } | {self.sfr.PANELS[i]: gen[i] for i in range(len(gen))})

    @wrap_errors(LogicalError)
    def log_imu(self) -> None:
        """
        Logs IMU data
        """
        print("Imu: ", int(t := time.time()), tbl := [round(i, 3) for i in self.sfr.devices["IMU"].get_tumble()[0]])
        self.sfr.logs["imu"].write({
            "ts0": t // 100000 * 100000,
            "ts1": int(t % 100000),
            "xgyro": tbl[0],
            "ygyro": tbl[1],
            "zgyro": tbl[2],
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
        delta = (power := self.sfr.battery.charging_power()) * (time.time() - self.clocks["integrate"][0].last_iteration)
        # If we're drawing/gaining absurd amounts of power
        if abs(power) > 10:
            # Verify we're actually drawing an absurd amount of power
            total_draw = []
            for i in range(5):
                total_draw.append(self.sfr.eps.bus_power() + sum(self.sfr.eps.raw_pdm_draw()[1]))
                time.sleep(1)
            if (avg_draw := sum(total_draw) / 5) >= 10: 
                raise HighPowerDrawError(details="Average Draw: " + str(avg_draw))  # Raise exception
            else:  # If value was bogus, truncate logs
                self.sfr.logs["power"].truncate(1)
                self.sfr.logs["solar"].truncate(1)
        else:
            # Add delta * time to BATTERY_CAPACITY_INT
            self.sfr.vars.BATTERY_CAPACITY_INT += delta

    @wrap_errors(LogicalError)
    def update_orbits(self) -> None:
        """
        Update orbits log when sun is detected
        """
        if sun := self.sfr.sun_detected() and self.sfr.vars.LAST_DAYLIGHT_ENTRY < self.sfr.vars.LAST_ECLIPSE_ENTRY:
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
