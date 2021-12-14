import time
import pandas as pd
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Logger:
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        self.sfr = sfr
        self.last_log_time = time.perf_counter()
        self.last_orbit_update = self.last_log_time
        self.LOG_DELAY = 10  # Seconds
        self.ORBIT_CHECK_DELAY = 60

    @wrap_errors(LogicalError)
    def log_pwr(self, buspower, pdm_states, pwr) -> None:
        """
        Logs the power draw of every pdm
        :param buspower: power draw of bus
        :param pdm_states: array of 1 and 0 representing state of all pdms. [0, 0, 1...]
        :param pwr: array of power draws from each pdm, in W. [1.3421 W, 0 W, .42123 W...]
        :param t: time to log data, defaults to time method is called
        """
        print("Power: ", t := time.time(), pdm_states, pwr)
        with open(self.sfr.pwr_log_path, "a") as f:
            f.write(str(t) + "," + str(buspower) + ",".join(pdm_states) + "," + ",".join(pwr) + "\n")

    @wrap_errors(LogicalError)
    def log_solar(self, gen: list) -> None:
        """
        Logs the solar power generation from each panel (sum of A and B)
        :param gen: array of power inputs from each panel, in W.
        :param t: time to log data, defaults to time method is called
        """
        print("Solar: ", t := time.time(), gen)
        with open(self.sfr.solar_log_path, "a") as f:
            f.write(str(t) + "," + ",".join(gen) + "\n")

    @wrap_errors(LogicalError)
    def log_imu(self, tumble: list) -> None: # Probably scuffed
        """
        Logs IMU datapoints
        :param tumble: result of getTumble() call
        """
        print("Imu: ", t := time.time(), tumble)

        # Format data into pandas series
        data = pd.concat(pd.Series([t]), pd.Series(tumble[0]), pd.Series(tumble[1]))
        data.to_frame().to_csv(path_or_buf=self.sfr.imu_log_path)

    @wrap_errors(LogicalError)
    def integrate_charge(self) -> None:
        """
        Integrate charge in Joules
        """
        # Log total power, store values into variables
        self.log_pwr((pdms_on := self.sfr.eps.power_pdms_on())[1], self.sfr.eps.bus_power(), pdms_on[0])
        # Log solar generation, store list into variable gen
        self.log_solar(self.sfr.eps.raw_solar_gen())
        # Subtract delta * time from BATTERY_CAPACITY_INT
        self.sfr.vars.BATTERY_CAPACITY_INT += self.sfr.battery.charging_power() * \
            (t := time.perf_counter() - self.last_log_time)
        self.last_log_time = t  # Update previous_time, accounts for rollover

    @wrap_errors(LogicalError)
    def update_orbits(self):
        """
        Update orbits log when sun is detected
        """
        if sun := self.sfr.eps.sun_detected() and self.sfr.vars.LAST_DAYLIGHT_ENTRY < self.sfr.vars.LAST_ECLIPSE_ENTRY:
            self.sfr.enter_sunlight()
        elif not sun and self.sfr.vars.LAST_DAYLIGHT_ENTRY > self.sfr.vars.LAST_ECLIPSE_ENTRY:
            self.sfr.enter_eclipse()
        self.sfr.vars.ORBITAL_PERIOD = self.sfr.analytics.calc_orbital_period()
        self.last_orbit_update = time.perf_counter()

    @wrap_errors(LogicalError)
    def log(self):
        if time.perf_counter() - self.last_log_time > self.LOG_DELAY:
            print("Logging power")
            self.integrate_charge()
            self.last_log_time = time.perf_counter()
        if time.perf_counter() - self.last_orbit_update > self.ORBIT_CHECK_DELAY:
            print("Logging orbits")
            self.update_orbits()
            self.last_log_time = time.perf_counter()
        self.sfr.dump()
