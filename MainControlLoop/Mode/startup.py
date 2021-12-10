import time
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket
from MainControlLoop.lib.exceptions import decorate_all_callables, wrap_errors, SystemError


class Startup(Mode):
    wrap_errors(SystemError)
    def __init__(self, sfr):
        """
        Sets up constants
        """
        super().__init__(sfr)
        # CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :) 
        self.THIRTY_MINUTES = 1800  # 1800 seconds in 30 minutes
        self.BEACON_WAIT_TIME = 120  # 2 minutes

        self.last_contact_attempt = 0
        self.conditions = {
            "Low Battery": False,
        }
        decorate_all_callables(self, SystemError)

    def __str__(self):
        return "Startup"

    def start(self) -> None:
        super(Startup, self).start()
        self.instruct["Pin On"]("Iridium")
        self.instruct["All Off"](exceptions=["Iridium"])
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD

    def antenna(self) -> None:
        if not self.sfr.vars.ANTENNA_DEPLOYED:
            # if 30 minutes have elapsed
            if time.time() - self.sfr.vars.START_TIME > self.THIRTY_MINUTES:
                # Enable power to antenna deployer
                self.instruct["Pin On"]("Antenna Deployer")
                time.sleep(5)
                if not self.sfr.devices["Antenna Deployer"].deploy():  # Deploy antenna
                    raise RuntimeError("ANTENNA FAILED TO DEPLOY")  # TODO: handle this somehow

    def execute_cycle(self) -> None:
        super(Startup, self).execute_cycle()
        if self.conditions["Low Battery"]:  # Execute cycle low battery
            self.instruct["All Off"]()  # turn everything off
            time.sleep(60 * 90)  # sleep for one full orbit
        else:  # Execute cycle normal
            self.instruct["Pin On"](self.sfr.vars.PRIMARY_RADIO)
            # TODO: HANDLE THIS BETTER
            try:
                self.read_radio()  # only reads radio if not low battery
                self.transmit_radio()
                self.check_time()
            except RuntimeError as e:
                print(e)
            # wait for BEACON_WAIT_TIME to not spam beacons
            if time.time() > self.last_contact_attempt + self.BEACON_WAIT_TIME:
                self.antenna()  # Antenna deployment, does nothing if antenna is already deployed
                # Attempt to establish contact with ground
                # TOOD: HANDLE THIS BETTER
                self.sfr.command_executor.GPL(TransmissionPacket("GPL", [], 0))
                self.last_contact_attempt = time.time()

    def read_radio(self):
        super(Startup, self).read_radio()
    
    def transmit_radio(self):
        return super(Startup, self).transmit_radio()

    def check_time(self):
        return super(Startup, self).check_time()


    def check_conditions(self) -> bool:
        super(Startup, self).check_conditions()
        return self.sfr.vars.CONTACT_ESTABLISHED is False  # if contact not established, stay in charging

    def switch_mode(self):
        self.sfr.LAST_MODE_SWITCH = time.time()
        if self.conditions["Low Battery"]:  # If battery is low
            return self.sfr.modes_list("Charging")
        else:
            return self.sfr.modes_list("Science")

    def update_conditions(self) -> None:
        super(Startup, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD

    def terminate_mode(self) -> None:
        super(Startup, self).terminate_mode()
        pass
