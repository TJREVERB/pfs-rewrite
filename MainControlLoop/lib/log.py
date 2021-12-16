import time
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Logger:
    class Clock:
        @wrap_errors(LogicalError)
        def __init__(self, func: callable, delay: float):
            """
            Run given function after given delay
            :param func: function to run
            :param delay: time to wait (seconds)
            """
            self.func, self.delay = func, delay
            self.last_iteration = 0

        def execute(self):
            """
            Execute a single cycle of the clock.
            Run func if enough time has passed, do nothing otherwise
            """
            if time.perf_counter() > self.last_iteration + self.delay:
                self.func()
                self.last_iteration = time.perf_counter()

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        self.sfr = sfr
        self.loggers = {
            "sfr": self.Clock(self.sfr.dump, 0),
            "imu": self.Clock(self.log_imu, 10),
            "power": self.Clock(self.integrate_charge, 30),
            "orbits": self.Clock(self.update_orbits, 60),
        }

    @wrap_errors(LogicalError)
    def log_pwr(self, buspower, pwr) -> None:
        """
        Logs the power draw of every pdm
        :param buspower: power draw of bus
        :param pdm_states: array of 1 and 0 representing state of all pdms. [0, 0, 1...]
        :param pwr: array of power draws from each pdm, in W. [1.3421 W, 0 W, .42123 W...]
        """
        print("Power: ", t := time.time(), pwr := [round(i, 3) for i in pwr])
        data = {
            "ts0": t // 100000 * 100000,
            "ts1": int(t % 100000),
            "buspower": str(buspower),
        }
        for i in range(len(pwr)):
            data[f"0x0{str(hex(i + 1))[2:].upper()}"] = pwr[i]
        self.sfr.logs["power"].write(data)

    @wrap_errors(LogicalError)
    def log_solar(self, gen: list) -> None:
        """
        Logs the solar power generation from each panel (sum of A and B)
        :param gen: array of power inputs from each panel, in W.
        """
        print("Solar: ", t := time.time(), gen := [round(i, 3) for i in gen])
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
        print("Imu: ", t := time.time(), tbl := [round(i, 3) for i in self.sfr.imu.getTumble()[0]])
        self.sfr.logs["imu"].write({
            "ts0": t // 100000 * 100000,
            "ts1": int(t % 100000),
            "xgyro": tbl[0],
            "ygyro": tbl[1],
        })

    @wrap_errors(LogicalError)
    def integrate_charge(self) -> None:
        """
        Integrate charge in Joules
        """
        import inspect
        curframe = inspect.currentframe()
        calframe = inspect.getouterframes(curframe, 3)
        print('Log pwr caller name:', calframe[2][3])
        # Log total power, store values into variables
        self.log_pwr(self.sfr.eps.bus_power(), self.sfr.eps.raw_pdm_draw()[1])
        # Log solar generation, store list into variable gen
        self.log_solar(self.sfr.eps.raw_solar_gen())
        # Subtract delta * time from BATTERY_CAPACITY_INT
        self.sfr.vars.BATTERY_CAPACITY_INT += self.sfr.battery.charging_power() * \
                                              (time.perf_counter() - self.loggers["power"].last_iteration)

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
