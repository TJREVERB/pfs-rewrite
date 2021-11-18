from MainControlLoop.Mode.mode import Mode
import time


class Charging(Mode):
    def __init__(self, sfr):
        super(Charging, self).__init__(sfr)

        self.conditions = {
            "Science Mode Status": False,  # this is False if science mode is not complete
            "Low Battery": True  # don't want to shift out of charging prematurely
        }
        self.PRIMARY_IRIDIUM_WAIT_TIME = 5*60
        self.SECONDARY_IRIDIUM_WAIT_TIME = 20*60

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
            self.sfr.MODE = self.sfr.modes_list["Outreach"]  # go to outreach
            return False
        else:  # science mode not done
            self.sfr.MODE = self.sfr.modes_list["SCIENCE"]  # go back to science mode

    def update_conditions(self) -> None:
        super(Charging, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() <= self.UPPER_THRESHOLD
        self.conditions["Science Mode Status"] = self.sfr.SIGNAL_STRENGTH_VARIABILITY > -1

    def execute_cycle(self) -> None:
        super(Charging, self).execute_cycle()
        self.read_radio()
        self.sfr.dump()  # Log changes

    def read_radio(self):
        """
        Main logic for implementation to read messages from radio in Charging mode class
        """
        if self.sfr.primary_radio == "Iridium" :
            if(time.time()-self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME):
                iridium_messages = self.sfr.devices["Iridium"].listen()  # get all messages from iridium, should be in the form of a list
                for message in iridium_messages:
                    self.sfr.IRIDIUM_RECEIVED_COMMAND.append(message)
        elif(self.sfr.primary_radio == "APRS"):
            if(time.time()-self.last_iridium_poll_time > self.SECONDARY_IRIDIUM_WAIT_TIME):
                if(time.time()-self.last_iridium_poll_time > self.SECONDARY_IRIDIUM_WAIT_TIME):
                    iridium_messages = self.sfr.devices["Iridium"].listen()  # get all messages from iridium, should be in the form of a list
                    for message in iridium_messages:
                        self.sfr.IRIDIUM_RECEIVED_COMMAND.append(message)  # add iridium messages to sfr
            
            self.sfr.APRS_RECEIVED_COMMAND.append(self.sfr.devices["APRS".listen()])  # add aprs messages to sfr
            # commands will be executed in the mode.py's super method for execute_cycle using a command executer

    def terminate_mode(self):
        super(Charging, self).terminate_mode()
        pass

