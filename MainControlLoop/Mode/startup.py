import time
from MainControlLoop.Mode.mode import Mode
from Drivers.transmission_packet import UnsolicitedData, UnsolicitedString
from lib.exceptions import wrap_errors, LogicalError
from lib.clock import Clock


class Startup(Mode):
    ANTENNA_WAIT_TIME = 15  # TODO: CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :) 1800 seconds
    ANTENNA_MAXIMUM_THRESHOLD = 5400  # TODO: CHANGE ARBITRARY VALUE

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
        if self.sfr.vars.ANTENNA_DEPLOYED:  # If the antenna has already been deployed, do nothing
            return False
        # If aprs and antenna deployer are locked off, do nothing
        if "APRS" not in self.sfr.vars.LOCKED_OFF_DEVICES and \
                "Antenna Deployer" not in self.sfr.vars.LOCKED_OFF_DEVICES:
            return False
        # If not enough time has passed to deploy the antenna, do nothing
        elif time.time() < self.sfr.vars.START_TIME + self.ANTENNA_WAIT_TIME:
            return False
        # If we haven't yet reached the maximum threshold of time to wait for antenna deployment
        if not time.time() > self.sfr.vars.START_TIME + self.ANTENNA_MAXIMUM_THRESHOLD:
            if self.sfr.imu.is_tumbling():  # If we're still tumbling
                return False  # Do nothing
        # Enable power to antenna deployer
        self.sfr.power_on("Antenna Deployer")
        time.sleep(5)
        self.sfr.devices["Antenna Deployer"].deploy()  # Deploy antenna
        print("Antenna deployment attempted")
        self.sfr.sleep(30)
        self.sfr.devices["Antenna Deployer"].check_deployment()
        if not self.sfr.vars.ANTENNA_DEPLOYED:  # If antenna deployment failed
            print("Antenna deployment unsuccessful")
            # Lock off antenna deployer/aprs and set primary radio to iridium
            # better to use nonfunctional radio than send power to a loadless aprs
            self.sfr.power_off("Antenna Deployer")
            self.sfr.set_primary_radio("Iridium", True)
            self.sfr.vars.LOCKED_OFF_DEVICES += ["Antenna Deployer", "APRS"]
            self.sfr.vars.FAILURES.append("Antenna Deployer")
            self.sfr.command_executor.transmit(UnsolicitedString(
                "Antenna deployment failed, Iridium is now primary radio"))
            return False
        print("Antenna deployment successful")
        return True

    @wrap_errors(LogicalError)
    def ping(self) -> bool:
        """
        Attempt to establish contact with ground
        :return: whether function ran successfully
        :rtype: bool
        """
        if self.sfr.vars.CONTACT_ESTABLISHED:
            return False
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
            self.deploy_antenna()  # Attempt to deploy antenna (checks conditions required for deployment)
            if self.beacon.time_elapsed():
                self.ping()  # Attempt to establish contact every 2 minutes (checks if contact is already established)
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
