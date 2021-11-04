from MainControlLoop.Mode.mode import Mode
import time


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
        self.last_ping = time.time()
        self.pings_performed = 0
        self.DATAPOINT_SPACING = 60 # in seconds
        self.NUMBER_OF_REQUIRED_PINGS = (90*60)/self.DATAPOINT_SPACING # number of pings to do to complete orbit

    def start(self):
        Mode.turn_devices_off()
        self.eps.commands["Pin On"]("Iridium")
        self.eps.commands["Pin On"]("UART-RS232")
        self.devices["Iridium"] = True

    def check_conditions(self) -> bool:
        if self.eps.telemetry["VBCROUT"]() > self.LOWER_THRESHOLD and self.pings_performed <= self.NUMBER_OF_REQUIRED_PINGS:  # if voltage greater than lower thres
            # TODO: SET CUSTOM LOWER THRESHOLD
            return True
        else:
            return False

    def execute_cycle(self):
        if self.pings_performed == self.NUMBER_OF_REQUIRED_PINGS:
            #send data back
            #when successful
            #do pings_peformed++
        elif time.time() - self.last_ping >= self.datapoint_spacing:
            #check signal strength
            #save data
            #pings_performed++

    def switch_modes(self):
        pass



