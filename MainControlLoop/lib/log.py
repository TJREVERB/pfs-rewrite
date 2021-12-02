import time
import pandas as pd


class Logger:
    def __init__(self, sfr):
        self.sfr = sfr
        self.last_log_time = time.perf_counter()
        self.last_orbit_update = self.last_log_time
        self.LOG_DELAY = 10  # Seconds
        self.ORBIT_CHECK_DELAY = 60

    def log_pwr(self, pdm_states, pwr, t=0) -> None:
        """
        Logs the power draw of every pdm
        :param pdm_states: array of 1 and 0 representing state of all pdms. [0, 0, 1...]
        :param pwr: array of power draws from each pdm, in W. [1.3421 W, 0 W, .42123 W...]
        :param t: time to log data, defaults to time method is called
        """
        if t == 0:
            t = time.time()
        print("Power: ", t, pdm_states, pwr)
        # Format data into pandas series
        data = pd.concat([pd.Series([t]), pd.Series(pdm_states), pd.Series(pwr)])
        data.to_frame().to_csv(path_or_buf=self.sfr.pwr_log_path, mode="a", header=False)  # Append data to log

    def log_solar(self, gen: list, t=0) -> None:
        """
        Logs the solar power generation from each panel (sum of A and B)
        :param gen: array of power inputs from each panel, in W.
        :param t: time to log data, defaults to time method is called
        """
        if t == 0:
            t = time.time()
        print("Solar: ", t, gen)
        data = pd.concat([pd.Series([t]), pd.Series(gen)])  # Format data into pandas series
        data.to_frame().to_csv(path_or_buf=self.sfr.solar_log_path, mode="a", header=False)  # Append data to log
    
    def integrate_charge(self) -> None:
        """
        Integrate charge in Joules
        """
        # Log total power, store values into variables
        self.log_pwr((pdms_on := self.sfr.eps.power_pdms_on())[1], 
            buspower := self.sfr.eps.bus_power() + pdms_on[0])
        # Log solar generation, store list into variable gen
        self.log_solar(gen := self.sfr.eps.raw_solar_gen())
        # Subtract delta * time from BATTERY_CAPACITY_INT
        self.sfr.vars.BATTERY_CAPACITY_INT += (sum(gen) - buspower - pdms_on[0]) * \
            (t := time.perf_counter() - self.last_log_time)
        # Update previous_time, accounts for rollover
        self.last_log_time = t
    
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
    
    def log(self):
        if time.perf_counter() - self.last_log_time > self.LOG_DELAY:
            print("Logging power")
            self.integrate_charge()
        if time.perf_counter() - self.last_orbit_update > self.ORBIT_CHECK_DELAY:
            print("Logging orbits")
            self.update_orbits()
        self.sfr.dump()
