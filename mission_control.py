import os
import traceback
import sys
import time
from MainControlLoop.main_control_loop import MainControlLoop
from MainControlLoop.lib.exceptions import *


class MissionControl:
    SIGNAL_THRESHOLD = 2

    def __init__(self):
        try:
            self.mcl = MainControlLoop()
            self.sfr = self.mcl.sfr
            self.error_dict = {
                APRSError: self.aprs_troubleshoot,
                IridiumError: self.iridium_troubleshoot,
                EPSError: self.eps_troubleshoot,
                RTCError: self.rtc_troubleshoot,
                IMUError: self.imu_troubleshoot,
                BatteryError: self.battery_troubleshoot,
                AntennaError: self.antenna_troubleshoot
            }
        except Exception as e:
            self.testing_mode(e)
    
    def get_traceback(self, e: Exception):
        tb = traceback.format_exc().split("\n")
        result = ""
        while len(tb) > 0:
            # Include parts of traceback which don't originate from wrapper
            if (line := tb[0].strip(" ")).startswith("File"):
                if not line.endswith("in wrapper"):
                    result += tb.pop(0) + "\n" + tb.pop(0) + "\n"
                else:
                    tb = tb[2:]
            else:  # If this line isn't part of traceback, add
                result += tb.pop(0) + "\n"
        return result

    def main(self):
        try:
            self.mcl.start()
        except Exception as e:
            self.testing_mode(e)
        while True:  # Run forever
            try:
                self.mcl.iterate()  # Run a single iteration of MCL
            except Exception as e:  # If a problem happens (entire pfs is wrapped to raise CustomExceptions)
                if type(e) in self.error_dict:
                    try:
                        self.error_dict[type(e)](e)  # tries to troubleshoot
                        continue  # Move on with MCL if troubleshooting solved problem (no additional exception)
                    except Exception as e:
                        self.testing_mode(e)  # troubleshooting fails
                elif type(e) == KeyboardInterrupt:
                    self.testing_mode(e)
                else:  # built in exception leaked
                    self.testing_mode(e)

    def aprs_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def iridium_troubleshoot(self, e: CustomException):
        print(self.get_traceback(e))
        self.sfr.instruct["Pin Off"]("Iridium")
        time.sleep(1)
        self.sfr.instruct["Pin On"]("Iridium")
        time.sleep(10)
        self.sfr.devices["Iridium"].functional()  # Raises error if fails

    def eps_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def rtc_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def imu_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def battery_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING
    
    def antenna_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def testing_mode(self, e: Exception):
        """
        DEBUG ONLY!!!
        Print current mode, values of sfr, exception's repr
        Then cleanly exit
        """
        print("ERROR!!!")
        print(f"Currently in {self.sfr.vars.MODE.__name__}")
        print("State field registry fields:")
        print(self.sfr.vars.to_dict())
        print("Exception: ")
        print(repr(e))
        print(self.get_traceback(e))
        self.sfr.turn_all_off()
        self.sfr.clear_logs()
        exit(1)

    def safe_mode(self, e: Exception):  # wrapper func for iridium or aprs safe mode
        safe_mode_func = self.get_correct_safe_mode()
        safe_mode_func(e)

    def get_correct_safe_mode(self):
        try:
            self.sfr.instruct["Pin On"]("Iridium")
            self.sfr.devices["Iridium"].transmit("Iridium safe mode enabled")
        except Exception:
            pass
        else:
            return self.safe_mode_iridium

        try:
            self.sfr.instruct["Pin On"]("APRS")
            self.sfr.devices["APRS"].transmit("APRS safe mode enabled")
        except Exception:
            os.system("sudo reboot")  # PFS team took an L
        else:
            return self.safe_mode_aprs

    def safe_mode_iridium(self, e: Exception):
        """
        Continiously listen for messages from main radio
        if there is message, attempt to exec method
        Should only switch back to mcl from confirmation from ground
        Precondition: iridium is functional
        """
        self.sfr.vars.enter_safe_mode = True
        self.sfr.devices["Iridium"].transmit(repr(e))
        while self.sfr.vars.enter_safe_mode:
            if self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
                self.sfr.devices["Iridium"].next_msg()
            for message in self.sfr.command_buffer:
                self.sfr.command_executor.primary_registry[message.command_string](message)

    def safe_mode_aprs(self, e: Exception):
        self.sfr.vars.enter_safe_mode = True
        self.sfr.devices["APRS"].transmit(repr(e))
        while self.sfr.vars.enter_safe_mode:
            if self.sfr.devices["APRS"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
                self.sfr.devices["APRS"].next_msg()

            for message in self.sfr.command_buffer:
                self.sfr.command_executor.primary_registry[message.command_string](message)

            if self.sfr.eps.telemetry["VBCROUT"]() < self.sfr.vars.LOWER_THRESHOLD:
                self.sfr.instruct["Pin Off"]("APRS")
                time.sleep(90*60)  # charge for one orbit
                self.sfr.instruct["Pin On"]("APRS")


if __name__ == "__main__":
    mission_control = MissionControl()
    mission_control.main()
