import time
from MainControlLoop.Mode.mode import Mode
from Drivers.transmission_packet import UnsolicitedData
from lib.exceptions import wrap_errors, LogicalError
from lib.clock import Clock


class Startup(Mode):
    ANTENNA_WAIT_TIME = 15  # TODO: CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :)

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Sets up constants
        """
        super().__init__(sfr)
        self.beacon = Clock(self.ping, 120)

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Startup"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super().start(["Iridium"])

    @wrap_errors(LogicalError)
    def deploy_antenna(self) -> bool:
        """
        Attempt to deploy antenna if antenna isn't deployed, we've detumbled, and enough time has passed
        :return: (bool) whether function ran
        """
        if self.sfr.vars.ANTENNA_DEPLOYED or self.sfr.imu.is_tumbling or \
                time.time() < self.sfr.vars.START_TIME + self.ANTENNA_WAIT_TIME:
            return False
        # Enable power to antenna deployer
        self.sfr.power_on("Antenna Deployer")
        time.sleep(5)
        self.sfr.devices["Antenna Deployer"].deploy()  # Deploy antenna
        print("Antenna deployment attempted")
        time.sleep(30)
        self.sfr.devices["Antenna Deployer"].check_deployment()
        if self.sfr.vars.ANTENNA_DEPLOYED:
            print("Antenna deployment successful")
        else:
            print("Antenna deployment unsuccessful")
        return True

    @wrap_errors(LogicalError)
    def ping(self) -> bool:
        """
        Attempt to establish contact with ground
        :return: (bool) whether function ran
        """
        print("Transmitting proof of life...")
        self.sfr.command_executor.GPL(UnsolicitedData("GPL"))
        return True

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        super().execute_cycle()
        if self.sfr.check_lower_threshold():  # Execute cycle low battery
            self.sfr.all_off()  # turn everything off
            self.sfr.sleep(self.sfr.vars.ORBITAL_PERIOD)  # sleep for one full orbit
            self.start()  # Run start again to turn on devices
        else:  # Execute cycle normal
            self.sfr.power_on(self.sfr.vars.PRIMARY_RADIO)  # TODO: DON'T PIN ON EVERY SINGLE CYCLE
            self.deploy_antenna()
            self.beacon.execute()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if (not self.sfr.vars.ANTENNA_DEPLOYED or not self.sfr.vars.CONTACT_ESTABLISHED) and \
                ("APRS" not in self.sfr.vars.LOCKED_OFF_DEVICES and
                 "Antenna Deployer" not in self.sfr.vars.LOCKED_OFF_DEVICES):
            # if the antennae haven't been deployed, or contact hasn't been established, stay in startup mode as long
            # as the APRS and Antenna Deployer are not locked off
            return self
        elif self.sfr.check_lower_threshold():
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Science"])
        else:
            return self.sfr.modes_list["Science"](self.sfr)
