from MainControlLoop.Mode.mode import Mode
from Drivers.transmission_packet import UnsolicitedData
from lib.exceptions import NoSignalException, wrap_errors, LogicalError
from lib.clock import Clock


class Science(Mode):
    """
    Mode for conducting experiments on the signal strength variability of iridium over an orbit
    """
    # number of pings to do to complete orbit
    # NUMBER_OF_REQUIRED_PINGS = self.sfr.vars.analytics.calc_orbital_period / self.DATAPOINT_SPACING
    NUMBER_OF_REQUIRED_PINGS = 5  # TODO: UPDATE

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Initializes constants specific to instance of Mode
        :param sfr: Reference to :class: 'MainControlLoop.lib.registry.StateFieldRegistry'
        :type sfr: :class: 'MainControlLoop.lib.registry.StateFieldRegistry'
        """

        super().__init__(sfr)
        self.ping_clock = Clock(5)  # TODO: MAKE 60
        if len(df := self.sfr.logs["Iridium"].read()) >= 50:
            self.sfr.logs["Iridium"].clear()
            self.pings_performed = 0
        else:
            self.pings_performed = len(df)

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns mode name as string
        :return: mode name
        :rtype: str
        """
        return "Science"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        """
        Powers on Iridium and APRS (if it is the primary radio)
        """
        super().start([self.sfr.vars.PRIMARY_RADIO, "Iridium"])

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if self.sfr.check_lower_threshold():  # If we're on low battery
            return self.sfr.modes_list["Charging"](self.sfr, type(self))  # Suggest charging
        elif self.sfr.devices["Iridium"] is None:  # If Iridium is off
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Outreach"]) # TODO: remove this after testing is done
            # return self.sfr.modes_list["Outreach"](self.sfr)  # Suggest outreach
        elif self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS:  # If we've finished getting our data
            return self.sfr.modes_list["Science"](self.sfr)  # TODO: remove this after testing
            # return self.sfr.modes_list["Outreach"](self.sfr)  # Suggest outreach (we'll go to charging when necessary)
        return self  # Otherwise, stay in science

    @wrap_errors(LogicalError)
    def ping(self) -> bool:
        """
        Log current iridium connectivity
        :return: whether function ran and pinged iridium
        :rtype: bool
        """
        print("Executing science mode ping")  # TODO: remove this after testing
        print("Recording signal strength ping " + str(self.pings_performed + 1) + "...")
        try:  # Log Iridium data
            geolocation = self.sfr.devices["Iridium"].processed_geolocation()
        except NoSignalException:  # Log 0,0,0 geolocation, 0 signal strength
            geolocation = (0, 0, 0)
        self.sfr.log_iridium(geolocation, self.sfr.devices["Iridium"].check_signal_active())
        self.pings_performed += 1
        return True

    @wrap_errors(LogicalError)
    def transmit_results(self) -> bool:
        """
        Transmit science mode results
        :return: whether function ran and transmitted results of signal strength variability
        :rtype: bool
        """
        print("Transmitting results...")
        self.sfr.vars.SIGNAL_STRENGTH_MEAN = self.sfr.analytics.signal_strength_mean()
        self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY = self.sfr.analytics.signal_strength_variability()
        print("Signal strength mean:", self.sfr.vars.SIGNAL_STRENGTH_MEAN)
        print("Signal strength variability:", self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY)
        # Transmit signal strength variability
        self.sfr.command_executor.GID(UnsolicitedData("GID"))
        return True

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        """
        Executes one iteration of mode
        For example: measure signal strength as the orbit location changes.
        NOTE: This method should not execute_buffers radio commands, that is done by command_executor class.
        """
        super().execute_cycle()
        # If enough time has passed and we haven't performed enough pings
        if self.ping_clock.time_elapsed() and self.pings_performed < self.NUMBER_OF_REQUIRED_PINGS:
            self.ping()  # Execute ping function
            self.ping_clock.update_time()
            if self.pings_performed == self.NUMBER_OF_REQUIRED_PINGS:  # If this was the final ping
                self.transmit_results()  # Transmit results
