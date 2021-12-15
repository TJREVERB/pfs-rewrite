from MainControlLoop.Mode.mode import Mode
import time
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Charging(Mode):
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        super(Charging, self).__init__(sfr)

        self.conditions = {
            "Science Mode Status": False,  # this is False if science mode is not complete
            "Low Battery": True  # don't want to shift out of charging prematurely
        }

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Charging"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super(Charging, self).start()
        # TODO: THIS LEAVES THE APRS ON DURING CHARGING MODE IF IT IS PRIMARY, IS THIS INTENTIONAL?
        self.sfr.instruct["Pin On"](self.sfr.vars.PRIMARY_RADIO)  # turn on primary radio
        self.sfr.instruct["All Off"](exceptions=[self.sfr.vars.PRIMARY_RADIO])  # turn off any not required devices

        self.conditions["Low Battery"] = self.sfr.battery.telemetry["VBAT"]() <= self.sfr.vars.UPPER_THRESHOLD
        self.conditions["Science Mode Status"] = self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY > -1

    @wrap_errors(LogicalError)
    def check_conditions(self) -> bool:
        super(Charging, self).check_conditions()  # in case we decide to add some super conditions later

        return self.conditions["Low Battery"]  # Stays in charging mode as long as battery is low

    @wrap_errors(LogicalError)
    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        if self.conditions["Science Mode Status"]:  # if science mode is complete
            return self.sfr.modes_list["Outreach"]  # suggest outreach mode
        else:  # science mode not done
            return self.sfr.modes_list["Science"]  # suggest science mode

    @wrap_errors(LogicalError)
    def update_conditions(self) -> None:
        super(Charging, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.battery.telemetry["VBAT"]() <= self.UPPER_THRESHOLD
        self.conditions["Science Mode Status"] = self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY > -1

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        self.read_radio()  
        self.transmit_radio()
        self.check_time()
        super(Charging, self).execute_cycle()

    @wrap_errors(LogicalError)
    def read_radio(self):
        super(Charging, self).read_radio()

    @wrap_errors(LogicalError)
    def transmit_radio(self):
        return super(Charging, self).transmit_radio()

    @wrap_errors(LogicalError)
    def check_time(self):
        return super(Charging, self).check_time()
        
        #TODO: Update Iridium time

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        super(Charging, self).terminate_mode()
        pass
