import time
from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.iridium import Iridium
from MainControlLoop.Drivers.bno055 import IMU
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError
import datetime, os


class Mode:
    # initialization: does not turn on devices, initializes instance variables
    @wrap_errors(LogicalError)
    def __init__(self, sfr, wait=40, thresh=2):
        self.LOWER_THRESHOLD = 6  # Lower battery voltage threshold for switching to CHARGING mode
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode
        self.previous_time = 0
        self.sfr = sfr
        self.last_iridium_poll_time = 0
        self.PRIMARY_IRIDIUM_WAIT_TIME = wait  # wait time for iridium polling if iridium is main radio (default to 40
        # seconds)
        # Actual time between read/write will depend on signal availability
        self.SIGNAL_THRESHOLD = thresh  # Lower threshold to read or transmit
        self.TIME_ERR_THRESHOLD = 120 # Two minutes acceptable time error between iridium network and rtc
        self.sfr.instruct = {
            "Pin On": self.sfr.turn_on_component,
            "Pin Off": self.sfr.turn_off_component,
            "All On": self.sfr.turn_all_on,
            "All Off": self.sfr.turn_all_off
        }

    @wrap_errors(LogicalError)
    def __str__(self):  # returns mode name as string
        pass

    @wrap_errors(LogicalError)
    def start(self) -> None:
        """
        Runs initial setup for a mode. Turns on and off devices for a specific mode.
        """
        pass

    @wrap_errors(LogicalError)
    def check_conditions(self) -> bool:
        """
        Checks whether conditions for mode to continue running are still true.
        NOTE: THIS METHOD DOES NOT SWITCH MODES OR MODIFY THE STATE FIELD REGISTRY. THAT IS DONE IN THE MCL
        :return: (bool) true to stay in mode, false to exit
        """
        return True

    @wrap_errors(LogicalError)
    def update_conditions(self) -> None:
        """
        Updates conditions dict in each mode
        """
        pass

    @wrap_errors(LogicalError)
    def switch_mode(self):
        """
        Returns which mode to switch to
        """
        pass

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        """
        Executes one iteration of mode
        For example: measure signal strength as the orbit location changes.
        NOTE: This method should not execute radio commands, that is done by command_executor class.
        """
        pass

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        """
        Safely terminates current mode.
        This DOES NOT turn off all devices, simply the ones turned on specifically for this mode.
        This is to prevent modes from turning on manually turned on or off devices.
        Also writes any relevant temporary memory stored in modules to sfr (i.e. iridium buffer).
        Does not handle memory, memory handler is responsible for insufficient memory errors.
        TODO: write memory handler in case of insufficient memory error.
        """
        self.sfr.dump()
        pass

    @wrap_errors(LogicalError)
    def read_radio(self) -> None:
        """
        Function for each mode to implement to determine how it will use the specific radios
        """
        # If primary radio is iridium and enough time has passed
        if self.sfr.vars.PRIMARY_RADIO == "Iridium" and \
                time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME \
                and self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
            # get all messages from iridium, store them in sfr
            self.sfr.devices["Iridium"].next_msg()
            self.last_iridium_poll_time = time.time()
        # If APRS is on for whatever reason
        if self.sfr.devices["APRS"] is not None:
            # add aprs messages to sfr
            self.sfr.devices["APRS"].next_msg()
        # commands will be executed in the mode.py's super method for execute_cycle using a command executor

        # TODO: Update Iridium time

    @wrap_errors(LogicalError)
    def transmit_radio(self) -> None:
        """
        Transmit any messages in the transmit queue
        :return: (bool) whether all transmit queue messages were sent
        """
        # If primary radio is iridium and enough time has passed
        if self.sfr.vars.PRIMARY_RADIO == "Iridium" and \
                time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME \
                and self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
            while len(self.sfr.vars.transmit_buffer) > 0:  # attempt to transmit transmit buffer
                packet = self.vars.transmit_buffer.pop(0)
                if not self.sfr.command_executor.transmit(packet):
                    self.vars.transmit_buffer.append(packet)
                    return False
        # If primary radio is APRS
        if self.sfr.vars.PRIMARY_RADIO == "APRS":
            while len(self.sfr.vars.transmit_buffer) > 0:  # attempt to transmit transmit buffer
                packet = self.vars.transmit_buffer.pop(0)
                if not self.sfr.command_executor.transmit(packet):
                    self.vars.transmit_buffer.append(packet)
                    return False
        return True

    @wrap_errors(LogicalError)
    def check_time(self) -> None:
        """
        Checks rtc time against iridium time, should be called AFTER all tx/rx functions
        """
        if self.sfr.vars.PRIMARY_RADIO == "Iridium" \
                and self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
            current_datetime = datetime.datetime.utcnow()
            iridium_datetime = self.sfr.devices["Iridium"].processed_time()
            if abs((current_datetime - iridium_datetime).total_seconds()) > self.TIME_ERR_THRESHOLD:
                os.system(f"""sudo date -s "{iridium_datetime.strftime("%Y-%m-%d %H:%M:%S UTC")}" """) # Update system time
                os.system("""sudo hwclock -w""") # Write to RTC


    @wrap_errors(LogicalError)
    def systems_check(self) -> list:
        """
        Performs a systems check of components that are on and returns a list of component failures
        TODO: implement system check of antenna deployer
        TODO: account for different exceptions in .functional() and attempt to troubleshoot
        :return: (list) component failures
        """
        result = []
        for device in self.sfr.devices:
            # TODO: Implement functional for all devices
            # if the device is on and not functional
            if self.sfr.devices[device] is not None and not self.sfr.devices[device].functional():
                result.append(device)
        return result


