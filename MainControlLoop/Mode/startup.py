import time
from MainControlLoop.Mode.mode import Mode
from Drivers.transmission_packet import UnsolicitedData, UnsolicitedString
from lib.exceptions import wrap_errors, LogicalError
from lib.clock import Clock


class Startup(Mode):
    """
    This is the mode we boot into as soon as we deploy from the ISS
    The condition for entering this mode (checked in mcl) is that the antenna has not been deployed
    And neither the antenna deployer nor the APRS is locked off
    Deploys antenna after minimum threshold if we're detumbled
    Deploys antenna after maximum threshold regardless of tumble status
    Establishes contact with ground
    """
    ANTENNA_WAIT_TIME = 15  # TODO: CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :) 1800 seconds
    ANTENNA_MAXIMUM_THRESHOLD = 5400  # TODO: CHANGE ARBITRARY VALUE

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        :param sfr: sfr object
        :type sfr: :class: 'lib.registry.StateFieldRegistry'
        """
        super().__init__(sfr)
        self.beacon = Clock(120)

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns 'Startup'
        :return: mode name
        :rtype: str
        """
        return "Startup"

    @wrap_errors(LogicalError)
    def start(self) -> bool:
        """
        Starts with only Iridium in order to establish contact
        Primary radio is switched automatically in mission control if packets in the transmission queue fail to transmit
        Returns False if we're not supposed to be in this mode due to locked devices
        :return: whether we're supposed to be in this mode
        :rtype: bool
        """
        return super().start(["Iridium"])

    @wrap_errors(LogicalError)
    def deploy_antenna(self) -> bool:
        """
        Attempt to deploy antenna if antenna isn't deployed, we've detumbled, and enough time has passed
        Also deploy antenna if we've passed the maximum threshold for time to wait before deployment
        :return: whether antenna was deployed successfully
        :rtype: bool
        """
        if self.sfr.vars.ANTENNA_DEPLOYED:  # If the antenna has already been deployed, do nothing
            print("Antenna already deployed")
            return False
        # If aprs and antenna deployer are locked off, do nothing
        if "APRS" in self.sfr.vars.LOCKED_OFF_DEVICES and \
                "Antenna Deployer" in self.sfr.vars.LOCKED_OFF_DEVICES:
            print("APRS and Antenna deployer locked off")
            return False
        # If not enough time has passed to deploy the antenna, do nothing
        elif time.time() < self.sfr.vars.START_TIME + self.ANTENNA_WAIT_TIME:
            print("Time not elapsed")
            return False
        # If we haven't yet reached the maximum threshold of time to wait for antenna deployment
        if not time.time() > self.sfr.vars.START_TIME + self.ANTENNA_MAXIMUM_THRESHOLD:
            if self.sfr.devices["IMU"].is_tumbling():  # If we're still tumbling
                print("currently tumbling")
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
            self.sfr.vars.LOCKED_OFF_DEVICES.update({"Antenna Deployer", "APRS"})
            self.sfr.vars.FAILURES.append("Antenna Deployer")
            self.sfr.command_executor.transmit(UnsolicitedString(
                "Antenna deployment failed, Iridium is now primary radio"))
            return False
        print("Antenna deployment successful")
        return True

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        """
        Executes one iteration of Startup mode
        If battery is low, powers off for an orbit to recharge
        Attempt to deploy antenna (see deploy_antenna for conditions)
        Every 2 minutes, attempt to establish contact by transmitting proof of life
        """
        super().execute_cycle()
        if self.sfr.check_lower_threshold():  # Execute cycle low battery
            self.sfr.all_off()  # turn everything off
            print("Sleeping")
            self.sfr.sleep(120)  # sleep for one full orbit #TODO: replace with 5400
            self.start()  # Run start again to turn on devices
        # Make sure primary radio is on (may change in mission control if Iridium packets don't transmit)
        self.sfr.power_on(self.sfr.vars.PRIMARY_RADIO)
        self.deploy_antenna()  # Attempt to deploy antenna (checks conditions required for deployment)
        if self.beacon.time_elapsed():
            if not self.sfr.vars.CONTACT_ESTABLISHED:  # Attempt to establish contact every 2 minutes
                print("Transmitting proof of life...")
                self.sfr.command_executor.GPL(UnsolicitedData("GPL"))
            self.beacon.update_time()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        """
        If contact hasn't been established, always stay in Startup
        If contact has been established but antenna is not deployed (and neither the antenna deployer
            nor APRS are locked off), stay in Startup
        If above conditions to leave Startup are satisfied, set final mode to Science if Iridium isn't locked off,
            otherwise Outreach
        If we're then low on power, suggest Charging -> final mode
        Otherwise if we have sufficient power, suggest final mode
        """
        super().suggested_mode()
        if not self.sfr.vars.CONTACT_ESTABLISHED:
            print("Contact not established")
            return self  # If contact hasn't been established, stay in startup
        elif ("APRS" not in self.sfr.vars.LOCKED_OFF_DEVICES and
              "Antenna Deployer" not in self.sfr.vars.LOCKED_OFF_DEVICES) and not self.sfr.vars.ANTENNA_DEPLOYED:
            print("Antenna still can be deployed")
            return self  # If antenna hasn't been deployed and it's possible to deploy the antenna, stay in startup
        else:  # If we can switch out of this mode
            final_mode = self.sfr.modes_list["Science"] if "Iridium" not in self.sfr.vars.LOCKED_OFF_DEVICES \
                else self.sfr.modes_list["Outreach"]  # End up in Science if Iridium is unlocked, otherwise Outreach
            # Leave to charging to make sure we have enough power for the next mode
            return self.sfr.modes_list["Charging"](self.sfr, final_mode)
