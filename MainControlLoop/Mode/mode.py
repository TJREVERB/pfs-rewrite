import time
from lib.exceptions import wrap_errors, LogicalError, NoSignalException
from lib.clock import Clock
from Drivers.transmission_packet import UnsolicitedData
import datetime
import os


class Mode:
    """
    This is the python equivalent of an interface for the different modes.
    All the modes extend this mode. Some functions are placeholders in :class: 'Mode' and
    only serve as a framework of what functions to include for development of the child classes.
    """
    # initialization: does not turn on devices, initializes instance variables
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Initializes constants specific to instance of Mode
        :param sfr: sfr object
        :type sfr: :class: 'lib.registry.StateFieldRegistry'
        """
        self.sfr = sfr
        self.TIME_ERR_THRESHOLD = 120  # Two minutes acceptable time error between iridium network and rtc
        self.iridium_clock = Clock(40)  # Poll iridium every "wait" seconds
        self.heartbeat_clock = Clock(5*60)  # Heartbeat every 2 minutes (not appended to queue)

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns mode name as string
        :return: mode name
        :rtype: str
        """
        return "Mode"

    @wrap_errors(LogicalError)
    def start(self, enabled_components: list) -> bool:
        """
        Checks if we can be in this mode (if any required components are locked off, we can't)
        Runs initial setup for a mode. Turns on and off devices for a specific mode.
        :param enabled_components: list of components which need to be enabled in this mode
        :type enabled_components: list
        :return: whether we should be in this mode
        :rtype: bool
        """
        if any([(i in self.sfr.vars.LOCKED_OFF_DEVICES) for i in enabled_components]):
            return False
        self.sfr.all_off(exceptions=enabled_components)
        for component in enabled_components:
            self.sfr.power_on(component)
        return True

    @wrap_errors(LogicalError)
    def suggested_mode(self):
        """
        Checks all conditions and returns which mode the current mode believes we should be in
        If we don't want to switch, return same mode
        If we do, return the mode we want to switch to
        This method in mode.py is just a framework for child classes, see specific
        child for actual implementation
        """
        pass

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        """
        Executes one iteration of mode
        For example: measure signal strength as the orbit location changes.
        Additionally, it resets EPS watchdog and transmits heartbeat
        """
        self.sfr.eps.commands["Reset Watchdog"]()  # ensures EPS doesn't reboot
        # If enough time has passed and primary radio is Iridium
        if self.iridium_clock.time_elapsed() and self.sfr.vars.PRIMARY_RADIO == "Iridium":
            try:
                self.poll_iridium()  # Poll Iridium
            except NoSignalException:
                pass
            self.iridium_clock.update_time()  # Update last iteration
        if self.heartbeat_clock.time_elapsed():  # Heartbeat pings
            self.heartbeat()
            self.heartbeat_clock.update_time()
        self.read_aprs()  # Read from APRS every cycle

    @wrap_errors(LogicalError)
    def poll_iridium(self) -> bool:
        """
        Runs every 5 minutes
        Reads Iridium messages and appends to buffer
        Transmits any messages in the transmit queue
        Updates rtc clock based on iridium time if needed
        :return: whether the function ran (whether it polled iridium or not)
        :rtype: bool
        """
        if self.sfr.devices["Iridium"] is None:  # Don't run if Iridium is powered off (should never happen)
            return False

        signal = self.sfr.devices["Iridium"].check_signal_passive()
        print("Iridium signal strength: ", signal)
        if signal < 1:
            return False

        self.sfr.command_executor.GPL(UnsolicitedData("GPL"))  # Transmit heartbeat immediately

        startlen = len(self.sfr.vars.command_buffer)
        self.sfr.devices["Iridium"].next_msg()  # Read from iridium
        if len(self.sfr.vars.command_buffer) > startlen:
            self.sfr.vars.LAST_IRIDIUM_RECEIVED = time.time()  # Update last message received

        self.sfr.command_executor.transmit_queue()  # Attempt to transmit transmission queue

        current_datetime = datetime.datetime.utcnow()
        iridium_datetime = self.sfr.devices["Iridium"].processed_time()
        if abs((current_datetime - iridium_datetime).total_seconds()) > self.TIME_ERR_THRESHOLD:
            os.system(f"sudo date -s \"{iridium_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')}\" ")  
            # Update system time
            os.system("sudo hwclock -w")  # Write to RTC

        return True

    @wrap_errors(LogicalError)
    def heartbeat(self) -> None:
        """
        Transmits proof of life if enough time has elapsed
        """
        self.sfr.command_executor.IHB(UnsolicitedData("IHB"))

    @wrap_errors(LogicalError)
    def read_aprs(self) -> bool:
        """
        Read from the APRS if it exists
        :return: whether the function ran (whether it read aprs messages or not)
        :rtype: bool
        """
        if self.sfr.devices["APRS"] is None:
            return False
        self.sfr.devices["APRS"].next_msg()
        return True

    @wrap_errors(LogicalError)
    def systems_check(self) -> bool:
        """
        Performs a systems check of components that are not locked off and returns if a part failed or not
        Throws error if .functional() fails

        :return: ALWAYS TRUE, a problem will result in an exception being raised
        :rtype: bool
        """
        # Iterate over all devices which aren't locked off
        for device in filter(lambda i: i not in self.sfr.vars.LOCKED_OFF_DEVICES, self.sfr.devices.keys()):
            if self.sfr.devices[device] is None:
                self.sfr.power_on(device)
                if device == "Iridium":
                    self.sfr.devices[device].SBD_STATUS()
                self.sfr.devices[device].functional()
                self.sfr.power_off(device)
            else:
                if device == "Iridium":
                    self.sfr.devices[device].SBD_STATUS()
                self.sfr.devices[device].functional()
        return True

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        """
        Safely terminates current mode.
        This DOES NOT turn off all devices, simply the ones turned on specifically for this mode.
        This is to prevent modes from turning on manually turned on or off devices.
        Also writes any relevant temporary memory stored in modules to sfr (i.e. iridium buffer).
        Does not handle memory.
        """
        self.sfr.dump()
