from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError


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
        """
        # TODO: WHAT IF PRIMARY RADIO IS APRS? WILL WE BE ABLE TO CHARGE?
        return super().start([self.sfr.vars.PRIMARY_RADIO])

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
