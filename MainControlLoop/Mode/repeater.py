from MainControlLoop.Mode.mode import Mode
import time


class Repeater(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)
        self.conditions = {
            "Low Battery": False
        }

        self.PRIMARY_IRIDIUM_WAIT_TIME = 5 * 60  # wait time for iridium polling if iridium is main radio
        self.SECONDARY_IRIDIUM_WAIT_TIME = 20 * 60  # wait time for iridium polling if iridium is not main radio

    def __str__(self):
        return "Repeater"

    def start(self) -> None:
        super(Repeater, self).start()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")
        self.instruct["All Off"](exceptions=["Iridium", "APRS"])
        self.sfr.devices["APRS"].enable_digi()

    def check_conditions(self) -> bool:
        super(Repeater, self).check_conditions()

        return not self.conditions["Low Battery"]  # as long as the battery is still good

    # always returns charging. just read the comment in outreach mode's switch_mode, I don't feel like writing it here again
    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        return self.sfr.modes_list["Charging"]

    def update_conditions(self):
        super(Repeater, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD

    def execute_cycle(self) -> None:
        self.read_radio()
        super(Repeater, self).execute_cycle()
        self.sfr.dump()  # Log changes

    def read_radio(self):
        """
        Main logic for reading messages from radio in Repeater mode
        """
        super(Repeater, self).read_radio()
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
            self.sfr.vars.APRS_RECEIVED_COMMAND.append(self.sfr.devices["APRS"].read())  # add aprs messages to sfr
            # commands will be executed in the mode.py's super method for execute_cycle using a command executor

    def terminate_mode(self) -> None:
        self.sfr.devices["APRS"].disable_digi()
        super(Repeater, self).terminate_mode()
        pass
