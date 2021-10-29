from MainControlLoop.Mode.mode import Mode
import gc


"""

        Measures Iridium signal strength over 3 orbits and transmits results
        :param measurements: number of measurements to take per orbit
        :param orbits: number of orbits to run for
                self.eps.commands["Pin On"]("Iridium")  # Switch on Iridium
        self.eps.commands["Pin On"]("UART-RS232")  # Switch on Iridium serial converter
        last_measurement = time.time()
        measurement_sep = self.sfr.ORBITAL_PERIOD / measurements  # Time between each measurement
        for orbit in range(orbits):  # Iterate through orbits
            for measurement in range(measurements):  # Iterate through measurements
                if time.time() - last_measurement >= measurement_sep:  # If enough time has passed to measure again
                    self.sfr.log_iridium(self.iridium.commands["Geolocation"](),
                    self.iridium.commands["Signal Quality"]())  # Log Iridium data
        # Transmit signal strength variability
        self.iridium.commands["Transmit"]("TJ;SSV:" + str(self.sfr.signal_strength_variability()))
        # Switch mode to either CHARGING or SCIENCE on exiting STARTUP, depending on battery voltage
        if self.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD:
            self.sfr.MODE = "CHARGING"
        else:
            self.sfr.MODE = "OUTREACH"
        self.sfr.dump()  # Log mode switch"""

class Science(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr, conditions={

        })

    def start(self) -> None:
