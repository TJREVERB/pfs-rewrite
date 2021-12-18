import time
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket
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
        self.last_contact_attempt = 0

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Startup"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super().start([self.sfr.vars.PRIMARY_RADIO, "Iridium"])

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
        self.sfr.instruct["Pin On"]("Antenna Deployer")
        time.sleep(5)
        self.sfr.devices["Antenna Deployer"].deploy()  # Deploy antenna
        print("Antenna Deployed")
        return True

    @wrap_errors(LogicalError)
    def ping(self) -> bool:
        """
        Attempt to establish contact with ground
        :return: (bool) whether function ran
        """
        print("Transmitting proof of life...")
        self.sfr.command_executor.GPL(TransmissionPacket("GPL", [], 0))
        return True

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        super().execute_cycle()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:  # Execute cycle low battery
            self.sfr.instruct["All Off"]()  # turn everything off
            time.sleep(self.sfr.vars.ORBITAL_PERIOD)  # sleep for one full orbit
            self.start()  # Run start again to turn on devices
        else:  # Execute cycle normal
            self.sfr.instruct["Pin On"](self.sfr.vars.PRIMARY_RADIO)  # TODO: DON'T PIN ON EVERY SINGLE CYCLE
            self.deploy_antenna()
            self.beacon.execute()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if not self.sfr.vars.ANTENNA_DEPLOYED or not self.sfr.vars.CONTACT_ESTABLISHED:  # Necessary startup tasks
            return self
        elif self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Science"])
        else:
            return self.sfr.modes_list["Science"](self.sfr)
