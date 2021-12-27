import os
import traceback
import time
from MainControlLoop.main_control_loop import MainControlLoop
from lib.exceptions import *
from lib.registry import StateFieldRegistry
from Drivers.transmission_packet import TransmissionPacket


class MissionControl:
    SIGNAL_THRESHOLD = 2

    def __init__(self):
        try:
            self.mcl = MainControlLoop()
            self.sfr = self.mcl.sfr
            self.sfr: StateFieldRegistry
            self.error_dict = {
                APRSError: self.aprs_troubleshoot,
                IridiumError: self.iridium_troubleshoot,
                EPSError: self.eps_troubleshoot,
                RTCError: self.rtc_troubleshoot,
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
                        self.sfr.instruct["Pin Off"](self.sfr.vars.PRIMARY_RADIO)
                        self.sfr.vars.PRIMARY_RADIO = self.get_other_radio(self.sfr.vars.PRIMARY_RADIO)
                        self.sfr.instruct["Pin On"](self.sfr.vars.PRIMARY_RADIO)
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
        self.sfr.instruct["Pin Off"]("IMU")
        # TODO: transmit down a notification

    def battery_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING
    
    def antenna_troubleshoot(self, e: CustomException):
        self.sfr.instruct["Reboot"]("Antenna Deployer")
        self.sfr.devices["Antenna Deployer"].functional()
        # TODO: transmit down a notification
    
    def high_power_draw_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

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
        self.sfr.devices["Iridium"].transmit_raw(repr(e))
        self.sfr.set_primary_radio("Iridium")
        self.sfr.command_executor.GCS(TransmissionPacket("GCS", [], 0))  # transmits down the encoded SFR
        while self.sfr.vars.enter_safe_mode:
            if self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
                self.sfr.devices["Iridium"].next_msg()
            for message in self.sfr.command_buffer:
                self.sfr.command_executor.primary_registry[message.command_string](message)

    def safe_mode_aprs(self, e: Exception):
        self.sfr.vars.enter_safe_mode = True
        self.sfr.devices["APRS"].transmit_raw(repr(e))
        self.sfr.set_primary_radio("APRS")
        self.sfr.command_executor.GCS(TransmissionPacket("GCS", [], 0))  # transmits down the encoded SFR
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
