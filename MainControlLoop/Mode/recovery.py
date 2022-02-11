from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError
from lib.clock import Clock
from Drivers.transmission_packet import UnsolicitedData


class Recovery(Mode):
    """
    This mode is what we boot into after deployment from the ISS
    The condition for entering this mode (checked in mcl) is that the antenna has been deployed
    Or that the antenna/aprs are locked off (so deployment in Startup is impossible)
    Runs a full systems check and reestablishes contact with ground
    """
    BEACON_WAIT_TIME = 120  # 2 minutes

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        :param sfr: sfr object
        :type sfr: :class: 'lib.registry.StateFieldRegistry'
        """
        super().__init__(sfr)
        self.beacon = Clock(self.BEACON_WAIT_TIME)

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns 'Recovery'
        :return: mode name
        :rtype: str
        """
        return "Recovery"

    @wrap_errors(LogicalError)
    def start(self) -> bool:
        """
        Runs full system check (throws error if something is wrong)
        Turns on only primary radio
        Returns False if we're not supposed to be in this mode due to locked devices
        """
        super().systems_check()  # Run only once, throws error if there's a problem with one of the devices
        if result := super().start([self.sfr.vars.PRIMARY_RADIO]):
            self.sfr.vars.CONTACT_ESTABLISHED = False
        return result

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        """
        Executes one iteration of Recovery mode
        If enough time has passed, beacon a proof of life ping to ground to establish contact
        If we're low on battery, sleep for an orbit before continuing
        """
        if self.sfr.check_lower_threshold():  # Execute cycle low battery
            self.sfr.all_off()  # turn everything off
            self.sfr.sleep(5400)  # sleep for one full orbit
            self.start()
        if self.beacon.time_elapsed():  # Attempt to establish contact with ground
            print("Transmitting proof of life...")
            self.sfr.command_executor.GPL(UnsolicitedData("GPL"))
            self.beacon.update_time()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        """
        If contact hasn't been established, stay in Recovery
        If contact has been established and Science mode is incomplete (and Iridium isn't locked off), go to Science
        If contact has been established and Science mode is complete (or Iridium is locked off), go to Outreach
        :return: instantiated mode object to switch to
        :rtype: :class: 'MainControlLoop.Mode.mode.Mode'
        """
        super().suggested_mode()
        if not self.sfr.vars.CONTACT_ESTABLISHED:  # If contact hasn't been established
            return self  # Stay in recovery
        # If Science mode incomplete and Iridium isn't locked off, suggest Science
        elif self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY == -1 and "Iridium" not in self.sfr.vars.LOCKED_OFF_DEVICES:
            return self.sfr.modes_list["Science"](self.sfr)
        else:  # If Science mode complete or Iridium is locked off, suggest Outreach
            return self.sfr.modes_list["Outreach"](self.sfr)
