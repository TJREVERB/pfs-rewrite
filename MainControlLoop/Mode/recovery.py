from MainControlLoop.Mode.mode import Mode
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError
import time
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket


class Recovery(Mode):
    BEACON_WAIT_TIME = 120  # 2 minutes

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Sets up constants
        """
        super().__init__(sfr)
        self.last_contact_attempt = 0
        self.systems_check_complete = False

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Recovery"

    @wrap_errors(LogicalError)  # TODO: IMPLEMENT
    def start(self) -> None:
        super().start([self.sfr.vars.PRIMARY_RADIO])
        self.sfr.vars.CONTACT_ESTABLISHED = False

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:  # TODO: IMPLEMENT
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:  # Execute cycle low battery
            self.sfr.instruct["All Off"]()  # turn everything off
            time.sleep(self.sfr.vars.ORBITAL_PERIOD)  # sleep for one full orbit
            self.start()
        else:
            if not self.systems_check_complete:
                super().systems_check()  # if systems check runs without throwing an error, everything works
                self.systems_check_complete = True
            if time.time() > self.last_contact_attempt + self.BEACON_WAIT_TIME:  # try to contact ground again
                self.antenna()  # Antenna deployment, does nothing if antenna is already deployed
                # Attempt to establish contact with ground
                print("Transmitting proof of life...")
                self.sfr.command_executor.GPL(TransmissionPacket("GPL", [], 0))
                self.last_contact_attempt = time.time()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        final_mode = self.sfr.modes_list["Outreach"] if self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY != -1 \
            else self.sfr.modes_list["Science"]
        if not (self.systems_check_complete and self.sfr.vars.CONTACT_ESTABLISHED):  # we are done with recovery mode
            return self
        elif self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:  # if we need to enter charging mode
            return self.sfr.modes_list["Charging"](self.sfr, final_mode(self.sfr))
        else:
            return final_mode(self.sfr)
