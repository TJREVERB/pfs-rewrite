import time
import threading  # TODO: CHANGE THE WAY THIS IS DONE
from MainControlLoop.Mode.mode import Mode


class Startup(Mode):
    def __init__(self, sfr):
        """
        Sets up variables, runs a systems check, turns on the components used in start up, calls iridium.wave()
        """
        # constants
        """
        CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :) 
        """
        self.THIRTY_MINUTES = 5  # 1800 seconds in 30 minutes
        self.ANTENNA_WAIT_TIME = 120  # 120 seconds in 2 minutes
        self.ACKNOWLEDGEMENT = "Hello from TJ!"  # Acknowledgement message from ground station
        super().__init__(sfr=sfr, conditions={
            "BATTERY_DRAINED": False,
            "CONTACT_ESTABLISHED": False,
        })
        self.last_beacon_time = time.time()
        self.last_contact_attempt = time.time()


    def __str__(self):
        return "Startup"

    def start(self):
        self.integrate_charge()  # integrates the charge
        # variable to check last time beacon was called
        self.last_beacon_time = time.time()
        # Systems check
        self.eps.commands["All On"]()
        self.sfr.FAILURES = self.systems_check()
        self.eps.commands["All Off"]()  # Switch off all PDMs
        self.eps.commands["Pin On"]("Iridium")  # Switch on Iridium
        self.eps.commands["Pin On"]("UART-RS232")
        # Attempt to establish contact with ground
        self.iridium.wave(self.eps.commands["VBCROUT"](), self.eps.solar_power(), self.eps.total_power(4))

    def antenna(self):  # TODO: FIGURE OUT SOME WAY TO DEPLOY THE ANTENNA WITHOUT BLOCKING CODE EXECUTION
        if not self.sfr.ANTENNA_DEPLOYED:
            self.sfr.dump()
            # if 30 minutes have elapsed
            if time.time() - self.sfr.START_TIME > self.THIRTY_MINUTES:
                # Enable power to antenna deployer
                self.eps.commands["Pin On"]("Antenna Deployer")
                time.sleep(5)
                if self.antenna_deployer.deploy():  # Deploy antenna
                    self.eps.commands["Pin Off"]("Antenna Deployer")  # Disable power to antenna deployer
                else:
                    raise RuntimeError("ANTENNA FAILED TO DEPLOY")  # TODO: handle this somehow. But how? If this doesnt work we die
                self.sfr.dump()  # Log state field registry change

    def execute_cycle_normal(self):
        if time.time() > self.last_beacon_time + self.ANTENNA_WAIT_TIME:  # wait for antenna_wait_time to not spam beacons
            # Attempt to establish contact with ground
            self.iridium.wave(self.eps.commands["VBCROUT"](), self.eps.solar_power(), self.eps.total_power(4))
            self.antenna()  # Antenna deployment, doesn't run if antenna is already deployed
            self.last_contact_attempt = time.time()


    def execute_cycle_low_battery(self):
        self.eps.commands["All Off"]()  # turn everything off
        time.sleep(60*90)  # sleep for one full orbit

    def execute_cycle(self):
        if self.battery_low():
            self.execute_cycle_low_battery()
        else:
            self.execute_cycle_normal()

    def check_conditions(self):
        """
        Checks whether we should be in this mode
        """

        self.conditions["BATTERY_DRAINED"] = self.eps.commands["VBCROUT"] < self.LOWER_THRESHOLD
        self.conditions["CONTACT_ESTABLISHED"] = self.sfr.IRIDIUM_RECEIVED_COMMAND.contains(self.ACKNOWLEDGEMENT)
        if self.conditions["CONTACT_ESTABLISHED"]:
            return False  # Return false contact is established; if battery drained, it will execute
            # exeute_cycle_low_battery
        return True

    def startup_complete(self):
        # boolean method to check if start up is complete
        return self.conditions["CONTACT_ESTABLISHED"]

    def battery_low(self):
        # boolean method to check if the battery is low
        return self.conditions["BATTERY_DRAINED"]

    def switch_modes(self):
        super(Startup, self).switch_modes()  # Run switch_modes of superclass

        if self.startup_complete():  # if start up complete, can successfully exit startup
            if self.conditions["CONTACT_ESTABLISHED"]:
                if self.conditions["BATTERY_DRAINED"]:
                    self.sfr.MODE = self.sfr.modes_list["CHARGING"]
                else:
                    self.sfr.MODE = self.sfr.modes_list["SCIENCE"]
        # else, just stay in start up, even if battery is drained, because it will execute the low battery execute
        # method
