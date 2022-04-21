import pandas as pd
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
        line = line_eq((df["voltage"].iloc[max_index],  # x: voltage at row immediately greater than target
                        df["energy"].iloc[max_index]),  # y: energy at row immediately greater than target
                       (df["voltage"].iloc[max_index + 1],  # x: voltage at row immediately less than target
                        df["energy"].iloc[max_index + 1]))  # y: energy at row immediately less than target
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
    def signal_strength_mean(self) -> float:
        """
        Calculates and returns signal strength mean based on Iridium data

        :return: average signal strength
        :rtype: float
        """
        return (self.sfr.logs["iridium"].read()  # Read iridium log
                ["signal"]  # Get signal strength column
                .mean())  # Find mean

    @wrap_errors(LogicalError)
    def signal_strength_variability(self) -> float:
        """
        Calculates and returns signal strength variability based on Iridium data

        :return: standard deviation of signal strength
        :rtype: float
        """
        return (self.sfr.logs["iridium"].read()  # Read iridium log
                ["signal"]  # Get signal strength column
                .std())  # Find standard deviation

    @wrap_errors(LogicalError)
    def total_energy_consumed(self) -> float:
        """
        Calculates and returns total energy consumed by satellite over mission duration

        :return: total energy consumed by satellite over mission duration
        :rtype: float
        """
        return ((((df := self.sfr.logs["power"].read())  # Read entire power log and walrus into "df"
                  ["ts0"] + df["ts1"])  # Calculate timestamp column
                 .diff()  # Find differences between consecutive timestamps (delta t)
                 .iloc[1:]  # Remove nan value created by diff
                 *  # Multiply delta t by
                 df[self.sfr.PDMS + ["buspower"]]  # Power draw columns
                 .sum(axis=1)  # Sum to find total power draw for each row
                 .iloc[1:])  # Exclude first element to keep size the same as timestamp diff column
                .sum())  # Sum of total power draws for each row to get total power draw over entire mission

    @wrap_errors(LogicalError)
    def total_energy_generated(self) -> float:
        """
        Calculates and returns total energy generated by satellite over mission duration

        :return: total energy generated by satellite over mission duration
        :rtype: float
        """
        return ((((df := self.sfr.logs["solar"].read())  # Read entire solar log and walrus into "df"
                  ["ts0"] + df["ts1"])  # Calculate timestamp column
                 .diff()  # Find differences between consecutive timestamps (delta t)
                 .iloc[1:]  # Remove nan value created by diff
                 *  # Multiply delta t by
                 df[self.sfr.PANELS]  # Solar generation columns
                 .sum(axis=1)  # Sum to find total power draw for each row
                 .iloc[1:])  # Exclude first element to keep size the same as timestamp diff column
                .sum())  # Sum of total power draws for each row to get total power draw over entire mission

    @wrap_errors(LogicalError)
    def total_data_transmitted(self) -> int:
        """
        Calculates and returns total amount of data transmitted by satellite

        :return: total amount of data transmitted by satellite
        :rtype: int
        """
        return (self.sfr.logs["transmission"].read()  # Read transmission log
                ["size"]  # Get size column
                .sum())  # Calculate and return sum
