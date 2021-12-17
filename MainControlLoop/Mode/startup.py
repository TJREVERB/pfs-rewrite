import time
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Startup(Mode):
    # TODO: CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :)
    THIRTY_MINUTES = 15  # 1800 seconds in 30 minutes
    BEACON_WAIT_TIME = 120  # 2 minutes

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Sets up constants
        """
        super().__init__(sfr)
        self.last_contact_attempt = 0
        self.start = self.recovery_start if self.sfr.vars.ANTENNA_DEPLOYED else self.true_start
        self.execute_cycle = self.recovery_exec if self.sfr.vars.ANTENNA_DEPLOYED else self.startup_exec

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Startup"

    @wrap_errors(LogicalError)
    def true_start(self):
        """
        If we booted into startup mode right after deploying from ISS (antenna not deployed)
        """
        super().start([self.sfr.vars.PRIMARY_RADIO, "Iridium"])

    @wrap_errors(LogicalError)
    def recovery_start(self):
        """
        If we booted into recovery mode
        """
        super().start([self.sfr.vars.PRIMARY_RADIO, "Iridium"])

    @wrap_errors(LogicalError)
    def antenna(self) -> None:
        if not self.sfr.vars.ANTENNA_DEPLOYED and not self.sfr.imu.is_tumbling() and \
                time.time() - self.sfr.vars.START_TIME > self.THIRTY_MINUTES:
            # Enable power to antenna deployer
            self.sfr.instruct["Pin On"]("Antenna Deployer")
            time.sleep(5)
            self.sfr.devices["Antenna Deployer"].deploy()  # Deploy antenna
            print("Antenna Deployed")

    @wrap_errors(LogicalError)
    def startup_exec(self):
        """
        If we just deployed from the ISS (antenna hasn't been deployed)
        """
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:  # Execute cycle low battery
            self.sfr.instruct["All Off"]()  # turn everything off
            time.sleep(self.sfr.vars.ORBITAL_PERIOD)  # sleep for one full orbit
            self.start()
        else:  # Execute cycle normal
            self.sfr.instruct["Pin On"](self.sfr.vars.PRIMARY_RADIO)  # TODO: DON'T PIN ON EVERY SINGLE CYCLE
            # wait for BEACON_WAIT_TIME to not spam beacons
            if time.time() > self.last_contact_attempt + self.BEACON_WAIT_TIME:
                self.antenna()  # Antenna deployment, does nothing if antenna is already deployed
                # Attempt to establish contact with ground
                print("Transmitting proof of life...")
                self.sfr.command_executor.GPL(TransmissionPacket("GPL", [], 0))
                self.last_contact_attempt = time.time()

    @wrap_errors(LogicalError)
    def recovery_exec(self):
        """
        If our satellite shut down and rebooted
        """
        pass

    @wrap_errors(LogicalError)
    def startup_suggested_mode(self) -> Mode:
        """
        If our satellite just deployed
        """
        super().suggested_mode()
        if not self.sfr.vars.ANTENNA_DEPLOYED or not self.sfr.vars.CONTACT_ESTABLISHED:  # Necessary startup tasks
            return self
        elif self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Science"])
        else:
            return self.sfr.modes_list["Science"](self.sfr)

    @wrap_errors(LogicalError)
    def recovery_suggested_mode(self) -> Mode:
        """
        If our satellite is in recovery mode
        """
        pass

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if not self.sfr.vars.ANTENNA_DEPLOYED or not self.sfr.vars.CONTACT_ESTABLISHED:  # Necessary startup tasks
            return self
        elif self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Science"])
        else:
            return self.sfr.modes_list["Science"](self.sfr)
