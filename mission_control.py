import os
import traceback
import time
from MainControlLoop.main_control_loop import MainControlLoop
from lib.exceptions import *
from lib.registry import StateFieldRegistry
from Drivers.transmission_packet import UnsolicitedData, UnsolicitedString


class MissionControl:
    SIGNAL_THRESHOLD = 2

    def __init__(self):
        try:
            self.sfr = StateFieldRegistry()
            self.mcl = MainControlLoop(self.sfr)
            self.error_dict = {
                APRSError: self.aprs_troubleshoot,
                IridiumError: self.iridium_troubleshoot,
                EPSError: self.eps_troubleshoot,
                IMUError: self.imu_troubleshoot,
                BatteryError: self.battery_troubleshoot,
                AntennaError: self.antenna_troubleshoot,
                HighPowerDrawError: self.high_power_draw_troubleshoot,
            }
        except Exception as e:
            self.testing_mode(e)  # TODO: change this for real pfs

    def get_traceback(self):
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
            self.mcl.start()  # initialize everything for mcl run
        except Exception as e:
            self.testing_mode(e)
        while True:  # Run forever
            try:
                print("----------------------------------- NEW MCL ITERATION --------------------------------------")
                self.mcl.iterate()  # Run a single iteration of MCL
            except Exception as e:  # If a problem happens (entire pfs is wrapped to raise CustomExceptions)
                if type(e) in self.error_dict:
                    try:
                        self.error_dict[type(e)](e)  # tries to troubleshoot
                        continue  # Move on with MCL if troubleshooting solved problem (no additional exception)
                    except IridiumError as e:
                        self.testing_mode(e)  # temporary for testing
                        # self.safe_mode_aprs(e)  <-- add this in before deployment
                    except Exception as e:
                        self.testing_mode(e)  # troubleshooting fails
                elif type(e) == KeyboardInterrupt:
                    self.testing_mode(e)
                else:  # built in exception leaked
                    self.testing_mode(e)
            else:  # dont want to force run this after potential remote code exec session
                for message_packet in self.sfr.vars.transmit_buffer:  # TODO: FIX IF ONE RADIO IS LOCKED OFF
                    if message_packet.get_packet_age() > self.sfr.vars.PACKET_AGE_LIMIT:  # switch radios
                        try:
                            self.error_dict[IridiumError](None)
                        except Exception:
                            if "APRS" in self.sfr.vars.LOCKED_OFF_DEVICES:
                                self.sfr.vars.LOCKED_OFF_DEVICES.remove("APRS")
                            self.sfr.set_primary_radio("APRS", True)
                            self.sfr.devices["APRS"].transmit(UnsolicitedString("PRIMARY RADIO SWITCHED"))

    def aprs_troubleshoot(self, e: CustomException):
        self.sfr.reboot("APRS")
        self.sfr.devices["APRS"].functional()

    def iridium_troubleshoot(self, e: CustomException):
        print(self.get_traceback())  # TODO: DEBUG
        self.sfr.reboot("Iridium")
        self.sfr.devices["Iridium"].functional()  # Raises error if fails

    def eps_troubleshoot(self, e: CustomException):
        # EPS will reset automatically after a while,
        # this ensures the python files don't get corrupted when that happens
        exit()

    def imu_troubleshoot(self, e: CustomException):
        # TODO: power cycle first
        self.sfr.reboot("IMU")
        try:
            self.sfr.devices["IMU"].functional()
        except IMUError:
            result = self.sfr.lock_device_off("IMU")
            if result:
                unsolicited_packet = UnsolicitedString("IMU failure: locked off IMU")
            else:
                unsolicited_packet = UnsolicitedString("IMU failure: locked on so no action taken")
            self.sfr.command_executor.transmit(unsolicited_packet)

    def battery_troubleshoot(self, e: CustomException):
        # EPS will reset automatically after a while,
        # this ensures the python files don't get corrupted when that happens
        exit()
    
    def antenna_troubleshoot(self, e: CustomException):
        self.sfr.reboot("Antenna Deployer")
        self.sfr.devices["Antenna Deployer"].functional()
    
    def high_power_draw_troubleshoot(self, e: CustomException):
        exit()
        # EPS will reset automatically after a while which will reset busses
        # this ensures the python files don't get corrupted when that happens

    def testing_mode(self, e: Exception):
        """
        DEBUG ONLY!!!
        Print current mode, values of sfr, exception's repr
        Then cleanly exit
        """
        print("ERROR!!!")
        print(f"Currently in {type(self.sfr.MODE).__name__}")
        print("State field registry fields:")
        print(self.sfr.vars.to_dict())
        print("Exception: ")
        print(repr(e))
        print(self.get_traceback())
        self.sfr.all_off()
        self.sfr.clear_logs()
        exit(1)

    def safe_mode(self, e: Exception):  # wrapper func for iridium or aprs safe mode
        safe_mode_func = self.get_correct_safe_mode()
        safe_mode_func(e)

    def get_correct_safe_mode(self):
        try:
            self.sfr.power_on("Iridium")
            self.sfr.devices["Iridium"].functional()
        except IridiumError:
            pass
        else:
            sent_successfully = False
            # keeps trying until we successfully transmit the fact that we have gone to iridium safe mode
            while not sent_successfully:
                try:
                    self.sfr.devices["Iridium"].transmit(UnsolicitedString("Iridium safe mode enabled"))
                except NoSignalException:
                    pass
                else:
                    sent_successfully = True
            return self.safe_mode_iridium

        try:
            self.sfr.power_on("APRS")
            self.sfr.devices["APRS"].functional()
            self.sfr.devices["APRS"].transmit(UnsolicitedString("APRS safe mode enabled"))
        except APRSError:
            print("L :(")
            exit()  # PFS team took an L
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
        self.sfr.devices["Iridium"].transmit(UnsolicitedString(repr(e)))
        self.sfr.set_primary_radio("Iridium")
        self.sfr.command_executor.GCS(UnsolicitedData("GCS"))  # transmits down the encoded SFR
        while self.sfr.vars.enter_safe_mode:
            if self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
                self.sfr.devices["Iridium"].next_msg()
            for message in self.sfr.vars.command_buffer:
                self.sfr.command_executor.primary_registry[message.command_string](message)
            
            if self.sfr.check_lower_threshold():  # if battery is low
                print("cry")
                self.sfr.devices["Iridium"].transmit(UnsolicitedString("Sat low battery, sleeping for 5400 seconds :("))
                self.sfr.power_off("Iridium")
                self.sfr.sleep(5400)  # charge for one orbit
                self.sfr.power_on("Iridium")

    def safe_mode_aprs(self, e: Exception):
        self.sfr.vars.enter_safe_mode = True
        self.sfr.devices["APRS"].transmit(UnsolicitedString(repr(e)))
        self.sfr.set_primary_radio("APRS")
        self.sfr.command_executor.GCS(UnsolicitedData("GCS"))  # transmits down the encoded SFR
        while self.sfr.vars.enter_safe_mode:
            self.sfr.devices["APRS"].next_msg()

            for message in self.sfr.vars.command_buffer:
                self.sfr.command_executor.primary_registry[message.command_string](message)

            if self.sfr.check_lower_threshold():
                print("cry")
                self.sfr.power_off("APRS")
                self.sfr.sleep(5400)  # charge for one orbit
                self.sfr.power_on("APRS")


if __name__ == "__main__":
    mission_control = MissionControl()
    mission_control.main()
