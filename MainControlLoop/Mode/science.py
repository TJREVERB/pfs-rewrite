from MainControlLoop.Mode.mode import Mode
import time


class Science(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)
        self.last_ping = time.time()
        self.pings_performed = 0
        self.DATAPOINT_SPACING = 60  # in seconds
        self.NUMBER_OF_REQUIRED_PINGS = (90 * 60) / self.DATAPOINT_SPACING  # number of pings to do to complete orbit
        self.PRIMARY_IRIDIUM_WAIT_TIME = 5 * 60  # wait time for iridium polling if iridium is main radio
        self.SECONDARY_IRIDIUM_WAIT_TIME = 20 * 60  # wait time for iridium polling if iridium is not main radio
        self.conditions = {
            "Collection Complete": False,
            "Low Battery": False
        }

        self.PRIMARY_IRIDIUM_WAIT_TIME = 5 * 60  # wait time for iridium polling if iridium is main radio
        self.SECONDARY_IRIDIUM_WAIT_TIME = 20 * 60  # wait time for iridium polling if iridium is not main radio

    def __str__(self):
        return "Science"

    def start(self) -> None:
        super(Science, self).start()
        self.instruct["Pin On"](self.sfr.primary_radio)
        self.instruct["All Off"](exceptions=[self.sfr.primary_radio])
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.sfr.LOWER_THRESHOLD
        self.conditions["Collection Complete"] = self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS

    def check_conditions(self) -> bool:
        super(Science, self).check_conditions()
        if self.conditions["Low Battery"]:
            self.switch_mode("Charging")
            return False
        elif self.conditions["Collection Complete"]:
            self.switch_mode("Outreach")
            return False
        else:
            return True

    def update_conditions(self) -> None:
        super(Science, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.sfr.LOWER_THRESHOLD
        self.conditions["Collection Complete"] = self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS

    def execute_cycle(self) -> None:
        super(Science, self).execute_cycle()
        self.read_radio()
        if self.pings_performed == self.NUMBER_OF_REQUIRED_PINGS:
            # Transmit signal strength variability
            self.sfr.devices["Iridium"].commands["Transmit"]("TJ;SSV:" +
                                                             str(self.sfr.analytics.signal_strength_variability()))
            self.pings_performed += 1
        elif time.time() - self.last_ping >= self.DATAPOINT_SPACING:
            self.sfr.log_iridium(self.sfr.devices["Iridium"].commands["Geolocation"](),
                                 self.sfr.devices["Iridium"].commands["Signal Quality"]())  # Log Iridium data
            self.pings_performed += 1

    def read_radio(self) -> None:
        """
        Main logic for reading messages from radio in Science mode
        """
        super(Science, self).read_radio()
        # If primary radio is iridium and enough time has passed
        if self.sfr.PRIMARY_RADIO == "Iridium" and \
                time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, store them in sfr
            try:
                self.sfr.devices["Iridium"].nextMsg()
            except RuntimeError:
                pass #TODO: IMPLEMENT CONTINGENCIES
            self.last_iridium_poll_time = time.time()
        # If primary radio is aprs and enough time has passed
        elif self.sfr.PRIMARY_RADIO == "APRS" and \
                time.time() - self.last_iridium_poll_time > self.SECONDARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, store them in sfr
            try:
                self.sfr.devices["Iridium"].nextMsg()
            except RuntimeError:
                pass #TODO: IMPLEMENT CONTINGENCIES
            self.last_iridium_poll_time = time.time()
        # If APRS is on for whatever reason
        if self.sfr.devices["APRS"] is not None:
            self.sfr.APRS_RECEIVED_COMMAND.append(self.sfr.devices["APRS"].nextMsg())  # add aprs messages to sfr
            # commands will be executed in the mode.py's super method for execute_cycle using a command executor

    def terminate_mode(self) -> None:
        super(Science, self).terminate_mode()
        pass
