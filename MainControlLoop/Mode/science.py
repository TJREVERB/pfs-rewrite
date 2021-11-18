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
            "Collection Complete": False,
            "Low Battery": False
        }

    def __str__(self):
        return "Science"

    def start(self):
        super(Science, self).start()

        self.instruct["Pin On"](self.sfr.primary_radio)
        self.instruct["All Off"](exceptions=[self.sfr.primary_radio])

        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.sfr.LOWER_THRESHOLD
        self.conditions["Collection Complete"] = self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS

    def check_conditions(self) -> bool:
        if self.conditions["Collection Complete"]:
            return False
        elif self.conditions["Low Battery"]:
            return False
        else:
            return True

    def update_conditions(self):
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.sfr.LOWER_THRESHOLD
        self.conditions["Collection Complete"] = self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS

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

        if self.conditions["Low Battery"]:  # if the battery is low, switch to charging mode
            return Charging(self.sfr)
        elif self.conditions["Collection Complete"]:
            return Outreach(self.sfr)
        else:
            return Charging(self.sfr)

    def terminate_mode(self):
        super(Science, self).terminate_mode()
        pass
