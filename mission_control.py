import os
import traceback
import time
from MainControlLoop.Mode.outreach.main_control_loop import MainControlLoop
from lib.exceptions import *
from lib.registry import StateFieldRegistry
from Drivers.transmission_packet import UnsolicitedData, UnsolicitedString


class MissionControl:
    SIGNAL_THRESHOLD = 2

    def __init__(self):
        try:
            self.sfr: StateFieldRegistry
            self.mcl = MainControlLoop()
            self.sfr = self.mcl.sfr
            #self.sfr: StateFieldRegistry
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
            self.testing_mode(e)

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
                    except IridiumError as e:
                        self.testing_mode(e)  # temporary for testing
                        # self.safe_mode_aprs(e)  <-- add this in before deployment
                    except APRSError as e:
                        self.testing_mode(e)  # temporary for testing
                        # self.safe_mode_iridium(e)  <-- add this in before deployment
                    except AntennaError as e:
                        self.testing_mode(e)  # temporary for testing
                        # self.safe_mode_iridium(e)  <-- add this in before deployment
                    except Exception as e:
                        self.testing_mode(e)  # troubleshooting fails
                elif type(e) == KeyboardInterrupt:
                    self.testing_mode(e)
                else:  # built in exception leaked
                    self.testing_mode(e)
            else:  # dont want to force run this after potential remote code exec session
                for message_packet in self.sfr.vars.transmit_buffer:
                    if message_packet.get_packet_age() > self.sfr.vars.PACKET_AGE_LIMIT:  # switch radios
                        self.sfr.power_off(self.sfr.vars.PRIMARY_RADIO)
                        self.sfr.vars.PRIMARY_RADIO = self.get_other_radio(self.sfr.vars.PRIMARY_RADIO)
                        self.sfr.power_on(self.sfr.vars.PRIMARY_RADIO)
                        # transmit radio switched to ground

    def get_other_radio(self, radio):
        if radio == "Iridium":
            return "APRS"
        else:
            return "Iridium"

    def aprs_troubleshoot(self, e: CustomException):
        self.sfr.reboot("APRS")
        self.sfr.devices["APRS"].functional()

    def iridium_troubleshoot(self, e: CustomException):
        print(self.get_traceback())
        self.sfr.power_off("Iridium")
        time.sleep(1)
        self.sfr.power_on("Iridium")
        time.sleep(10)
        self.sfr.devices["Iridium"].functional()  # Raises error if fails

    def eps_troubleshoot(self, e: CustomException):
        exit()  # EPS will reset automatically after a while, this ensures the python files don't get corrupted when that happens

    def imu_troubleshoot(self, e: CustomException):
        #TODO: power cycle first
        result = self.sfr.lock_device_off("IMU")
        if result:
            unsolicited_packet = UnsolicitedString("IMU failure: locked off IMU")
        else:
            unsolicited_packet = UnsolicitedString("IMU failure: locked on so no action taken")
        self.sfr.command_executor.transmit(unsolicited_packet)

    def battery_troubleshoot(self, e: CustomException):
        exit()  # EPS will reset automatically after a while, this ensures the python files don't get corrupted when that happens
    
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
            while not sent_successfully:  # keeps trying until we successfully transmit the fact that we have gone to iridium safe mode
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
        self.sfr.devices["Iridium"].transmit(UnsolicitedString(repr(e)))
        self.sfr.set_primary_radio("Iridium")
        self.sfr.command_executor.GCS(UnsolicitedData("GCS"))  # transmits down the encoded SFR
        while self.sfr.vars.enter_safe_mode:
            if self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
                self.sfr.devices["Iridium"].next_msg()
            for message in self.sfr.command_buffer:
                self.sfr.command_executor.primary_registry[message.command_string](message)
            
            if self.sfr.check_lower_threshold():
                self.sfr.power_off("Iridium")
                self.sfr.sleep(self.sfr.vars.ORBITAL_PERIOD)  # charge for one orbit
                self.sfr.power_on("Iridium")

    def safe_mode_aprs(self, e: Exception):
        self.sfr.vars.enter_safe_mode = True
        self.sfr.devices["APRS"].transmit(UnsolicitedString(repr(e)))
        self.sfr.set_primary_radio("APRS")
        self.sfr.command_executor.GCS(UnsolicitedData("GCS"))  # transmits down the encoded SFR
        while self.sfr.vars.enter_safe_mode:
            self.sfr.devices["APRS"].next_msg()

            for message in self.sfr.command_buffer:
                self.sfr.command_executor.primary_registry[message.command_string](message)

            if self.sfr.check_lower_threshold():
                self.sfr.power_off("APRS")
                self.sfr.sleep(self.sfr.vars.ORBITAL_PERIOD)  # charge for one orbit
                self.sfr.power_on("APRS")


if __name__ == "__main__":
    mission_control = MissionControl()
    mission_control.main()
