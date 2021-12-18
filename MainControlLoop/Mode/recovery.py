from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError
import time


class Recovery(Mode):

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Sets up constants
        """
        super().__init__(sfr)
        self.last_contact_attempt = 0

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Recovery"

    @wrap_errors(LogicalError)  # TODO: IMPLEMENT
    def start(self) -> None:
        super().start([self.sfr.vars.PRIMARY_RADIO])

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:  # TODO: IMPLEMENT
        super().execute_cycle()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:  # Execute cycle low battery
            self.sfr.instruct["All Off"]()  # turn everything off
            time.sleep(self.sfr.vars.ORBITAL_PERIOD)  # sleep for one full orbit
            self.start()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()

        if not self.sfr.vars.ANTENNA_DEPLOYED:  # just in case this slipped through, go to startup mode
            return self.sfr.modes_list["Startup"](self.sfr)

        science_mode_complete = self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY != -1
        if False:  # TODO: implement conditions for staying in recovery mode
            return self
        elif self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:  # if we need to enter charging mode
            if science_mode_complete:  # if we have already finished science, charging will go to outreach
                return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Outreach"])
            else:  # we need to charge, then go to science
                return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Science"])
        elif science_mode_complete:  # If we've finished getting our data
            return self.sfr.modes_list["Outreach"](self.sfr)
        else:  # if we still need to finish science mode, and we are done with recovery mode
            return self.sfr.modes_list["Science"](self.sfr)