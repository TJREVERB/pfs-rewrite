from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError
import time
from Drivers.transmission_packet import UnsolicitedData


class Recovery(Mode):
    BEACON_WAIT_TIME = 120  # 2 minutes

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Initializes constants specific to instance of Mode
        :param sfr: Reference to :class: 'MainControlLoop.lib.registry.StateFieldRegistry'
        :type sfr: :class: 'MainControlLoop.lib.registry.StateFieldRegistry'
        """
        super().__init__(sfr)
        self.last_contact_attempt = 0
        self.systems_check_complete = False

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns mode name as string
        :return: mode name
        :rtype: str
        """
        return "Recovery"

    @wrap_errors(LogicalError)
    def start(self) -> bool:
        """
        Runs initial setup for a mode. Turns on and off devices for a specific mode.
        """
        if result := super().start([self.sfr.vars.PRIMARY_RADIO]):
            self.sfr.vars.CONTACT_ESTABLISHED = False
        return result

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        """
        Executes one iteration of mode
        For example: measure signal strength as the orbit location changes.
        NOTE: This method should not execute_buffers radio commands, that is done by command_executor class.
        """
        if self.sfr.check_lower_threshold():  # Execute cycle low battery
            self.sfr.all_off()  # turn everything off
            self.sfr.sleep(5400)  # sleep for one full orbit
            self.start()
        else:
            if not self.systems_check_complete:
                super().systems_check()  # if systems check runs without throwing an error, everything works
                self.systems_check_complete = True
            if time.time() > self.last_contact_attempt + self.BEACON_WAIT_TIME:  # try to contact ground again
                # Attempt to establish contact with ground
                print("Transmitting proof of life...")
                self.sfr.command_executor.GPL(UnsolicitedData("GPL"))
                self.last_contact_attempt = time.time()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        """
        Checks all conditions and returns which mode the current mode believes we should be in
        If we don't want to switch, return same mode
        If we do, return the mode we want to switch to
        :return: instantiated mode object to switch to
        :rtype: :class: 'Mode'
        """
        super().suggested_mode()
        final_mode = self.sfr.modes_list["Outreach"] if self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY != -1 \
            else self.sfr.modes_list["Science"]
        if not (self.systems_check_complete and self.sfr.vars.CONTACT_ESTABLISHED):  # we are done with recovery mode
            return self
        elif self.sfr.check_lower_threshold():  # if we need to enter charging mode
            return self.sfr.modes_list["Charging"](self.sfr, final_mode(self.sfr))
        else:
            return final_mode(self.sfr)
