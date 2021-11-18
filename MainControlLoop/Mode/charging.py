from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.outreach import Outreach
from MainControlLoop.Mode.science import Science
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
        if self.conditions["Low Battery"]:  # if voltage is less than upper limit
            return True
        else:
            return False

    def update_conditions(self) -> None:
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

    def switch_modes(self):
        super(Charging, self).switch_modes()
        if self.conditions["Science Mode Status"]:  # science mode is complete
            return Outreach(self.sfr)
        else:
            return Science(self.sfr)  # does science mode if not done

    def terminate_mode(self):
        super(Charging, self).terminate_mode()
        self.instruct["Pin Off"](self.sfr.primary_radio)

