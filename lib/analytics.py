import pandas as pd
import time
from lib.exceptions import wrap_errors, LogicalError


@wrap_errors(LogicalError)
def line_eq(a: tuple, b: tuple) -> callable:
    slope = (b[1] - a[1]) / (b[0] - a[1])
    y_int = a[1] - slope * a[0]
    return lambda x: slope * x + y_int


class Analytics:
    """
    This class provides methods to analyze data from logs

    :param sfr: sfr object
    :type sfr: :class: 'lib.registry.StateFieldRegistry'
    """

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        self.sfr = sfr

    @wrap_errors(LogicalError)
    def volt_to_charge(self, voltage: float) -> float:
        """
        Map volts to remaining battery charge in Joules

        :param voltage: battery voltage
        :type voltage: float
        :return: estimated charge in Joules
        :rtype: float
        """
        max_index = ((df := self.sfr.logs["voltage_energy"].read())  # Read voltage-energy log and walrus into "df"
                     [df["voltage"] > voltage]  # Get all rows where voltage is above target voltage
                     .shape[0]  # Get length of result
                     - 1)  # Length - 1 is last index
        # Linearize function near target voltage
        line = line_eq((df["voltage"][max_index],  # x: voltage at row immediately greater than target
                        df["energy"][max_index]),  # y: energy at row immediately greater than target
                       (df["voltage"][max_index + 1],  # x: voltage at row immediately less than target
                        df["energy"][max_index + 1]))  # y: energy at row immediately less than target
        return line(voltage)  # Calculate energy at target voltage

    @wrap_errors(LogicalError)
    def historical_consumption(self, n: int) -> pd.Series:
        """
        Returns pandas series of power consumption over last/latest n data points

        :param n: number of data points to return
        :type n: int
        :return: :class:'pd.Series' of last n data points
        :rtype: :class:'pd.Series'
        """

        df = self.sfr.logs["power"].read().tail(n)  # Get last n elements
        return (df[["buspower"] + self.sfr.PDMS]  # Get columns containing power draw values
                .sum(axis=1))  # Sum over first axis to get a Series containing total power draw for each row

    @wrap_errors(LogicalError)
    def historical_generation(self, n: int) -> pd.Series:
        """
        Get power generation over last n data points while in sunlight

        :param n: number of data points to return
        :type n: int
        :return: :class:'pd.Series' of last n data points while in sunlight
        :rtype: :class:'pd.Series'
        """
        df = self.sfr.logs["solar"].read().tail(n)  # Get last n elements
        return ((sums :=  # Walrus into variable "sums"
                 df[self.sfr.PANELS]  # Get columns for all panels
                 .sum(axis=1))  # Find the sum
                [sums > self.sfr.eps.SUN_DETECTION_THRESHOLD])  # Rows of sums where sum is greater than threshold

    @wrap_errors(LogicalError)
    def predicted_consumption(self, duration: int) -> float:
        """
        Uses empirical data to estimate how much energy we'd consume
        with a particular set of pdms enabled over a duration.
        Accounts for change over time in power draw of components.

        :param duration: time in seconds to remain in state
        :type duration: int
        :return: predicted amount of energy consumed
        :rtype: float
        """
        return (self.historical_consumption(50)  # Sum of 50 rows of power log
                .mean()  # Get mean
                * duration)  # Multiply by duration to predict consumption

    @wrap_errors(LogicalError)
    def predicted_generation(self, duration: int) -> tuple:
        """
        Predict how much power will be generated by solar panels over given duration
        Assumes simulation will start at current orbital position
        :param duration: time in seconds to simulate for
        :type duration: int
        :return: tuple of (estimated power generation, standard deviation of data, oldest data point)
        :rtype: tuple
        """
        current_time = time.time()  # Set current time
        orbits = self.sfr.logs["orbits"].read().tail(51)  # Read first 51 elements of orbits log
        if orbits.shape[0] < 4:  # If we haven't logged any orbits
            solar = self.sfr.logs["solar"].read().tail(50)  # Read first 50 elements of solar power log
            if solar.shape[0] > 0:  # If we have solar data
                # Estimate based on what we have
                return (solar[self.sfr.PANELS]  # Get only panels columns
                        .sum(axis=1)  # Get total generation for each row
                        .mean()  # Mean generation over dataset
                        * duration)  # Multiply by duration to predict generation
            else:  # If we haven't logged any solar data
                return self.sfr.eps.solar_power() * duration  # Poll eps for power estimate and multiply by duration
        orbits["timestamp"] = orbits["ts0"] + orbits["ts1"]  # Generate timestamp column
        # Calculate sunlight period
        sunlight_period = (orbits[orbits["phase"] == "daylight"]  # Get all rows where phase is daylight
                           ["timestamp"]  # Get timestamp column of those rows
                           .diff()  # Difference between daylight entries
                           .mean(skipna=True))  # Mean difference between daylight entries
        orbital_period = self.calc_orbital_period()  # Calculate orbital period
        in_sun = self.historical_generation(50)  # Filter out all data points which weren't taken in sunlight
        solar_gen = in_sun.mean()  # Calculate average solar power generation

        # Function to calculate energy generation over a given time since entering sunlight
        def energy_over_time(t):  # Magic
            return int(t / orbital_period) * sunlight_period * solar_gen + \
                   min([t % orbital_period, sunlight_period]) * solar_gen

        # Set start time for simulation
        start = (current_time  # Start with current time
                 -  # Subtract last time we entered daylight (to get current orbital position)
                 orbits[orbits["phase"] == "daylight"]  # All rows where we're in daylight
                 ["timestamp"]  # Get timestamp column
                 .iloc[-1])  # Get last row (last time we entered daylight)
        # Calculate and return total energy production over duration
        return energy_over_time(start + duration) - energy_over_time(start)  # f(a + b) - f(a) = f(b)

    @wrap_errors(LogicalError)
    def calc_orbital_period(self) -> float:
        """
        Calculate orbital period over last 50 orbits
        :return: average orbital period over last 50 orbits
        """
        df = self.sfr.logs["orbits"].read().tail(51)  # Reads in data
        df["timestamp"] = df["ts0"] + df["ts1"]  # Create timestamp column
        if df.shape[0] > 2:  # If we have enough rows
            return df["timestamp"].diff(periods=2).mean(skipna=True)  # Return orbital period
        return 90 * 60  # Return assumed orbital period

    @wrap_errors(LogicalError)
    def signal_strength_mean(self) -> float:
        """
        Calculates and returns signal strength mean based on Iridium data

        :return: average signal strength
        :rtype: float
        """
        df = self.sfr.logs["iridium"].read()
        return df["signal"].mean()

    @wrap_errors(LogicalError)
    def signal_strength_variability(self) -> float:
        """
        Calculates and returns signal strength variability based on Iridium data

        :return: standard deviation of signal strength
        :rtype: float
        """
        df = self.sfr.logs["iridium"].read()
        return df["signal"].std()

    @wrap_errors(LogicalError)
    def total_energy_consumed(self) -> float:
        """
        Calculates and returns total energy consumed by satellite over mission duration

        :return: total energy consumed by satellite over mission duration
        :rtype: float
        """
        df = self.sfr.logs["power"].read()
        df["timestamp"] = df["ts0"] + df["ts1"]
        return (df["timestamp"].diff().iloc[1:] * df[self.sfr.PDMS + ["buspower"]].sum(axis=1).iloc[1:]).sum()

    @wrap_errors(LogicalError)
    def total_energy_generated(self) -> float:
        """
        Calculates and returns total energy generated by satellite over mission duration

        :return: total energy generated by satellite over mission duration
        :rtype: float
        """
        df = self.sfr.logs["solar"].read()
        df["timestamp"] = df["ts0"] + df["ts1"]
        return (df["timestamp"].diff() * df[self.sfr.PANELS].sum(axis=0).iloc[1:]).sum()

    @wrap_errors(LogicalError)
    def orbital_decay(self) -> float:
        """
        Calculates and returns total orbital decay of satellite in seconds

        :return: orbital decay of satellite in seconds
        :rtype: float
        """
        df = self.sfr.logs["orbits"].read()
        df["timestamp"] = df["ts0"] + df["ts1"]
        if df.shape[0] < 3:
            return 0
        return (df["timestamp"].iloc[-1] - df["timestamp"].iloc[-3]) - \
               (df["timestamp"].iloc[2] - df["timestamp"].iloc[0])

    @wrap_errors(LogicalError)
    def total_data_transmitted(self) -> int:
        """
        Calculates and returns total amount of data transmitted by satellite

        :return: total amount of data transmitted by satellite
        :rtype: int
        """
        return self.sfr.logs["transmission"].read()["size"].sum()

    @wrap_errors(LogicalError)
    def sunlight_ratio(self, n: int) -> float:
        """
        Calculates and returns over the last 50 orbits what fraction of each orbit we spend in sunlight

        :param n: number of orbits to analyze
        :type n: int
        :return: what fraction of each orbit we spend in sunlight (0 if not enough data)
        :rtype: float
        """
        orbits_data = self.sfr.logs["orbits"].read().tail(n * 2 + 1)
        orbits_data["timestamp"] = orbits_data["ts0"] + orbits_data["ts1"]
        # Calculate sunlight period
        if orbits_data.shape[0] > 2:
            sunlight_period = (orbits_data[orbits_data["phase"] == "sunlight"]["timestamp"]).diff(periods=2).mean()
        else:
            sunlight_period = 0
        return sunlight_period / self.sfr.vars.ORBITAL_PERIOD  # How much of our orbit we spend in sunlight
