import time
from lib.exceptions import wrap_errors, LogicalError
from lib.clock import Clock
import datetime
import os


class Mode:
    # initialization: does not turn on devices, initializes instance variables
    @wrap_errors(LogicalError)
    def __init__(self, sfr, wait=40, thresh=2):
        self.SIGNAL_THRESHOLD = thresh
        self.previous_time = 0
        self.sfr = sfr
        self.TIME_ERR_THRESHOLD = 120  # Two minutes acceptable time error between iridium network and rtc
        self.clocks = {
            # Read from iridium, transmit buffer, and update clock every "wait" seconds (default 40)
            "Poll Iridium": Clock(self.poll_iridium, delay=wait, conditions=[  # Only if
                lambda: self.sfr.vars.PRIMARY_RADIO == "Iridium",  # Iridium is primary
                lambda: self.sfr.devices["Iridium"] is not None,  # Iridium is on
                # We have connection to the constellation
                lambda: self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD,
            ]),
            # Check Iridium timeout every possible iteration
            "Iridium Timeout": Clock(lambda: self.sfr.set_primary_radio("APRS"), conditions=[  # Only if
                lambda: time.time() - self.sfr.vars.LAST_IRIDIUM_RECEIVED >  # We haven't received a message
                        self.sfr.vars.UNSUCCESSFUL_RECEIVE_TIME_CUTOFF  # For a very long time
            ]),
            # Read from APRS every possible iteration
            "Read APRS": Clock(self.sfr.devices["APRS"].next_msg, conditions=[  # Only if
                lambda: self.sfr.devices["APRS"] is not None,  # APRS is on
            ]),
        }

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
        for i in set(enabled_components):
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
        for i in self.clocks.keys():
            self.clocks[i].execute()

    @wrap_errors(LogicalError)
    def poll_iridium(self) -> None:
        """
        Read Iridium messages and append to buffer
        Transmit any messages in the transmit queue
        Update hardware clock
        DOES NOT RUN UNLESS WE HAVE IRIDIUM CONNECTIVITY
        """
        self.sfr.devices["Iridium"].next_msg()  # Read from iridium
        self.sfr.vars.LAST_IRIDIUM_RECEIVED = time.time()  # Update last message received
        print("Attempting to transmit queue")
        while len(self.sfr.vars.transmit_buffer) > 0:  # attempt to transmit buffer
            if not self.sfr.command_executor.transmit(p := self.sfr.vars.transmit_buffer[0], appendtoqueue=False):
                print("Signal strength lost!")
                break
            self.sfr.vars.transmit_buffer.pop(0)
            print("Transmitted " + p.command_string)
        current_datetime = datetime.datetime.utcnow()
        iridium_datetime = self.sfr.devices["Iridium"].processed_time()
        if abs((current_datetime - iridium_datetime).total_seconds()) > self.TIME_ERR_THRESHOLD:
            os.system(
                f"""sudo date -s "{iridium_datetime.strftime("%Y-%m-%d %H:%M:%S UTC")}" """)  # Update system time
            os.system("""sudo hwclock -w""")  # Write to RTC

    @wrap_errors(LogicalError)
    def systems_check(self):
        """
        Performs a systems check of components that are on and returns a list of component failures
        Throws error if .functional() fails
        TODO: implement system check of antenna deployer
        """
        for device in self.sfr.devices.keys():
            self.sfr.devices[device].functional()

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
