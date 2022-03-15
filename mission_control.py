import traceback
from MainControlLoop.main_control_loop import MainControlLoop
from lib.exceptions import *
from lib.registry import StateFieldRegistry
from lib.clock import Clock
from Drivers.transmission_packet import UnsolicitedData, UnsolicitedString


def get_traceback() -> str:
    """
    Removes wrapper lines from traceback for readability
    :return: traceback
    :rtype: str
    """
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
    """
    Manager class for entire pfs
    Runs mcl, handles errors, contains code for safe mode
    """
    SIGNAL_THRESHOLD = 2

    def __init__(self):
        """
        Attempts to initialize everything
        If an error happens, testing mode is triggered
        """
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
            self.transmission_queue_clock = Clock(10)
        except Exception as e:
            if not self.troubleshoot(e):  # If built-in troubleshooting fails
                self.error_handle(e)  # Handle error

    def main(self):
        """
        Run pfs
        """
        try:
            self.mcl.start()  # initialize everything for mcl run
        except Exception as e:
            self.testing_mode(e)
        while True:  # Run forever
            if self.sfr.vars.ENABLE_SAFE_MODE:
                print("safe mode iteration")
                self.safe_mode()
            else:
                print("=================================================== ~ MCL ITERATION ~ "
                      "===================================================", file = open("pfs-output.txt", "a"))
                try:
                    self.mcl.iterate()  # Run a single iteration of MCL
                except Exception as e:  # If a problem happens
                    print("Caught exception (printed from mission_control line 75) ", e, file = open("pfs-output.txt", "a"))
                    if not self.troubleshoot(e):  # If built-in troubleshooting fails
                        self.error_handle(e)  # Handle error, uncomment when done testing low level things
                    # Move on with MCL if troubleshooting solved problem (no additional exception)
            # If any packet has been in the queue for too long and APRS is not locked off, switch primary radio
            if any([i.get_packet_age() > self.sfr.vars.PACKET_AGE_LIMIT for i in self.sfr.vars.transmit_buffer]):
                if "APRS" not in self.sfr.vars.LOCKED_OFF_DEVICES:
                    self.sfr.set_primary_radio("APRS", True)
                    self.sfr.command_executor.transmit(UnsolicitedString("PRIMARY RADIO SWITCHED"))

    def testing_mode(self, e: Exception):
        """
        DEBUG ONLY!!!
        Print current mode, values of sfr, exception's repr
        Then cleanly exit
        """
        print("ERROR!!!", file = open("pfs-output.txt", "a"))
        try:
            print(f"Currently in {type(self.sfr.MODE).__name__}", file = open("pfs-output.txt", "a"))
            print("State field registry fields:", file = open("pfs-output.txt", "a"))
            print(self.sfr.vars.to_dict(), file = open("pfs-output.txt", "a"))
            self.sfr.clear_logs()
        except Exception:
            print("Error in sfr init, unable to clear logs", file = open("pfs-output.txt", "a"))
        print("Exception: " + repr(e), file = open("pfs-output.txt", "a"))
        print("Traceback:\n" + get_traceback(), file = open("pfs-output.txt", "a"))
        try:
            self.sfr.all_off()
        except Exception:
            print("PDM power cycle failed! Manually power cycle before next testing run", file = open("pfs-output.txt", "a"))
        try:
            self.sfr.clear_logs()
        except Exception:
            print("Log clearing failed! Consider manually clearing logs before next run", file = open("pfs-output.txt", "a"))
        exit(1)

    def troubleshoot(self, e: Exception) -> bool:
        """
        Attempts to troubleshoot error
        :param e: error to troubleshoot
        :type e: Exception
        :return: whether troubleshooting worked
        :rtype: bool
        """
        try:
            print("Attempting troubleshoot", file = open("pfs-output.txt", "a"))
            print(self.error_dict[type(e)], file = open("pfs-output.txt", "a"))
            self.error_dict[type(e)]()  # tries to troubleshoot, raises exception if error not in dict
            return True
        except Exception:  # If .functional doesn't solve the problem, raises an error
            return False

    def error_handle(self, e: Exception):
        """
        If an error was unresolved, notifies ground and sets up satellite to enter safe mode
        :param e: error which triggered safe mode
        :type e: Exception
        """
        self.sfr.vars.ENABLE_SAFE_MODE = True
        self.sfr.all_off(safe=True)
        try:  # Try to set up for iridium first
            # Try to switch primary radio, returns False if Iridium is locked off
            if not self.sfr.set_primary_radio("Iridium"):  # also sets primary if possible
                raise IridiumError()  # If primary radio switch failed, don't run further
            self.sfr.devices["Iridium"].functional()  # Test if iridium is functional
            # Notify ground that we're in safe mode with iridium primary radio
            self.sfr.reboot("Iridium")
            self.sfr.command_executor.transmit(UnsolicitedString("SAFE MODE ENTERED"))
        except IridiumError:  # If iridium fails
            try:  # Try to set up for aprs
                # Try to switch primary radio, returns False if APRS is locked off or antenna is not deployed
                if not self.sfr.set_primary_radio("APRS", turn_off_old=True):
                    raise APRSError()  # If primary radio switch failed, don't run further
                self.sfr.devices["APRS"].functional()  # Test if APRS is functional
                self.sfr.command_executor.transmit(UnsolicitedString("SAFE MODE ENTERED"))
            except APRSError:  # If aprs fails
                print("L :(", file = open("pfs-output.txt", "a"))
                self.testing_mode(e)  # DEBUG
                self.sfr.crash()  # PFS team took an L
        self.sfr.command_executor.transmit(UnsolicitedString(repr(e)))  # Transmit down error
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

        self.sfr.command_executor.execute_buffers()  # Execute all received commands
        if self.transmission_queue_clock.time_elapsed():  # Once every 10 seconds
            if self.sfr.devices["Iridium"] is not None and self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD: 
                # If iridium is on and signal is present
                self.sfr.command_executor.transmit_queue()  # Attempt to transmit entire transmission queue
                self.transmission_queue_clock.update_time()
            elif self.sfr.devices["APRS"] is not None:   
                # If APRS is on, don't check for signal
                self.sfr.command_executor.transmit_queue()  # Attempt to transmit entire transmission queue
                self.transmission_queue_clock.update_time()

        if self.sfr.check_lower_threshold():  # if battery is low
            print("cry", file = open("pfs-output.txt", "a"))
            self.sfr.command_executor.transmit(UnsolicitedString("Sat low battery, sleeping for 5400 seconds :("))
            self.sfr.power_off(self.sfr.vars.PRIMARY_RADIO)
            self.sfr.sleep(120)  # charge for one orbit TODO: 5400
            self.sfr.vars.BATTERY_CAPACITY_INT = self.sfr.analytics.volt_to_charge(sfr.battery.telemetry["VBAT"]())
            self.sfr.power_on(self.sfr.vars.PRIMARY_RADIO)

    def aprs_troubleshoot(self):
        """
        Attempt to troubleshoot APRS
        Raises error if troubleshooting fails
        """
        self.sfr.vars.FAILURES.append("APRS")
        self.sfr.reboot("APRS")
        self.sfr.devices["APRS"].functional()
        self.sfr.vars.FAILURES.remove("APRS")

    def iridium_troubleshoot(self):
        """
        Attempt to troubleshoot Iridium
        Raises error if troubleshooting fails
        """
        print(get_traceback(), file = open("pfs-output.txt", "a"))  # TODO: DEBUG
        print("-- Rebooting Iridium", file = open("pfs-output.txt", "a"))  # TODO: Debug
        self.sfr.vars.FAILURES.append("Iridium")
        self.sfr.reboot("Iridium")
        self.sfr.devices["Iridium"].functional()  # Raises error if fails
        self.sfr.vars.FAILURES.remove("Iridium")

    def eps_troubleshoot(self):
        """
        Attempt to troubleshoot EPS by waiting for watchdog reset
        Exiting ensures the python files don't get corrupted during reset
        """
        self.sfr.crash()

    def imu_troubleshoot(self):
        """
        Attempt to troubleshoot IMU
        Switches off IMU if troubleshooting fails because this is a noncritical component
        """
        self.sfr.vars.FAILURES.append("IMU")
        print("Rebooting IMU", file = open("pfs-output.txt", "a"))
        self.sfr.reboot("IMU")
        try:
            print("Checking if IMU is functional", file = open("pfs-output.txt", "a"))
            self.sfr.devices["IMU"].functional()
            self.sfr.vars.FAILURES.remove("IMU")
        except IMUError:
            print("Locking IMU off, proceeding with MCL", file = open("pfs-output.txt", "a"))
            result = self.sfr.lock_device_off("IMU")
            if result:
                unsolicited_packet = UnsolicitedString("IMU failure: locked off IMU")
            else:
                unsolicited_packet = UnsolicitedString("IMU failure: locked on so no action taken")
            self.sfr.command_executor.transmit(unsolicited_packet)

    def battery_troubleshoot(self):
        """
        Attempt to troubleshoot battery by waiting for watchdog reset
        Exiting ensures the python files don't get corrupted during reset
        """
        self.sfr.crash()

    def antenna_troubleshoot(self):
        """
        Attempt to troubleshoot Antenna Deployer
        Raises error if troubleshooting fails and locks antenna deployer/aprs off to avoid damaging satellite
        """
        try:
            self.sfr.vars.FAILURES.append("Antenna Deployer")
            self.sfr.reboot("Antenna Deployer")
            self.sfr.devices["Antenna Deployer"].functional()
            self.sfr.vars.FAILURES.remove("Antenna Deployer")
        except Exception as e:  # Lock off APRS to avoid damaging satellite
            self.sfr.vars.LOCKED_OFF_DEVICES += ["Antenna Deployer", "APRS"]
            self.sfr.set_primary_radio("Iridium", True)
            raise e

    def high_power_draw_troubleshoot(self):
        """
        Attempt to troubleshoot unusual power draw by waiting for watchdog reset
        Exiting ensures the python files don't get corrupted during reset
        """
        self.sfr.crash()


if __name__ == "__main__":
    mission_control = MissionControl()
    mission_control.main()
