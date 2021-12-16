import pandas as pd
import time
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


@wrap_errors(LogicalError)
def line_eq(a: tuple, b: tuple) -> callable:
    slope = (b[1] - a[1]) / (b[0] - a[1])
    y_int = a[1] - slope * a[0]
    return lambda x: slope * x + y_int


class Analytics:
    """
    Methods to analyze our data
    """
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        self.sfr = sfr

    @wrap_errors(LogicalError)
    def volt_to_charge(self, voltage: float) -> float:
        """
        Map volts to remaining battery charge in Joules
        :param voltage: battery voltage
        :return: (float) estimated charge in Joules
        """
        max_index = len(df := self.sfr.logs["voltage_energy"].read()) - 1
        for i in range(len(df)):
            if df["voltage"][i] > voltage:
                max_index = i
        line = line_eq((df["voltage"][max_index - 1], df["energy"][max_index - 1]),
                       (df["voltage"][max_index], df["energy"][max_index]))
        return line(voltage)

    @wrap_errors(LogicalError)
    def historical_consumption(self, n: int) -> pd.Series:
        """
        Get power consumption over last n datapoints
        """
        df = self.sfr.logs["power"].read().tail(n)
        return df[["buspower"] + [f"0x0{str(hex(i))[2:].upper()}" for i in range(1, 11)]].sum(axis=1)

    @wrap_errors(LogicalError)
    def predicted_consumption(self, duration: int) -> tuple:
        """
        Uses empirical data to estimate how much energy we'd consume
        with a particular set of pdms enabled over a duration.
        Accounts for change over time in power draw of components.
        :param pdm_states: list containing states of all pdms as 1 or 0
        :param duration: time, in seconds, to remain in state
        :return: (tuple) (predicted amount of energy consumed, standard deviation)
        """
        return (total := self.historical_consumption(50)).mean() * duration, total.stdev()

    @wrap_errors(LogicalError)
    def predicted_generation(self, duration) -> tuple:
        """
        Predict how much power will be generated by solar panels over given duration
        Assumes simulation will start at current orbital position
        :param duration: time in s to simulate for
        :return: (tuple) (estimated power generation, standard deviation of data, oldest data point)
        """
        current_time = time.time()  # Set current time
        panels = ["bcr1", "bcr2", "bcr3"]  # List of panels to average
        solar = self.sfr.logs["solar"].read().tail(50)  # Read solar power log
        orbits = self.sfr.logs["orbits"].read().tail(51)  # Read orbits log
        solar["timestamp"] = solar["ts0"] + solar["ts1"]
        orbits["timestamp"] = orbits["ts0"] + orbits["ts1"]
        # Calculate sunlight period
        sunlight_period = pd.Series([orbits["timestamp"][i + 1] - orbits["timestamp"][i]
                                     for i in range(orbits.shape[0] - 1)
                                     if orbits["phase"][i] == "sunlight"]).mean()
        # Calculate orbital period
        orbital_period = sunlight_period + pd.Series([orbits["timestamp"][i + 1] -
                                                      orbits["timestamp"][i] for i in range(orbits.shape[0] - 1)
                                                      if orbits["phase"][i] == "eclipse"]).mean()
        # Filter out all data points which weren't taken in sunlight
        in_sun = pd.DataFrame([solar[i] for i in range(solar.shape[0])
                               if orbits[solar["timestamp"][i] -
                                         orbits["timestamp"] > 0]["phase"][-1] == "sunlight"])
        solar_gen = in_sun[panels].sum(axis=1).mean()  # Calculate average solar power generation
        # Function to calculate energy generation over a given time since entering sunlight
        energy_over_time = lambda t: int(t / orbital_period) * sunlight_period * solar_gen + \
            min([t % orbital_period, sunlight_period]) * solar_gen
        # Set start time for simulation
        start = current_time - orbits[orbits["phase"] == "sunlight"]["timestamp"][-1]
        # Calculate and return total energy production over duration
        return energy_over_time(start + duration) - energy_over_time(start)

    @wrap_errors(LogicalError)
    def calc_orbital_period(self) -> float:
        """
        Calculate orbital period over last 50 orbits
        :return: average orbital period over last 50 orbits
        """
        df = self.sfr.logs["orbits"].read().tail(51)  # Reads in data
        # Calculates on either last 50 points or whole dataset
        print(df)
        sunlight = ((tmp := df[df["phase"] == "sunlight"])["ts0"] + tmp["ts1"]).tolist()
        eclipse = ((tmp := df[df["phase"] == "eclipse"])["ts0"] + tmp["ts1"]).tolist()
        # Appends eclipse data to deltas
        deltas = [sunlight[i + 1] - sunlight[i] for i in range(-2, -1 * len(sunlight), -1)] + \
                 [eclipse[i + 1] - eclipse[i] for i in range(-2, -1 * len(eclipse), -1)]
        if len(deltas) > 0:
            return sum(deltas) / len(deltas)
        else:
            return 90 * 60

    @wrap_errors(LogicalError)
    def signal_strength_variability(self) -> float:
        """
        Calculates and returns signal strength variability based on Iridium data
        :return: (float) standard deviation of signal strength
        """
        df = self.sfr.logs["iridium"].read()
        return df["signal"].std()

    @wrap_errors(LogicalError)
    def total_power_consumed(self) -> float:  # TODO: MULTIPLY W * S TO GET ENERGY
        """
        Calculates and returns total power consumed by satellite over mission duration
        """
        df = self.sfr.logs["power"].read()
        return df[[f"0x0{str(hex(i))}" for i in range(1, 11)] + ["buspower"]].sum().sum()

    @wrap_errors(LogicalError)
    def total_power_generated(self) -> float:
        """
        Calculates and returns total power generated by satellite over mission duration
        """
        df = self.sfr.logs["solar"].read()
        return df[["bcr1", "bcr2", "bcr3"]].sum().sum()

    @wrap_errors(LogicalError)
    def orbital_decay(self) -> float:
        """
        Calculates and returns total orbital decay of satellite in seconds
        """
        df = self.sfr.logs["orbits"].read()
        df["timestamp"] = df["ts0"] + df["ts1"]
        if len(df) < 3:
            raise RuntimeError("Not enough data!")
        return (df["timestamp"][-1] - df["timestamp"][-3]) - (df["timestamp"][2] - df["timestamp"][0])

    @wrap_errors(LogicalError)
    def total_data_transmitted(self) -> int:
        """
        Calculates and returns total amount of data transmitted by satellite
        """
        return self.sfr.logs["transmission"].read()["size"].sum()
