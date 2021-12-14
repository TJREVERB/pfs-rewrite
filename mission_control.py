import os
import traceback
import sys
import time
from MainControlLoop.main_control_loop import MainControlLoop
from MainControlLoop.lib.exceptions import *


class MissionControl:
    SIGNAL_THRESHOLD = 2

    def __init__(self):
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
    
    def get_traceback(self, e: Exception):
        tb = traceback.extract_stack(sys.exc_info()[2])

    def main(self):
        self.mcl.start()
        while True:  # Run forever
            try:
                try:
                    self.mcl.iterate()  # Run a single iteration of MCL
                except Exception as e:  # If a problem happens (entire pfs is wrapped to raise CustomExceptions)
                    if e == KeyboardInterrupt:  # If we ended the program
                        raise  # Raise up to next try-except block
                    elif type(e) in self.error_dict:
                        self.error_dict[type(e)](e)
                    elif type(e) == LogicalError:
                        raise  # We shouldn't troubleshoot a problem with high level code
                    else:  # built in error
                        raise
                    continue  # Move on with MCL if troubleshooting solved problem (no additional exception)
                # If a leak happens (impossible), exception will travel up to next try-except block (safe mode)
            except Exception as e:  # If another exception happens during troubleshooting (troubleshooting fails)
                if type(e) == KeyboardInterrupt:  # If we ended the program
                    self.sfr.clear_logs()  # Reset sfr
                    exit(0)  # Cleanly exit
                else:  # If error is genuine
                    # self.safe_mode(e)  # Safe mode to allow ground to solve the problem
                    self.testing_mode(e)  # DEBUG

    def aprs_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def iridium_troubleshoot(self, e: CustomException):
        print(self.get_traceback(e))
        self.turn_off("Iridium")
        time.sleep(1)
        self.turn_on("Iridium")
        time.sleep(5)
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

    def turn_on(self, component):
        if self.sfr.devices[component] is not None:  # if component is already on, stop method from running further
            return None
        if self.sfr.vars.LOCKED_DEVICES[component] is True:  # if component is locked, stop method from running further
            return None

        self.sfr.eps.commands["Pin On"](component)  # turns on component
        self.sfr.devices[component] = self.sfr.component_to_class[component](
            self.sfr)  # registers component as on by setting component status in sfr to object instead of None
        if component in self.sfr.component_to_serial:  # see if component has a serial converter to open
            serial_converter = self.sfr.component_to_serial[component]  # gets serial converter name of component
            self.sfr.eps.commands["Pin On"](serial_converter)  # turns on serial converter
            self.sfr.serial_converters[serial_converter] = True  # sets serial converter status to True (on)

        if component == "APRS":
            self.sfr.devices[component].disable_digi()
        if component == "IMU":
            self.sfr.devices[component].start()

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    def turn_off(self, component):
        if self.sfr.devices[component] is None:  # if component is off, stop method from running further.
            return None
        if self.sfr.vars.LOCKED_DEVICES[component] is True:  # if component is locked, stop method from running further
            return None

        if component == "Iridium" and self.sfr.devices[
            "Iridium"] is not None:  # Read in MT buffer to avoid wiping commands when mode switching
            try:
                self.sfr.devices[component].next_msg()
            except Exception as e:
                print(e)

        self.sfr.devices[component] = None  # sets device object in sfr to None instead of object
        self.sfr.eps.commands["Pin Off"](component)  # turns component off
        if component in self.sfr.component_to_serial:  # see if component has a serial converter to close
            # Same suggestion as for __turn_on_component
            serial_converter = self.sfr.component_to_serial[component]  # get serial converter name for component
            self.sfr.eps.commands["Pin Off"](serial_converter)  # turn off serial converter
            self.sfr.serial_converters[serial_converter] = False  # sets serial converter status to False (off)

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
        exit(1)

    def get_other_radio(self, current_radio):
        if current_radio == "Iridium":
            return "APRS"
        else:
            return "Iridium"

    def safe_mode(self, e: Exception):
        """
        Continiously listen for messages from main radio
        if there is message, attempt to exec method
        Should only switch back to mcl from confirmation from ground
        Should we put something to attempt to switch back to mcl if too much time passed?
        """

        is_working_radio = False
        for _ in range(2):
            try:
                self.sfr.turn_on(self.sfr.vars.PRIMARY_RADIO)
                self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit(repr(e))
            except Exception as e:
                self.sfr.vars.PRIMARY_RADIO = self.get_other_radio(self.sfr.vars.PRIMARY_RADIO)
            else:
                is_working_radio = True
                break
        if not is_working_radio:
            os.system("sudo reboot")  # Pfs team took an L

        troubleshooting_completed = False
        while not troubleshooting_completed:
            try:
                if self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
                    self.sfr.devices["Iridium"].next_msg()
                for messages in self.sfr.command_buffer:
                    if messages.command_string == "":  # idk:
                        troubleshooting_completed = True
                        break
                    elif messages.command_string in self.sfr.command_executor.primary_registry:
                        self.sfr.command_executor.primary_registry[messages.command_string](messages)
                    else:
                        exec(f"{messages.command_string}")
            except:  # add specific errors that would pertain to iridium not working
                os.system("sudo reboot")

    def charge(self):
        pass


if __name__ == "__main__":
    mission_control = MissionControl()
    mission_control.main()
