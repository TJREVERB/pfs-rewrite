import traceback
from MainControlLoop.main_control_loop import MainControlLoop
from lib.exceptions import *
from lib.registry import StateFieldRegistry
from Drivers.transmission_packet import UnsolicitedData, UnsolicitedString


def get_traceback():
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


class MissionControl:
    SIGNAL_THRESHOLD = 2

    def __init__(self):
        #try:
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
        #except Exception as e:
        #    self.testing_mode(e)  # TODO: change this for real pfs

    def main(self):
        try:
            self.mcl.start()  # initialize everything for mcl run
        except Exception as e:
            self.testing_mode(e)
        while True:  # Run forever
            if self.sfr.vars.ENABLE_SAFE_MODE:
                print("safe mode iteration")
                self.safe_mode()
            else:
                print("=================================================== ~ MCL ITERATION ~ ===================================================")
                try:
                    self.mcl.iterate()  # Run a single iteration of MCL
                except Exception as e:  # If a problem happens
                    if not self.troubleshoot(e):  # If built-in troubleshooting fails
                        self.testing_mode(e)  # Debug
                        # self.error_handle(e)  # Handle error, uncomment when done testing low level things
            # If any packet has been in the queue for too long and APRS is not locked off, switch primary radio
            if any([i.get_packet_age() > self.sfr.vars.PACKET_AGE_LIMIT for i in self.sfr.vars.transmit_buffer]):
                if "APRS" not in self.sfr.vars.LOCKED_OFF_DEVICES:
                    self.sfr.set_primary_radio("APRS", True)
                    self.sfr.devices["APRS"].transmit(UnsolicitedString("PRIMARY RADIO SWITCHED"))

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
        print(get_traceback())
        self.sfr.all_off()
        self.sfr.clear_logs()
        exit(1)

    def troubleshoot(self, e: Exception) -> bool:
        """
        Attempts to troubleshoot error
        :param e: error to troubleshoot
        :return: whether troubleshooting worked
        """
        try:
            self.error_dict[type(e)](e)  # tries to troubleshoot, raises exception if error not in dict
            return True
            # Move on with MCL if troubleshooting solved problem (no additional exception)
        except Exception:
            return False
            self.testing_mode(e)  # troubleshooting fails
            # self.error_handle(e) <-- uncomment when done testing lower level things

    def error_handle(self, e: Exception):
        """
        If an error was unresolved, notifies ground and sets up satellite to enter safe mode
        """
        self.sfr.vars.ENABLE_SAFE_MODE = True
        self.sfr.all_off()
        try:  # Try to set up for iridium first
            if "Iridium" in self.sfr.vars.LOCKED_OFF_DEVICES:  # If iridium is locked off
                raise IridiumError()  # Skip to trying aprs
            self.sfr.set_primary_radio("Iridium", True)
            self.sfr.devices["Iridium"].functional()
            # keeps trying until we successfully transmit the fact that we have gone to iridium safe mode
            while True:
                try:
                    self.sfr.devices["Iridium"].transmit(UnsolicitedString("SAFE MODE: Iridium primary radio"))
                    break
                except NoSignalException:
                    continue
        except IridiumError:  # If iridium fails
            try:  # Try to set up for aprs
                if "APRS" in self.sfr.vars.LOCKED_OFF_DEVICES:  # If aprs is locked off
                    raise APRSError()  # Skip to exiting and waiting for watchdog reset
                self.sfr.set_primary_radio("APRS", True)
                self.sfr.devices["APRS"].functional()
                self.sfr.devices["APRS"].transmit(UnsolicitedString("SAFE MODE: APRS primary radio"))
            except APRSError:  # If aprs fails
                print("L :(")
                exit()  # PFS team took an L
        self.sfr.command_executor.transmit(UnsolicitedString(repr(e)))
        self.sfr.command_executor.GCS(UnsolicitedData("GCS"))  # transmits down the encoded SFR

    def safe_mode(self):
        """
        Runs a single iteration of safe mode
        Continiously listen for messages from main radio
        if there is message, attempt to exec method
        Should only switch back to mcl from confirmation from ground
        """
        if self.sfr.devices["Iridium"] is not None:  # If iridium is on
            if self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
                self.sfr.devices["Iridium"].next_msg()  # Read
        if self.sfr.devices["APRS"] is not None:  # If aprs is on
            self.sfr.devices["APRS"].next_msg()  # Read

        for message in self.sfr.vars.command_buffer:  # Execute command buffer
            self.sfr.command_executor.primary_registry[message.command_string](message)

        if self.sfr.check_lower_threshold():  # if battery is low
            print("cry")
            self.sfr.command_executor.transmit(UnsolicitedString("Sat low battery, sleeping for 5400 seconds :("))
            self.sfr.power_off(self.sfr.vars.PRIMARY_RADIO)
            self.sfr.sleep(5400)  # charge for one orbit
            self.sfr.power_on(self.sfr.vars.PRIMARY_RADIO)

    def aprs_troubleshoot(self):
        self.sfr.vars.FAILURES.append("APRS")
        self.sfr.reboot("APRS")
        self.sfr.devices["APRS"].functional()
        self.sfr.vars.FAILURES.remove("APRS")

    def iridium_troubleshoot(self):
        print(get_traceback())  # TODO: DEBUG
        self.sfr.vars.FAILURES.append("Iridium")
        self.sfr.reboot("Iridium")
        self.sfr.devices["Iridium"].functional()  # Raises error if fails
        self.sfr.vars.FAILURES.remove("Iridium")

    def eps_troubleshoot(self):
        # EPS will reset automatically after a while,
        # this ensures the python files don't get corrupted when that happens
        exit()

    def imu_troubleshoot(self):
        self.sfr.vars.FAILURES.append("IMU")
        self.sfr.reboot("IMU")
        try:
            self.sfr.devices["IMU"].functional()
            self.sfr.vars.FAILURES.remove("IMU")
        except IMUError:
            result = self.sfr.lock_device_off("IMU")
            if result:
                unsolicited_packet = UnsolicitedString("IMU failure: locked off IMU")
            else:
                unsolicited_packet = UnsolicitedString("IMU failure: locked on so no action taken")
            self.sfr.command_executor.transmit(unsolicited_packet)

    def battery_troubleshoot(self):
        # EPS will reset automatically after a while,
        # this ensures the python files don't get corrupted when that happens
        exit()

    def antenna_troubleshoot(self):
        self.sfr.vars.FAILURES.append("Antenna Deployer")
        self.sfr.reboot("Antenna Deployer")
        self.sfr.devices["Antenna Deployer"].functional()
        self.sfr.vars.FAILURES.remove("Antenna Deployer")

    def high_power_draw_troubleshoot(self):
        exit()
        # EPS will reset automatically after a while which will reset busses
        # this ensures the python files don't get corrupted when that happens


if __name__ == "__main__":
    mission_control = MissionControl()
    mission_control.main()
