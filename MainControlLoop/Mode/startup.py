import time
from MainControlLoop.Mode.mode import Mode
from Drivers.transmission_packet import UnsolicitedData
from lib.exceptions import wrap_errors, LogicalError
from lib.clock import Clock


class Startup(Mode):
    ANTENNA_WAIT_TIME = 15  # TODO: CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :) 1800 seconds

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Initializes constants specific to instance of Mode
        :param sfr: Reference to :class: 'MainControlLoop.lib.registry.StateFieldRegistry'
        :type sfr: :class: 'MainControlLoop.lib.registry.StateFieldRegistry'
        """
        super().__init__(sfr)
        self.beacon = Clock(120)

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns mode name as string
        :return: mode name
        :rtype: str
        """
        return "Startup"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        """
        Runs initial setup for a mode. Turns on and off devices for a specific mode.
        """
        super().start(["Iridium"])

    @wrap_errors(LogicalError)
    def deploy_antenna(self) -> bool:
        """
        Attempt to deploy antenna if antenna isn't deployed, we've detumbled, and enough time has passed
        :return: whether antenna was deployed successfully
        :rtype: bool
        """
        if self.sfr.vars.ANTENNA_DEPLOYED or self.sfr.imu.is_tumbling() or \
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
            return False
        return True

    @wrap_errors(LogicalError)
    def ping(self) -> bool:
        """
        Attempt to establish contact with ground
        :return: whether function ran successfully
        :rtype: bool
        """
        print("Transmitting proof of life...")
        self.sfr.command_executor.GPL(UnsolicitedData("GPL"))
        return True

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        """
        Executes one iteration of mode
        For example: measure signal strength as the orbit location changes.
        """
        super().execute_cycle()
        if self.sfr.check_lower_threshold():  # Execute cycle low battery
            self.sfr.all_off()  # turn everything off
            self.sfr.sleep(5400)  # sleep for one full orbit
            self.start()  # Run start again to turn on devices
        else:  # Execute cycle normal
            self.sfr.power_on(self.sfr.vars.PRIMARY_RADIO)  # Make sure primary radio is on
            # If aprs and antenna deployer aren't locked off
            if "APRS" not in self.sfr.vars.LOCKED_OFF_DEVICES and \
                    "Antenna Deployer" not in self.sfr.vars.LOCKED_OFF_DEVICES:
                self.deploy_antenna()  # Attempt to deploy antenna (checks other conditions required for deployment)
            if self.beacon.time_elapsed():
                self.ping()  # Attempt to establish contact every 2 minutes
                self.beacon.update_time()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if not self.sfr.vars.CONTACT_ESTABLISHED:
            return self  # If contact hasn't been established, stay in startup
        elif ("APRS" not in self.sfr.vars.LOCKED_OFF_DEVICES and
              "Antenna Deployer" not in self.sfr.vars.LOCKED_OFF_DEVICES) and not self.sfr.vars.ANTENNA_DEPLOYED:
            return self  # If antenna hasn't been deployed and it's possible to deploy the antenna, stay in startup
        elif self.sfr.check_lower_threshold():  # Charging if we can switch but are low on power
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Science"])
        else:  # Science if we can switch and have enough power
            return self.sfr.modes_list["Science"](self.sfr)
