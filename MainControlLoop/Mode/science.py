from MainControlLoop.Mode.mode import Mode
import time


class Science(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)
        self.last_ping = time.time()
        self.pings_performed = 0
        self.DATAPOINT_SPACING = 60  # in seconds
        self.NUMBER_OF_REQUIRED_PINGS = (90*60)/self.DATAPOINT_SPACING # number of pings to do to complete orbit

    def __str__(self):
        return "Science"

    def start(self):
        self.instruct["Pin On"](self.sfr.defaults["PRIMARY_RADIO"])

    def check_conditions(self) -> bool:
        if self.sfr.eps.telemetry["VBCROUT"]() > self.LOWER_THRESHOLD and self.pings_performed <= self.NUMBER_OF_REQUIRED_PINGS:  # if voltage greater than lower thres
            # TODO: SET CUSTOM LOWER THRESHOLD
            return True
        else:
            return False

    def execute_cycle(self):
        if self.pings_performed == self.NUMBER_OF_REQUIRED_PINGS:
            # Transmit signal strength variability
            self.sfr.devices["Iridium"].commands["Transmit"]("TJ;SSV:" + str(self.sfr.signal_strength_variability()))
            self.pings_performed += 1
        elif time.time() - self.last_ping >= self.DATAPOINT_SPACING:
            self.sfr.log_iridium(self.sfr.devices["Iridium"].commands["Geolocation"](), self.sfr.devices["Iridium"].commands["Signal Quality"]())  # Log Iridium data
            self.pings_performed += 1

    def switch_modes(self):
        pass

    def terminate_mode(self):
        self.instruct["Pin Off"](self.sfr.defaults["PRIMARY_RADIO"])



