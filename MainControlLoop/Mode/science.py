from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.mode import Mode
import time

from MainControlLoop.Mode.outreach import Outreach


class Science(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)
        self.last_ping = time.time()
        self.pings_performed = 0
        self.DATAPOINT_SPACING = 60  # in seconds
        self.NUMBER_OF_REQUIRED_PINGS = (90*60)/self.DATAPOINT_SPACING # number of pings to do to complete orbit
        self.conditions = {
            "COLLECTION_COMPLETE":False,
            "CHARGE_LOW":False
        }

    def __str__(self):
        return "Science"

    def start(self):
        super(Science, self).start()
        # We shouldn't be looking in the defaults dictionary to find the primary radio...
        # Use the primary radio defined after sfr instantiation
        # i.e. self.sfr.PRIMARY_RADIO
        self.instruct["Pin On"](self.sfr.PRIMARY_RADIO)
        # Pin On the Iridium as well? Because we need it to conduct our measurements

    def check_conditions(self) -> bool:
        self.conditions["CHARGE_LOW"] = self.sfr.eps.telemetry["VBCROUT"]() > self.sfr.LOWER_THRESHOLD 
        self.conditions["COLLECTION_COMPLETE"] = self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS
        if self.conditions["CHARGE_LOW"] or self.conditions["COLLECTION_COMPLETE"]:  # if voltage greater than lower threshold
            return False
        else:
            return True

    def execute_cycle(self):
        super(Science, self).execute_cycle()
        if self.pings_performed == self.NUMBER_OF_REQUIRED_PINGS:
            # Transmit signal strength variability
            self.sfr.devices["Iridium"].commands["Transmit"]("TJ;SSV:" + 
                                                             str(self.sfr.signal_strength_variability()))
            self.pings_performed += 1
        elif time.time() - self.last_ping >= self.DATAPOINT_SPACING:
            self.sfr.log_iridium(self.sfr.devices["Iridium"].commands["Geolocation"](), 
                                 self.sfr.devices["Iridium"].commands["Signal Quality"]())  # Log Iridium data
            self.pings_performed += 1

    def switch_modes(self):
        super(Science, self).switch_modes()  # Run switch_modes of superclass

        if self.conditions["CHARGE_LOW"]:  # if the battery is low, switch to charging mode
            return Charging
        elif self.conditions["COLLECTION_COMPLETE"]:
            return Outreach
        else:
            return Science #if this is called even though the conditions are met, this just returns itself

    def terminate_mode(self):
        self.instruct["Pin Off"](self.sfr.PRIMARY_RADIO)
