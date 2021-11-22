from MainControlLoop.Mode.mode import Mode
import time


class Outreach(Mode):
    def __init__(self, sfr):
        super().__init__(sfr)

        self.conditions = {
            "Low Battery": False
        }

        self.PRIMARY_IRIDIUM_WAIT_TIME = 5 * 60  # wait time for iridium polling if iridium is main radio
        self.SECONDARY_IRIDIUM_WAIT_TIME = 20 * 60  # wait time for iridium polling if iridium is not main radio

    def __str__(self):
        return "Outreach"

    def start(self) -> None:
        super(Outreach, self).start()
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")
        self.instruct["All Off"](exceptions=["Iridium", "APRS"])

    def check_conditions(self) -> bool:
        super(Outreach, self).check_conditions()

        return not (self.conditions["Low Battery"]) #as long as the battery is not low, we stay

    # This will always return charging mode, regardless of the conditions... even if check_conditions was previously true
    # If this is ever called when check_conditions was still true, there is probably a reason, so return a DIFFERENT mode
    def switch_mode(self):
        return self.sfr.modes_list["Charging"]  # suggest charging

    def update_conditions(self) -> None:
        super(Outreach, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() > self.sfr.vars.LOWER_THRESHOLD

    def execute_cycle(self) -> None:
        super(Outreach, self).execute_cycle()
        self.read_radio()

    def read_radio(self) -> None:
        """
        Main logic for reading messages from radio in Outreach mode
        """
        super(Outreach, self).read_radio()
        # If primary radio is iridium and enough time has passed
        if self.sfr.vars.PRIMARY_RADIO == "Iridium" and \
                time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, store them in sfr
            try:
                self.sfr.devices["Iridium"].next_msg()
            except RuntimeError:
                pass #TODO: IMPLEMENT CONTINGENCIES
            self.last_iridium_poll_time = time.time()
        # If primary radio is aprs and enough time has passed
        elif self.sfr.vars.PRIMARY_RADIO == "APRS" and \
                time.time() - self.last_iridium_poll_time > self.SECONDARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, should be in the form of a list
            iridium_messages = self.sfr.devices["Iridium"].next_msg()
            # Append messages to IRIDIUM_RECEIVED_COMMAND
            self.sfr.vars.IRIDIUM_RECEIVED_COMMAND = self.sfr.vars.IRIDIUM_RECEIVED_COMMAND + iridium_messages
            self.last_iridium_poll_time = time.time()
        # If APRS is on for whatever reason
        if self.sfr.devices["APRS"] is not None:
            self.sfr.vars.APRS_RECEIVED_COMMAND.append(self.sfr.devices["APRS"].next_msg())  # add aprs messages to sfr
            # commands will be executed in the mode.py's super method for execute_cycle using a command executor

    def terminate_mode(self) -> None:
        super(Outreach, self).terminate_mode()
        pass
