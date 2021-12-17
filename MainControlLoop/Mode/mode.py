import time
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError
import datetime
import os


class Mode:
    # initialization: does not turn on devices, initializes instance variables
    @wrap_errors(LogicalError)
    def __init__(self, sfr, wait=40, thresh=2):
        self.LOWER_THRESHOLD = 6  # Lower battery voltage threshold for switching to CHARGING mode
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode
        self.previous_time = 0
        self.sfr = sfr
        self.last_iridium_poll_time = 0  # used to determine whether the iridium has been able to send recently
        self.PRIMARY_IRIDIUM_WAIT_TIME = wait  # wait time for iridium polling if iridium is main radio (default to 40
        # seconds)
        # Actual time between read/write will depend on signal availability
        self.SIGNAL_THRESHOLD = thresh  # Lower threshold to read or transmit
        self.TIME_ERR_THRESHOLD = 120  # Two minutes acceptable time error between iridium network and rtc

    @wrap_errors(LogicalError)
    def __str__(self):  # returns mode name as string
        pass

    @wrap_errors(LogicalError)
    def start(self, enabled_components: list) -> None:
        """
        Runs initial setup for a mode. Turns on and off devices for a specific mode.
        :param enabled_components: list of components which are enabled in this mode
        """
        self.sfr.turn_all_off()
        for i in enabled_components:
            self.sfr.turn_on_component(i)

    @wrap_errors(LogicalError)
    def suggested_mode(self):
        """
        Checks all conditions and returns which mode the current mode believes we should be in
        If we don't want to switch, return same mode
        If we do, return the mode we want to switch to
        :return: (Mode) instantiated mode object to switch to
        """
        pass

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        """
        Executes one iteration of mode
        For example: measure signal strength as the orbit location changes.
        NOTE: This method should not execute radio commands, that is done by command_executor class.
        """
        self.read_radio()
        self.transmit_buffer()
        self.check_time()

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
        if self.sfr.vars.PRIMARY_RADIO == "Iridium":
            if time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME \
                    and self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
                # get all messages from iridium, store them in sfr
                self.sfr.devices["Iridium"].next_msg()
                self.last_iridium_poll_time = time.time()
                self.sfr.vars.LAST_IRIDIUM_RECEIVED = time.time()
            elif time.time() - self.sfr.vars.LAST_IRIDIUM_RECEIVED > self.sfr.vars.UNSUCCESSFUL_RECEIVE_TIME_CUTOFF:
                # if we haven't read from the radio in a while, and weren't able to right now, default to APRS
                self.sfr.set_primary_radio("APRS")  # TODO: should this turn off the old radio?

        # If APRS is on for whatever reason
        if self.sfr.devices["APRS"] is not None:
            # add aprs messages to sfr
            self.sfr.devices["APRS"].next_msg()
        # commands will be executed in the mode.py's super method for execute_cycle using a command executor

        # TODO: Update Iridium time

    @wrap_errors(LogicalError)
    def transmit_buffer(self) -> None:
        """
        Transmit any messages in the transmit queue
        :return: (bool) whether all transmit queue messages were sent
        """
        print("Signal strength: " + str(ss := self.sfr.devices["Iridium"].check_signal_passive()))
        if self.sfr.vars.PRIMARY_RADIO == "APRS" or (self.sfr.vars.PRIMARY_RADIO == "Iridium" and
                 time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME and
                 ss >= self.SIGNAL_THRESHOLD):
            print("Attempting to transmit queue")
            while len(self.sfr.vars.transmit_buffer) > 0:  # attempt to transmit transmit buffer
                if not self.sfr.command_executor.transmit(p := self.sfr.vars.transmit_buffer[0], appendtoqueue = False):
                    print("Signal strength lost!")
                    break
                self.sfr.vars.transmit_buffer.pop(0)
                print("Transmitted " + p.command_string)

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
                os.system(
                    f"""sudo date -s "{iridium_datetime.strftime("%Y-%m-%d %H:%M:%S UTC")}" """)  # Update system time
                os.system("""sudo hwclock -w""")  # Write to RTC

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