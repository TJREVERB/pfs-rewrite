from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.iridium import Iridium
import time


class Comms():
    command_registry = {

    }
    limited_command_registry = {

    }

    def __init__(self, sfr):
        self.sfr = sfr
        self.last_iridium_time = -1
        self.IRIDIUM_TIME_DELAY = 5
        self.prefix = "TEST"

    def check_aprs_message(self, message):
        # checks if the aprs message is a command from us
        if(len(message) > len(self.prefix) and message[:len(self.prefix)] == self.prefix):
            return True
        else:
            return False

    def read(self):

        if self.sfr.PRIMARY_RADIO == Iridium:
            if(time.time()-self.last_iridium_time > self.IRIDIUM_TIME_DELAY):
                message = self.sfr.PRIMARY_RADIO.read()
                if(message in self.command_registry.keys()):  # execute message
                    self.command_registry[message]()
                else:
                    # error handling
                    pass

        elif self.sfr.PRIMARY_RADIO == APRS:
            message = self.sft.PRIMARY_RADIO.read()
            if(self.check_aprs_message(message)):
                if(message in self.command_registry.keys()):
                    self.command_registry[message]()
                else:
                    # error handle
            else:
                if(message in self.limited_command_registry.keys()):
                    self.command_registry[message]()
                else:
                    # error handle

    def write(self):
        pass
