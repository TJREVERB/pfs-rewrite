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
        # TODO: THIS LEAVES THE APRS ON DURING CHARGING MODE IF IT IS PRIMARY, IS THIS INTENTIONAL?
        self.instruct["Pin On"](self.sfr.vars.PRIMARY_RADIO)  # turn on primary radio
        self.instruct["All Off"](exceptions=[self.sfr.vars.PRIMARY_RADIO])  # turn off any not required devices

        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() <= self.sfr.vars.UPPER_THRESHOLD
        self.conditions["Science Mode Status"] = self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY > -1

    def check_conditions(self) -> bool:
        super(Charging, self).check_conditions()  # in case we decide to add some super conditions later

        return self.conditions["Low Battery"]  # Stays in charging mode as long as battery is low

    def switch_mode(self):
        if self.conditions["Science Mode Status"]:  # if science mode is complete
            return self.sfr.modes_list["Outreach"]  # suggest outreach mode
        else:  # science mode not done
            return self.sfr.modes_list["Science"]  # suggest science mode

    def update_conditions(self) -> None:
        super(Charging, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() <= self.UPPER_THRESHOLD
        self.conditions["Science Mode Status"] = self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY > -1

    def execute_cycle(self) -> None:
        self.read_radio()  # Super will call execute_commands so we need to read the commands
        super(Charging, self).execute_cycle()

    def read_radio(self) -> None:
        """
        Main logic for reading messages from radio in Charging mode
        """
        super(Charging, self).read_radio()
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
        super(Charging, self).terminate_mode()
        pass
