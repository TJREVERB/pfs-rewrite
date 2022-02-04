import time
from lib.exceptions import wrap_errors, LogicalError
from lib.clock import Clock
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
    def __init__(self, sfr, wait=10, thresh=2):  # TODO: replace wait with appropriate time when done testing
        """
        Initializes constants specific to instance of Mode
        :param sfr: Reference to :class: 'MainControlLoop.lib.registry.StateFieldRegistry'
        :type sfr: :class: 'MainControlLoop.lib.registry.StateFieldRegistry'
        :param wait: poll iridium ever "wait" seconds, defaults to 10
        :type wait: int, optional
        :param thresh: signal threshold for polling iridium, defaults to 2
        :type thresh: int, optional
        """
        self.SIGNAL_THRESHOLD = thresh  # TODO: FIX
        self.sfr = sfr
        self.TIME_ERR_THRESHOLD = 120  # Two minutes acceptable time error between iridium network and rtc
        self.iridium_clock = Clock(wait)  # Poll iridium every "wait" seconds

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns mode name as string
        :return: mode name
        :rtype: str
        """
        return "Mode"

    @wrap_errors(LogicalError)
    def start(self, enabled_components: list) -> None:
        """
        Runs initial setup for a mode. Turns on and off devices for a specific mode.
        :param enabled_components: list of components which need to be enabled in this mode
        :type enabled_components: list
        """
        self.sfr.all_off(exceptions=enabled_components)
        for component in enabled_components:
            self.sfr.power_on(component)

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
        NOTE: This method should not execute_buffers radio commands, that is done by command_executor class.
        """
        self.sfr.eps.commands["Reset Watchdog"]()  # ensures EPS doesn't reboot
        if self.iridium_clock.time_elapsed():  # If enough time has passed
            self.poll_iridium()
            self.iridium_clock.update_time()
        self.read_aprs()  # Read from APRS every cycle

    @wrap_errors(LogicalError)
    def poll_iridium(self) -> bool:
        """
        Reads Iridium messages and appends to buffer
        Transmits any messages in the transmit queue
        Updates rtc clock based on iridium time if needed
        :return: whether the function ran (whether it polled iridium or not)
        :rtype: bool
        """
        if self.sfr.devices["Iridium"] is None and self.sfr.vars.PRIMARY_RADIO != "Iridium":
            return False
        signal = self.sfr.devices["Iridium"].check_signal_passive()
        print("Iridium signal strength: ", signal)
        if signal <= self.SIGNAL_THRESHOLD:
            return False
        # TODO: add this back after testing
        # if self.sfr.devices["Iridium"].check_signal_passive() <= self.SIGNAL_THRESHOLD:
        #     return False
        self.sfr.devices["Iridium"].next_msg()  # Read from iridium
        self.sfr.vars.LAST_IRIDIUM_RECEIVED = time.time()  # Update last message received
        print("Attempting to transmit queue")
        while len(self.sfr.vars.transmit_buffer) > 0:  # attempt to transmit buffer
            if not self.sfr.command_executor.transmit_from_buffer(p := self.sfr.vars.transmit_buffer[0]):
                print("Signal strength lost!")
                break
            self.sfr.vars.transmit_buffer.pop(0)
            print(f"Transmitted {p}")
        current_datetime = datetime.datetime.utcnow()
        iridium_datetime = self.sfr.devices["Iridium"].processed_time()
        if abs((current_datetime - iridium_datetime).total_seconds()) > self.TIME_ERR_THRESHOLD:
            os.system(f"sudo date -s \"{iridium_datetime.strftime('%Y-%m-%d %H:%M:%S UTC')}\" ")  
            # Update system time
            os.system("sudo hwclock -w")  # Write to RTC
        return True

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

        :return: whether there was a failure in non-locked off components
        :rtype: bool
        """
        for device in self.sfr.devices.keys():
            if not (device in self.sfr.vars.LOCKED_OFF_DEVICES):  # if it is not locked off, run functional check
                device_object = self.sfr.devices[device]
                was_off = False
                if device_object is None:  # if the device is off, turn it on for the system check
                    was_off = True
                    self.sfr.power_on(device)
                    device_object = self.sfr.devices[device]
                if device_object.functional() is False:
                    return False
                if was_off:  # if it was previously off, turn it back off now that the systems check is complete
                    self.sfr.power_off(device)
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
