from MainControlLoop.Mode.mode import Mode
import time


class Science(Mode):
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
            "Low Battery": False,
            "Iridium Status": True  # if iridium works (not locked off), True
        }

        self.PRIMARY_IRIDIUM_WAIT_TIME = 5 * 60  # wait time for iridium polling if iridium is main radio
        self.SECONDARY_IRIDIUM_WAIT_TIME = 20 * 60  # wait time for iridium polling if iridium is not main radio

    def __str__(self):
        return "Science"

    def start(self) -> None:
        super(Science, self).start()
        if self.sfr.vars["PRIMARY_RADIO"] == "APRS":
            self.instruct["Pin On"]("APRS")
        self.instruct["Pin On"]("Iridium")
        self.instruct["All Off"](exceptions=["APRS", "Iridium"])
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.sfr.vars.LOWER_THRESHOLD
        self.conditions["Collection Complete"] = self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS
        self.conditions["Iridium Status"] = self.sfr.devices["Iridium Status"] is not None

    def check_conditions(self) -> bool:
        super(Science, self).check_conditions()

        return (not self.conditions["Low Battery"]) and (not self.conditions["Collection Complete"])

    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        return self.sfr.modes_list["Charging"]

    def update_conditions(self) -> None:
        super(Science, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.sfr.vars.LOWER_THRESHOLD
        self.conditions["Collection Complete"] = self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS
        self.conditions["Iridium Status"] = self.sfr.devices["Iridium Status"] is not None

    def execute_cycle(self) -> None:
        self.read_radio()
        super(Science, self).execute_cycle()

        if self.pings_performed == self.NUMBER_OF_REQUIRED_PINGS: # We shouldnt do this tbh
            # Transmit signal strength variability
            self.sfr.devices["Iridium"].commands["Transmit"]("TJ;SSV:" +
                                                             str(self.sfr.analytics.signal_strength_variability()))
            self.pings_performed += 1 
        elif time.time() - self.last_ping >= self.DATAPOINT_SPACING:
            self.sfr.log_iridium(self.sfr.devices["Iridium"].GEO_C(),
                                 self.sfr.devices["Iridium"].RSSI())  # Log Iridium data
            self.pings_performed += 1

    def read_radio(self) -> None:
        """
        Main logic for reading messages from radio in Science mode
        """
        super(Science, self).read_radio()
        # If primary radio is iridium and enough time has passed
        if self.sfr.vars.PRIMARY_RADIO == "Iridium" and \
                time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, store them in sfr
            try:
                self.sfr.devices["Iridium"].next_msg()
            except RuntimeError:
                pass  # TODO: IMPLEMENT CONTINGENCIES
            self.last_iridium_poll_time = time.time()
        # If primary radio is aprs and enough time has passed
        elif self.sfr.vars.PRIMARY_RADIO == "APRS" and \
                time.time() - self.last_iridium_poll_time > self.SECONDARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, store them in sfr
            try:
                self.sfr.devices["Iridium"].next_msg()
            except RuntimeError:
                pass  # TODO: IMPLEMENT CONTINGENCIES
            self.last_iridium_poll_time = time.time()
        # If APRS is on for whatever reason
        if self.sfr.devices["APRS"] is not None:
            self.sfr.vars.APRS_RECEIVED_COMMAND.append(self.sfr.devices["APRS"].next_msg())  # add aprs messages to sfr
            # commands will be executed in the mode.py's super method for execute_cycle using a command executor

    def terminate_mode(self) -> None:
        super(Science, self).terminate_mode()
        pass
