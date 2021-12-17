from numpy import nan
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket
import time
from MainControlLoop.lib.exceptions import NoSignalException, wrap_errors, LogicalError


class Science(Mode):
    DATAPOINT_SPACING = 5  # in seconds, TODO: MAKE 60
    # NUMBER_OF_REQUIRED_PINGS = (90 * 60) / self.DATAPOINT_SPACING  # number of pings to do to complete orbit
    NUMBER_OF_REQUIRED_PINGS = 5
    PRIMARY_IRIDIUM_WAIT_TIME = 5 * 60
    SECONDARY_IRIDIUM_WAIT_TIME = 20 * 60

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        super().__init__(sfr)
        self.last_ping = time.time()
        self.pings_performed = 0

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Science"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super().start()
        if self.sfr.vars.PRIMARY_RADIO == "APRS":
            self.sfr.instruct["Pin On"]("APRS")
        self.sfr.instruct["Pin On"]("IMU")
        self.sfr.instruct["Pin On"]("Iridium")
        self.sfr.instruct["All Off"](exceptions=["APRS", "Iridium", "IMU", "Antenna Deployer"])
        self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY = -1
        self.sfr.logs["iridium"].clear()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:  # If we're on low battery
            return self.sfr.modes_list["Charging"](self.sfr, type(self))  # Suggest charging
        elif self.sfr.devices["Iridium"](self.sfr) is None:  # If Iridium is off
            return self.sfr.modes_list["Outreach"](self.sfr)  # Suggest outreach
        elif self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY != -1:  # If we've finished getting our data
            return self.sfr.modes_list["Outreach"](self.sfr)  # Suggest outreach (we'll go to charging when necessary)
        return self  # Otherwise, stay in science

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        super().execute_cycle()
        if self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY != -1:  # If we've already calculated SSV
            pass  # Do nothing
        elif self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS:  # If we've performed enough pings
            print("Transmitting results...")
            # Transmit signal strength variability
            self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY = self.sfr.analytics.signal_strength_variability()
            self.sfr.command_executor.GSV(TransmissionPacket("GSV", [], 0))
        elif time.time() - self.last_ping >= self.DATAPOINT_SPACING:  # If it's time to perform a ping
            print("Recording signal strength ping " + str(self.pings_performed + 1) + "...")
            try:  # Log Iridium data
                self.sfr.log_iridium(self.sfr.devices["Iridium"].processed_geolocation(),
                                     self.sfr.devices["Iridium"].check_signal_active())
                print("Logged with connectivity")
            except NoSignalException:  # Log NaN geolocation, 0 signal strength
                self.sfr.log_iridium((nan, nan, nan), 0)
                print("Logged 0 connectivity")
            finally:  # Always update last_ping time to prevent spamming pings
                self.pings_performed += 1
                self.last_ping = time.time()
