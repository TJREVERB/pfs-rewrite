from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError


class Repeater(Mode):
    """
    This mode turns on APRS with digipeating
    Mandatory to have digipeat enabled if we want to use the APRS network
    Only triggered through command from ground
    """
    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns 'Repeater'
        :return: mode name
        :rtype: str
        """
        return "Repeater"

    @wrap_errors(LogicalError)
    def start(self) -> bool:
        """
        Switches on APRS (and Iridium if it's primary radio)
        Enables digipeating
        """
        if result := super().start([self.sfr.vars.PRIMARY_RADIO, "APRS"]):
            self.sfr.devices["APRS"].enable_digi()
        return result

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        """
        If we don't want to switch, return same mode
        If we do, return the mode we want to switch to
        :return: instantiated mode object to switch to
        :rtype: :class: 'MainControlLoop.Mode.mode.Mode'
        """
        super().suggested_mode()
        if self.sfr.check_lower_threshold():  # If low battery
            # Switch to charging, then outreach
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Outreach"])
        return self

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        """
        Safely terminates current mode.
        Switches off digipeating.
        """
        super(Repeater, self).terminate_mode()
        self.sfr.devices["APRS"].disable_digi()
