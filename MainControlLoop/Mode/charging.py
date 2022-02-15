from Drivers.transmission_packet import UnsolicitedData
from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError
from lib.clock import Clock


class Charging(Mode):
    """
    This mode allows us to charge our battery while still maintaining contact with the ground
    Only the primary radio is on
    """
    @wrap_errors(LogicalError)
    def __init__(self, sfr, mode: type):
        """
        :param sfr: sfr object
        :type sfr: :class: 'lib.registry.StateFieldRegistry'
        :param mode: mode class to instantiate and to switch to after charging is complete
        :type mode: type
        """
        super().__init__(sfr)
        self.mode = mode
        # TODO: CHANGE TO 5 MINUTES TO ALLOW FOR CHARGING
        self.iridium_clock = Clock(10)  # Change Iridium poll interval to allow for charging
        # TODO: CHANGE TO 90 MINUTES TO ALLOW FOR CHARGING
        self.aprs_duty_cycle = Clock(10)  # If APRS is primary radio, transmit heartbeat every 90 minutes

        def charging_poll() -> bool:  # Switch Iridium off when not using
            self.sfr.power_on("Iridium")
            result = super(Charging, self).poll_iridium()
            self.sfr.power_off("Iridium")
            return result
        self.poll_iridium = charging_poll  # Cursed decoration of superclass method

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns 'Charging'
        :return: mode name
        :rtype: str
        """
        return "Charging"

    @wrap_errors(LogicalError)
    def start(self) -> bool:
        """
        Start all necessary devices
        Switch on only the primary radio to minimize power usage
        Returns False if we're not supposed to be in this mode due to locked devices
        :return: whether we're supposed to be in this mode
        :rtype: bool
        """
        return super().start([self.sfr.vars.PRIMARY_RADIO])

    @wrap_errors(LogicalError)
    def poll_aprs(self) -> None:
        """
        Poll the APRS once per orbit
        Transmits heartbeat pint and reads messages
        """
        self.sfr.power_on("APRS")
        print("Transmitting heartbeat...")
        self.sfr.command_executor.GPL(UnsolicitedData("GPL"))  # Transmit heartbeat immediately
        self.sfr.power_off("APRS")

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        """
        Doesn't call Mode execute_cycle because we want to reimplement transmit/receive with a charging focus
        """
        super().execute_cycle()
        if self.sfr.vars.PRIMARY_RADIO == "APRS" and self.aprs_duty_cycle.time_elapsed():
            self.poll_aprs()
            self.aprs_duty_cycle.update_time()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        """
        If charging complete, instantiate new mode object based on init parameter and suggest it
        Otherwise, suggest self
        :return: instantiated mode object to switch to
        :rtype: :class: 'MainControlLoop.Mode.mode.Mode'
        """
        super().suggested_mode()
        if self.sfr.check_upper_threshold():
            return self.mode(self.sfr)
        return self
