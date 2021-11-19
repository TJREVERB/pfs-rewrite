from MainControlLoop.Mode.mode import Mode
import time


class Outreach(Mode):
    def __init__(self, sfr):
        super().__init__(sfr)

        self.conditions = {
            "Low Battery": False
        }
        self.limited_command_registry = {
            # Reads and transmits battery voltage
            "BVT": lambda: self.sfr.devices["APRS"].write("TJ;" + str(self.sfr.eps.telemetry["VBCROUT"]())),
            # Transmit total power draw of connected components
            "PWR": lambda: self.sfr.devices["APRS"].write("TJ;" + str(self.sfr.eps.total_power(3)[0])),
            # Calculate and transmit Iridium signal strength variability
            "SSV": lambda: self.sfr.devices["APRS"].write("TJ;SSV:" + str(self.sfr.signal_strength_variability())),
            # Transmit current solar panel production
            "SOL": lambda: self.sfr.devices["APRS"].write("TJ;SOL:" + str(self.sfr.eps.solar_power())),
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
        if self.conditions["Low Battery"]:
            self.switch_mode("Charging")
            return False
        else:
            return True

    def update_conditions(self) -> None:
        super(Outreach, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() > self.sfr.LOWER_THRESHOLD

    def execute_cycle(self) -> None:
        super(Outreach, self).execute_cycle()
        self.read_radio()

    def read_radio(self) -> None:
        """
        Main logic for reading messages from radio in Outreach mode
        """
        super(Outreach, self).read_radio()
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
        super(Outreach, self).terminate_mode()
        pass
