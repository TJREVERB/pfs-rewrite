import time
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Startup(Mode):
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Sets up constants
        """
        super().__init__(sfr)
        # CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :) 
        self.THIRTY_MINUTES = 15  # 1800 seconds in 30 minutes
        self.BEACON_WAIT_TIME = 120  # 2 minutes

        self.last_contact_attempt = 0
        self.conditions = {
            "Tumbling": True
        }

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Startup"

    @wrap_errors(LogicalError)
    def start(self) -> None:
        super(Startup, self).start()
        self.sfr.instruct["Pin On"]("Iridium")
        self.sfr.instruct["All Off"](exceptions=["Iridium"])
        self.conditions["Low Battery"] = self.sfr.battery.telemetry["VBAT"]() < self.LOWER_THRESHOLD

    @wrap_errors(LogicalError)
    def antenna(self) -> None:
        if not self.sfr.vars.ANTENNA_DEPLOYED:
            # if 30 minutes have elapsed
            if time.time() - self.sfr.vars.START_TIME > self.THIRTY_MINUTES:
                # Enable power to antenna deployer
                self.sfr.instruct["Pin On"]("Antenna Deployer")
                time.sleep(5)
                self.sfr.devices["Antenna Deployer"].deploy()  # Deploy antenna
                print("Antenna Deployed")

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        super(Startup, self).execute_cycle()
        if self.conditions["Low Battery"]:  # Execute cycle low battery
            self.sfr.instruct["All Off"]()  # turn everything off
            time.sleep(60 * 90)  # sleep for one full orbit
        else:  # Execute cycle normal
            self.sfr.instruct["Pin On"](self.sfr.vars.PRIMARY_RADIO)
            self.read_radio()  # only reads radio if not low battery
            self.transmit_radio()
            self.check_time()
            # wait for BEACON_WAIT_TIME to not spam beacons
            if time.time() > self.last_contact_attempt + self.BEACON_WAIT_TIME:
                self.antenna()  # Antenna deployment, does nothing if antenna is already deployed
                # Attempt to establish contact with ground
                # TOOD: HANDLE THIS BETTER
                print("Transmitting proof of life...")
                self.sfr.command_executor.GPL(TransmissionPacket("GPL", [], 0))
                self.last_contact_attempt = time.time()

    @wrap_errors(LogicalError)
    def read_radio(self):
        super(Startup, self).read_radio()

    @wrap_errors(LogicalError)
    def transmit_radio(self):
        return super(Startup, self).transmit_radio()

    @wrap_errors(LogicalError)
    def check_time(self):
        return super(Startup, self).check_time()

    @wrap_errors(LogicalError)
    def check_conditions(self) -> bool:
        super(Startup, self).check_conditions()
        df = self.sfr.logs["imu"].read().tail(5) 
        return self.sfr.vars.CONTACT_ESTABLISHED is False  # if contact not established, stay in charging

    @wrap_errors(LogicalError)
    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        if self.conditions["Low Battery"]:  # If battery is low
            return self.sfr.modes_list("Charging")
        else:
            return self.sfr.modes_list("Science")

    @wrap_errors(LogicalError)
    def update_conditions(self) -> None:
        super(Startup, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.battery.telemetry["VBAT"]() < self.LOWER_THRESHOLD

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        super(Startup, self).terminate_mode()
        pass
