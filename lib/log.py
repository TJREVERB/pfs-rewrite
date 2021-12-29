import time
from lib.exceptions import wrap_errors, LogicalError, HighPowerDrawError
from lib.clock import Clock


class Logger:
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        self.sfr = sfr
        self.loggers = {
            "sfr": Clock(self.sfr.dump, 0),
            "imu": Clock(self.log_imu, 10),
            "power": Clock(self.integrate_charge, 30),
            "orbits": Clock(self.update_orbits, 60),
        }

    @wrap_errors(LogicalError)
    def log_pwr(self, buspower, pwr) -> None:
        """
        Logs the power draw of every pdm
        :param buspower: power draw of bus
        :param pdm_states: array of 1 and 0 representing state of all pdms. [0, 0, 1...]
        :param pwr: array of power draws from each pdm, in W. [1.3421 W, 0 W, .42123 W...]
        """
        print("Power: ", int(t := time.time()), buspower, pwr := [round(i, 3) for i in pwr])
        data = {
            "ts0": t // 100000 * 100000,
            "ts1": int(t % 100000),
            "buspower": str(buspower),
        }
        for i in range(len(pwr)):
            data[self.sfr.PDMS] = pwr[i]
        self.sfr.logs["power"].write(data)

    @wrap_errors(LogicalError)
    def log_solar(self, gen: list) -> None:
        """
        Logs the solar power generation from each panel (sum of A and B)
        :param gen: array of power inputs from each panel, in W.
        """
        print("Solar: ", int(t := time.time()), gen := [round(i, 3) for i in gen])
        self.sfr.logs["solar"].write({
            "ts0": t // 100000 * 100000,
            "ts1": int(t % 100000),
            "bcr1": gen[0],
            "bcr2": gen[1],
            "bcr3": gen[2],
        })

    @wrap_errors(LogicalError)
    def log_imu(self) -> None:  # Probably scuffed
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

    @wrap_errors(LogicalError)
    def integrate_charge(self) -> None:
        """
        Integrate charge in Joules
        """
        # Log total power, store values into variables
        self.log_pwr(self.sfr.eps.bus_power(), self.sfr.eps.raw_pdm_draw()[1])
        # Log solar generation, store list into variable gen
        self.log_solar(self.sfr.eps.raw_solar_gen())
        delta = self.sfr.battery.charging_power() * (time.time() - self.loggers["power"].last_iteration)
        # If we're drawing/gaining absurd amounts of power
        if abs(delta) > 999:  # TODO: ARBITRARY THRESHOLD
            # Verify we're actually drawing an absurd amount of power
            total_draw = []
            for i in range(5):
                total_draw.append(self.sfr.eps.bus_power() + sum(self.sfr.eps.raw_pdm_draw()[1]))
                time.sleep(1)
            if (avg_draw := sum(total_draw) / 5) >= 999:  # TODO: ARBITRARY THRESHOLD
                raise HighPowerDrawError(details="Average Draw: " + str(avg_draw))  # Raise exception
            else:  # If value was bogus, truncate logs and integrate charge based on historical data
                self.sfr.logs["power"].truncate(1)
                self.sfr.logs["solar"].truncate(1)
                self.sfr.vars.BATTERY_CAPACITY_INT += self.sfr.analytics.predicted_generation(
                    t := time.time() - self.loggers["power"].last_iteration) - (self.sfr.analytics.predicted_consumption(t))
        else:
            # Add delta * time to BATTERY_CAPACITY_INT
            self.sfr.vars.BATTERY_CAPACITY_INT += delta

    @wrap_errors(LogicalError)
    def update_orbits(self):
        """
        Update orbits log when sun is detected
        """
        if sun := self.sfr.sun_detected() and self.sfr.vars.LAST_DAYLIGHT_ENTRY < self.sfr.vars.LAST_ECLIPSE_ENTRY:
            self.sfr.enter_sunlight()
        elif not sun and self.sfr.vars.LAST_DAYLIGHT_ENTRY > self.sfr.vars.LAST_ECLIPSE_ENTRY:
            self.sfr.enter_eclipse()
        self.sfr.vars.ORBITAL_PERIOD = self.sfr.analytics.calc_orbital_period()

    @wrap_errors(LogicalError)
    def log(self):
        for i in self.loggers.keys():
            self.loggers[i].execute()
