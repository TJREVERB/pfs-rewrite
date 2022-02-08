from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError


class Repeater(Mode):
    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns mode name as string
        :return: mode name
        :rtype: str
        """
        return "Repeater"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        """
        Runs initial setup for a mode. Turns on and off devices for a specific mode.
        """
        return super().start([self.sfr.vars.PRIMARY_RADIO, "APRS"])
        self.sfr.devices["APRS"].enable_digi()

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
        if self.sfr.check_lower_threshold():  # If low battery
            # Switch to charging, then outreach
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Outreach"])
        return self

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        """
        Safely terminates current mode.
        This DOES NOT turn off all devices, simply the ones turned on specifically for this mode.
        This is to prevent modes from turning on manually turned on or off devices.
        Also writes any relevant temporary memory stored in modules to sfr (i.e. iridium buffer).
        Does not handle memory.
        """
        super(Repeater, self).terminate_mode()
        self.sfr.devices["APRS"].disable_digi()
