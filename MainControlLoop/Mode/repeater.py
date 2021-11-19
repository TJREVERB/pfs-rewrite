from MainControlLoop.Mode.mode import Mode
import time

class Repeater(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)
        self.conditions = {
            "Low Battery": False
        }

        self.PRIMARY_IRIDIUM_WAIT_TIME = 5*60  # wait time for iridium polling if iridium is main radio
        self.SECONDARY_IRIDIUM_WAIT_TIME = 20*60  # wait time for iridium polling if iridium is not main radio

    def __str__(self):
        return "Repeater"

    def start(self) -> None:
        super(Repeater, self).start()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")
        self.instruct["All Off"](exceptions=["Iridium", "APRS"])
        # TODO: TURN ON DIGIPEATING

    def check_conditions(self) -> bool:
        super(Repeater, self).check_conditions()
        if not self.conditions["Low Battery"]:  # if not low battery
            return True  # keep in current mode
        else:
            self.switch_mode("Charging")
            return False  # switch modes

    def update_conditions(self):
        super(Repeater, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD
        
    def execute_cycle(self) -> None:
        super(Repeater, self).execute_cycle()
        self.read_radio()
        self.sfr.dump()  # Log changes

    def read_radio(self):
        """
        Main logic for reading messages from radio in Repeater mode
        """
        super(Repeater, self).read_radio()
        # If primary radio is iridium and enough time has passed
        if self.sfr.PRIMARY_RADIO == "Iridium" and \
           time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, should be in the form of a list
            iridium_messages = self.sfr.devices["Iridium"].listen()
            # Append messages to IRIDIUM_RECEIVED_COMMAND
            self.sfr.IRIDIUM_RECEIVED_COMMAND = self.sfr.IRIDIUM_RECEIVED_COMMAND + iridium_messages
        # If primary radio is aprs and enough time has passed
        elif self.sfr.PRIMARY_RADIO == "APRS" and \
             time.time() - self.last_iridium_poll_time > self.SECONDARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, should be in the form of a list
            iridium_messages = self.sfr.devices["Iridium"].listen()
            # Append messages to IRIDIUM_RECEIVED_COMMAND
            self.sfr.IRIDIUM_RECEIVED_COMMAND = self.sfr.IRIDIUM_RECEIVED_COMMAND + iridium_messages
        # If APRS is on for whatever reason
        if self.sfr.devices["APRS"] is not None:
            self.sfr.APRS_RECEIVED_COMMAND.append(self.sfr.devices["APRS"].listen())  # add aprs messages to sfr
            # commands will be executed in the mode.py's super method for execute_cycle using a command executor

    def terminate_mode(self) -> None:
        # TODO: write to APRS to turn off digipeating
        super(Repeater, self).terminate_mode()
        pass
