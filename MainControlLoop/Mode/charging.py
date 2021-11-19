from MainControlLoop.Mode.mode import Mode
import time


class Charging(Mode):
    def __init__(self, sfr):
        super(Charging, self).__init__(sfr)

        self.conditions = {
            "Science Mode Status": False,  # this is False if science mode is not complete
            "Low Battery": True  # don't want to shift out of charging prematurely
        }
        self.PRIMARY_IRIDIUM_WAIT_TIME = 5 * 60  # wait time for iridium polling if iridium is main radio
        self.SECONDARY_IRIDIUM_WAIT_TIME = 20 * 60  # wait time for iridium polling if iridium is not main radio

    def __str__(self):
        return "Charging"

    def start(self) -> None:
        super(Charging, self).start()
        self.instruct["Pin On"](self.sfr.primary_radio)  # turn on primary radio
        self.instruct["All Off"](exceptions=[self.sfr.primary_radio])  # turn off any not required devices

        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() <= self.UPPER_THRESHOLD
        self.conditions["Science Mode Status"] = self.sfr.SIGNAL_STRENGTH_VARIABILITY > -1

    def check_conditions(self) -> bool:
        super(Charging, self).check_conditions()
        if self.conditions["Low Battery"]:  # if voltage is less than upper limit
            return True  # stay in charging
        elif self.conditions["Science Mode Status"]:  # if science mode is complete
            self.switch_mode("Outreach")
            return False
        else:  # science mode not done
            self.switch_mode("Science")  # go back to science mode
            return False

    def update_conditions(self) -> None:
        super(Charging, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() <= self.UPPER_THRESHOLD
        self.conditions["Science Mode Status"] = self.sfr.SIGNAL_STRENGTH_VARIABILITY > -1

    def execute_cycle(self) -> None:
        super(Charging, self).execute_cycle()
        self.read_radio()
        self.sfr.dump()  # Log changes

    def read_radio(self) -> None:
        """
        Main logic for reading messages from radio in Charging mode
        """
        super(Charging, self).read_radio()
        # If primary radio is iridium and enough time has passed
        if self.sfr.PRIMARY_RADIO == "Iridium" and \
                time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, should be in the form of a list
            iridium_messages = self.sfr.devices["Iridium"].nextMsg()
            # Append messages to IRIDIUM_RECEIVED_COMMAND
            self.sfr.IRIDIUM_RECEIVED_COMMAND = self.sfr.IRIDIUM_RECEIVED_COMMAND + iridium_messages
            self.last_iridium_poll_time = time.time()
        # If primary radio is aprs and enough time has passed
        elif self.sfr.PRIMARY_RADIO == "APRS" and \
                time.time() - self.last_iridium_poll_time > self.SECONDARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, should be in the form of a list
            iridium_messages = self.sfr.devices["Iridium"].nextMsg()
            # Append messages to IRIDIUM_RECEIVED_COMMAND
            self.sfr.IRIDIUM_RECEIVED_COMMAND = self.sfr.IRIDIUM_RECEIVED_COMMAND + iridium_messages
            self.last_iridium_poll_time = time.time()
        # If APRS is on for whatever reason
        if self.sfr.devices["APRS"] is not None:
            self.sfr.APRS_RECEIVED_COMMAND.append(self.sfr.devices["APRS"].nextMsg())  # add aprs messages to sfr
            # commands will be executed in the mode.py's super method for execute_cycle using a command executor

    def terminate_mode(self) -> None:
        super(Charging, self).terminate_mode()
        pass
