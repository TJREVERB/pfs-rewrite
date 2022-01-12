from numpy import nan
from MainControlLoop.Mode.mode import Mode
from Drivers.transmission_packet import UnsolicitedData
from lib.exceptions import NoSignalException, wrap_errors, LogicalError
from lib.clock import Clock


class Science(Mode):
    # number of pings to do to complete orbit
    # NUMBER_OF_REQUIRED_PINGS = self.sfr.vars.analytics.calc_orbital_period / self.DATAPOINT_SPACING
    NUMBER_OF_REQUIRED_PINGS = 5  # TODO: UPDATE

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        super().__init__(sfr)
        self.ping_clock = Clock(self.ping, 5)  # TODO: MAKE 60
        self.pings_performed = 0

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Science"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super().start([self.sfr.vars.PRIMARY_RADIO, "Iridium"])
        self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY = -1

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if self.sfr.check_lower_threshold():  # If we're on low battery
            return self.sfr.modes_list["Charging"](self.sfr, type(self))  # Suggest charging
        elif self.sfr.devices["Iridium"] is None:  # If Iridium is off
            return self.sfr.modes_list["Outreach"](self.sfr)  # Suggest outreach
        elif self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY != -1:  # If we've finished getting our data
            return self.sfr.modes_list["Outreach"](self.sfr)  # Suggest outreach (we'll go to charging when necessary)
        return self  # Otherwise, stay in science

    @wrap_errors(LogicalError)
    def ping(self) -> bool:
        """
        Log current iridium connectivity
        :return: (bool) whether function ran
        """
        if self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS:
            return False
        print("Recording signal strength ping " + str(self.pings_performed + 1) + "...")
        try:  # Log Iridium data
            geolocation = self.sfr.devices["Iridium"].processed_geolocation()
            if(geolocation == (0, 0, 0)):
                self.sfr.log_iridium(geolocation,
                    self.sfr.devices["Iridium"].check_signal_active(), True)            
            else:
                self.sfr.log_iridium(geolocation,
                    self.sfr.devices["Iridium"].check_signal_active())
            print("Logged with connectivity")
        except NoSignalException:  # Log NaN geolocation, 0 signal strength
            self.sfr.log_iridium((nan, nan, nan), 0, True)
            print("Logged 0 connectivity")
        finally:  # Always update last_ping time to prevent spamming pings
            self.pings_performed += 1
            return True

    @wrap_errors(LogicalError)
    def transmit_results(self) -> bool:
        """
        Transmit science mode results
        :return: (bool) whether function ran
        """
        print("Transmitting results...")
        self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY = self.sfr.analytics.signal_strength_variability()
        # Transmit signal strength variability
        self.sfr.command_executor.GSV(UnsolicitedData("GSV"))
        return True

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        super().execute_cycle()
        if not self.ping_clock.execute():  # If we've performed enough pings
            self.transmit_results()
