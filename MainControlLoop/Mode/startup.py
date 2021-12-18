import time
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket
from lib.exceptions import wrap_errors, LogicalError
from lib.clock import Clock


class Startup(Mode):
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Sets up constants
        """
        super().__init__(sfr)
        self.clocks |= {
            # TODO: CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :)
            "Antenna": Clock(self.deploy_antenna, delay=15, conditions=[  # 1800 seconds = 30 minutes
                lambda: self.sfr.vars.ANTENNA_DEPLOYED,
                lambda: not self.sfr.imu.is_tumbling,
            ]),
            # Beacon proof of life to ground every 120 seconds (mode switches if contact is established)
            "Beacon": Clock(self.ping, delay=120),
        }
        self.last_contact_attempt = 0

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Startup"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super().start([self.sfr.vars.PRIMARY_RADIO, "Iridium"])

    @wrap_errors(LogicalError)
    def deploy_antenna(self) -> None:
        # Enable power to antenna deployer
        self.sfr.instruct["Pin On"]("Antenna Deployer")
        time.sleep(5)
        self.sfr.devices["Antenna Deployer"].deploy()  # Deploy antenna
        print("Antenna Deployed")

    @wrap_errors(LogicalError)
    def ping(self) -> None:
        # Attempt to establish contact with ground
        print("Transmitting proof of life...")
        self.sfr.command_executor.GPL(TransmissionPacket("GPL", [], 0))

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        super().execute_cycle()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:  # Execute cycle low battery
            self.sfr.instruct["All Off"]()  # turn everything off
            time.sleep(self.sfr.vars.ORBITAL_PERIOD)  # sleep for one full orbit
            self.start()  # Run start again to turn on devices
        else:  # Execute cycle normal
            self.sfr.instruct["Pin On"](self.sfr.vars.PRIMARY_RADIO)  # TODO: DON'T PIN ON EVERY SINGLE CYCLE

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        super().suggested_mode()
        if not self.sfr.vars.ANTENNA_DEPLOYED or not self.sfr.vars.CONTACT_ESTABLISHED:  # Necessary startup tasks
            return self
        elif self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:
            return self.sfr.modes_list["Charging"](self.sfr, self.sfr.modes_list["Science"])
        else:
            return self.sfr.modes_list["Science"](self.sfr)
