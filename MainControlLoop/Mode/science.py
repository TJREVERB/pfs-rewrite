from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket
import time
from MainControlLoop.lib.exceptions import NoSignalException, wrap_errors, LogicalError


class Science(Mode):
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        super().__init__(sfr)
        self.last_ping = time.time()
        self.pings_performed = 0
        self.DATAPOINT_SPACING = 5  # in seconds, TODO: MAKE 60
        # self.NUMBER_OF_REQUIRED_PINGS = (90 * 60) / self.DATAPOINT_SPACING  # number of pings to do to complete orbit
        self.NUMBER_OF_REQUIRED_PINGS = 5  # DEBUG
        self.PRIMARY_IRIDIUM_WAIT_TIME = 5 * 60  # wait time for iridium polling if iridium is main radio
        self.SECONDARY_IRIDIUM_WAIT_TIME = 20 * 60  # wait time for iridium polling if iridium is not main radio
        self.conditions = {
            "Collection Complete": False,
            "Low Battery": False,
            "Iridium Status": True  # if iridium works (not locked off), True
        }

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Science"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super(Science, self).start()
        if self.sfr.vars.PRIMARY_RADIO == "APRS":
            self.instruct["Pin On"]("APRS")
        self.instruct["Pin On"]("Iridium")
        self.instruct["All Off"](exceptions=["APRS", "Iridium"])
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.sfr.vars.LOWER_THRESHOLD
        self.conditions["Collection Complete"] = self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS
        self.conditions["Iridium Status"] = self.sfr.devices["Iridium"] is not None

    @wrap_errors(LogicalError)
    def check_conditions(self) -> bool:
        super(Science, self).check_conditions()

        return self.conditions["Low Battery"] or self.conditions["Collection Complete"]

    @wrap_errors(LogicalError)
    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        return self.sfr.modes_list["Charging"]

    @wrap_errors(LogicalError)
    def update_conditions(self) -> None:
        super(Science, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.sfr.vars.LOWER_THRESHOLD
        self.conditions["Collection Complete"] = self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS
        self.conditions["Iridium Status"] = self.sfr.devices["Iridium"] is not None

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        self.read_radio()
        self.transmit_radio()
        self.check_time()
        super(Science, self).execute_cycle()

        if self.pings_performed >= self.NUMBER_OF_REQUIRED_PINGS:
            print("Transmitting results...")
            # Transmit signal strength variability
            pckt = TransmissionPacket("GSV", [], 0)
            self.sfr.command_executor.GSV(pckt)
            self.pings_performed += 1 
        elif time.time() - self.last_ping >= self.DATAPOINT_SPACING:
            print("Recording signal strength ping " + str(self.pings_performed + 1) + "...")
            try:
                self.sfr.log_iridium(self.sfr.devices["Iridium"].processed_geolocation(),
                                    self.sfr.devices["Iridium"].RSSI())  # Log Iridium data
            except NoSignalException:
                print("No signal strength!")  # If there's no signal, wait for DATAPOINT_SPACING
            else:  # If data was successfully recorded, increase pings performed
                self.pings_performed += 1
            finally:  # Always update last_ping time to prevent spamming pings
                self.last_ping = time.time()

    @wrap_errors(LogicalError)
    def read_radio(self):
        super(Science, self).read_radio()

    @wrap_errors(LogicalError)
    def transmit_radio(self):
        return super(Science, self).transmit_radio()

    @wrap_errors(LogicalError)
    def check_time(self):
        return super(Science, self).check_time()

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        super(Science, self).terminate_mode()
