import time
import threading  # TODO: CHANGE THE WAY THIS IS DONE
from MainControlLoop.Mode.mode import Mode


class Startup(Mode):
    def __init__(self, sfr):
        """

        """
        self.THIRTY_MINUTES = 5  # 1800 seconds in 30 minutes
        self.ACKNOWLEDGEMENT = "Hello from TJ!"  # Acknowledgement message from ground station
        super().__init__(sfr=sfr, conditions={
            "BATTERY_DRAINED": False,
            "CONTACT_ESTABLISHED": False,
        })
        # Systems check
        self.eps.commands["All On"]()
        self.sfr.FAILURES = self.systems_check()
        # Switch off all PDMs
        self.eps.commands["All Off"]()
        # Consider changing thread to asyncio later
        threading.Thread(target=self.antenna).start()  # TODO: REMOVE
        self.eps.commands["Pin On"]("Iridium")  # Switch on Iridium
        self.eps.commands["Pin On"]("UART-RS232")
        # Fields for iridium.wave()
        solar_generation = self.eps.solar_power()
        battery_voltage = self.eps.commands["VBCROUT"]()
        current_output = self.eps.total_power(4)
        self.last_contact_attempt = time.time()
        # Attempt to establish contact with ground
        self.iridium.wave(battery_voltage, solar_generation, current_output)

    def antenna(self):  # TODO: FIGURE OUT SOME WAY TO DEPLOY THE ANTENNA WITHOUT BLOCKING CODE EXECUTION
        if not self.sfr.ANTENNA_DEPLOYED:
            self.sfr.dump()
            # if 30 minutes have elapsed
            if time.time() - self.sfr.START_TIME > self.THIRTY_MINUTES:
                # Enable power to antenna deployer
                self.eps.commands["Pin On"]("Antenna Deployer")
                time.sleep(5)
                if self.antenna_deployer.deploy():  # Deploy antenna
                    print("deployed")
                    self.eps.commands["Pin Off"]("Antenna Deployer")  # Disable power to antenna deployer
                else:
                    raise RuntimeError("ANTENNA FAILED TO DEPLOY")  # TODO: handle this somehow
                self.sfr.dump()  # Log state field registry change

    def execute_cycle(self):
        super(Startup, self).execute_cycle()  # Run execute_cycle of superclass
        self.antenna()  # Antenna deployment, doesn't run if antenna is already deployed
        # Fields for iridium.wave()
        solar_generation = self.eps.solar_power()
        battery_voltage = self.eps.commands["VBCROUT"]()
        current_output = self.eps.total_power(4)
        self.last_contact_attempt = time.time()
        # Attempt to establish contact with ground
        self.iridium.wave(battery_voltage, solar_generation, current_output)
        time.sleep(120)  # TODO: DON'T USE TIME.SLEEP, ITERATE AND CHECK FOR ELAPSED TIME SINCE LAST ATTEMPT

    def check_conditions(self):
        super(Startup, self).check_conditions()  # Run check_conditions of superclass
        self.conditions["BATTERY_DRAINED"] = self.eps.commands["VBCROUT"] < self.LOWER_THRESHOLD
        self.conditions["CONTACT_ESTABLISHED"] = self.sfr.IRIDIUM_RECEIVED_COMMAND.contains(self.ACKNOWLEDGEMENT)
        if self.conditions["BATTERY_DRAINED"] or self.conditions["CONTACT_ESTABLISHED"]:
            return False  # Return false if either battery has drained or contact is established
        return True

    def switch_modes(self):
        super(Startup, self).switch_modes()  # Run switch_modes of superclass
        # TODO: FIX THIS LOGIC
        if self.conditions["CONTACT_ESTABLISHED"]:
            if self.conditions["BATTERY_DRAINED"]:
                self.sfr.MODE = self.sfr.modes_list["CHARGING"]
            else:
                self.sfr.MODE = self.sfr.modes_list["SCIENCE"]
        else:
            self.sfr.MODE = self.sfr.modes_list["CHARGING"]
