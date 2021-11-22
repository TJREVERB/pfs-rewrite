"""
Methods to analyze our data
"""
import pandas as pd
import numpy as np
import time


def line_eq(a: tuple, b: tuple) -> callable:
    slope = (b[1] - a[1]) / (b[0] - a[1])
    y_int = a[1] - slope * a[0]
    return lambda x: slope * x + y_int


class Analytics:
    def __init__(self, sfr):
        self.sfr = sfr

    def volt_to_charge(self, voltage: float) -> float:
        """
        Map volts to remaining battery charge in Joules
        :param voltage: battery voltage
        :return: (float) estimated charge in Joules
        """
        max_index = len(self.sfr.voltage_energy_map["voltage"]) - 1
        for i in range(len(self.sfr.voltage_energy_map["voltage"])):
            if self.sfr.voltage_energy_map["voltage"][i] > voltage:
                max_index = i
        min_index = max_index - 1
        line = line_eq((self.sfr.voltage_energy_map["voltage"][min_index],
                        self.sfr.voltage_energy_map["energy"][min_index]),
                       (self.sfr.voltage_energy_map["voltage"][max_index],
                        self.sfr.voltage_energy_map["energy"][max_index]))
        return line(voltage)

    def predicted_consumption(self, pdm_states: list, duration: int) -> tuple:
        """
        Uses empirical data to estimate how much energy we'd consume
        with a particular set of pdms enabled over a duration.
        Accounts for change over time in power draw of components.
        :param pdm_states: list containing states of all pdms as 1 or 0
        :param duration: time, in seconds, to remain in state
        :return: (tuple) (predicted amount of energy consumed, standard deviation)
        """
        df = pd.read_csv(self.sfr.pwr_log_path, header=0).tail(50)
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
        solar = pd.read_csv(self.sfr.solar_log_path, header=0).tail(51)  # Read solar power log
        orbits = pd.read_csv(self.sfr.orbit_log_path, header=0).tail(51)  # Read orbits log
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

    def calc_orbital_period(self) -> float:
        """
        Calculate orbital period over last 50 orbits
        :return: average orbital period over last 50 orbits
        """
        df = pd.read_csv(self.sfr.orbit_log_path, header=0)  # Reads in data
        # Calculates on either last 50 points or whole dataset
        sunlight = df.loc[df["phase"] == "sunlight"]
        eclipse = df.loc[df["phase"] == "eclipse"]
        # Appends eclipse data to deltas
        deltas = [sunlight[i + 1] - sunlight[i] for i in range(-2, -1 * min([len(sunlight), 50]), -1)] + \
            [eclipse[i + 1] - eclipse[i] for i in range(-2, -1 * min([len(eclipse), 50]), -1)]
        if len(deltas) > 0:
            return sum(deltas) / len(deltas)
        else:
            return -1

    def signal_strength_variability(self) -> float:
        """
        Calculates and returns signal strength variability based on Iridium data
        :return: (float) standard deviation of signal strength
        """
        df = pd.read_csv(self.sfr.iridium_data_path, header=0)
        return df["signal"].std()
