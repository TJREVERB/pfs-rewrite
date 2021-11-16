import time
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.outreach import Outreach
from MainControlLoop.Mode.repeater import Repeater

class Startup(Mode):
    def __init__(self, sfr):
        """
        Sets up variables, runs a systems check, turns on the components used in start up, calls iridium.wave()
        """
        # constants
        """
        CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :) 
        """
        super().__init__(sfr)
        self.THIRTY_MINUTES = 5  # 1800 seconds in 30 minutes
        self.ANTENNA_WAIT_TIME = 120  # 120 seconds in 2 minutes
        self.ACKNOWLEDGEMENT = "Hello from TJ!"  # Acknowledgement message from ground station
        self.contact_established = False  # boolean for if contact with ground station has been made
        self.last_beacon_time = time.time()
        self.last_contact_attempt = time.time()

    def __str__(self):
        return "Startup"

    def start(self):
        super(Startup, self).start()
        # Why is this line here? Shouldn't we be integrating charge in every cycle, not in start?
        self.integrate_charge()  # integrates the charge
        # variable to check last time beacon was called
        self.last_beacon_time = time.time()

    def antenna(self):
        if not self.sfr.ANTENNA_DEPLOYED:
            self.sfr.dump()
            # if 30 minutes have elapsed
            if time.time() - self.sfr.START_TIME > self.THIRTY_MINUTES:
                # Enable power to antenna deployer
                self.instruct["Pin On"]("Antenna Deployer")
                time.sleep(5)
                if self.sfr.devices["Antenna Deployer"].deploy():  # Deploy antenna
                    self.instruct["Pin Off"]("Antenna Deployer")  # Disable power to antenna deployer
                else:
                    raise RuntimeError("ANTENNA FAILED TO DEPLOY")  # TODO: handle this somehow
                self.sfr.dump()  # Log state field registry change

    def execute_cycle_normal(self):
        self.instruct["Pin On"](self.sfr.PRIMARY_RADIO)
        if time.time() > self.last_beacon_time + self.ANTENNA_WAIT_TIME:  # wait for antenna_wait_time to not spam beacons
            self.antenna()  # Antenna deployment, does nothing if antenna is already deployed
            if self.sfr.ANTENNA_DEPLOYED:  # Attempt to establish contact with ground
                self.sfr.devices["Iridium"].wave(self.sfr.eps.commands["VBCROUT"](), self.sfr.eps.solar_power(), self.sfr.eps.total_power(4))
                self.last_contact_attempt = time.time()

    def execute_cycle_low_battery(self):
        self.instruct["All Off"]()  # turn everything off
        time.sleep(60*90)  # sleep for one full orbit

    def execute_cycle(self):
        super(Startup, self).execute_cycle()
        if self.sfr.eps.commands["VBCROUT"] < self.LOWER_THRESHOLD:
            self.execute_cycle_low_battery()
        else:
            self.execute_cycle_normal()

    def check_conditions(self):
        """
        Checks whether we should be in this mode
        """
        self.contact_established = self.sfr.IRIDIUM_RECEIVED_COMMAND.contains(self.ACKNOWLEDGEMENT)
        if self.contact_established:
            return False  # Return false contact is established
        else:
            return True

    def switch_modes(self):
        super(Startup, self).switch_modes()
        if self.contact_established:  # if start up complete, can successfully exit startup
            if self.sfr.eps.commands["VBCROUT"] < self.LOWER_THRESHOLD:
                return Charging
            else:
                return Science
        # else, just stay in start up, even if battery is drained, because it will execute the low battery execute
        # method
