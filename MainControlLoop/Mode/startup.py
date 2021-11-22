import time
from MainControlLoop.Mode.mode import Mode


class Startup(Mode):
    def __init__(self, sfr):
        """
        Sets up constants
        """
        super().__init__(sfr)
        # CHANGE 30 MINUTES TO ACTUALLY BE 30 MINUTES :) 
        self.THIRTY_MINUTES = 1800  # 1800 seconds in 30 minutes
        self.BEACON_WAIT_TIME = 120  # 2 minutes
        # CHANGE TO ACCOMMODATE DATA BUDGET
        self.ACKNOWLEDGEMENT = "Hello from TJ!"  # Acknowledgement message from ground station

        self.PRIMARY_IRIDIUM_WAIT_TIME = 5 * 60  # wait time for iridium polling if iridium is main radio
        self.SECONDARY_IRIDIUM_WAIT_TIME = 20 * 60  # wait time for iridium polling if iridium is not main radio

        self.last_contact_attempt = 0
        self.conditions = {
            "Low Battery": False,
        }

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
            except RuntimeError as e:
                print(e)
            # wait for BEACON_WAIT_TIME to not spam beacons
            if time.time() > self.last_contact_attempt + self.BEACON_WAIT_TIME:
                self.antenna()  # Antenna deployment, does nothing if antenna is already deployed
                # Attempt to establish contact with ground
                # TOOD: HANDLE THIS BETTER
                try:
                    self.sfr.devices["Iridium"].wave(self.sfr.eps.telemetry["VBCROUT"](), 
                                                    self.sfr.eps.solar_power(), self.sfr.eps.total_power(4))
                except RuntimeError as e:
                    print(e)
                self.last_contact_attempt = time.time()

    def read_radio(self) -> None:
        """
        Main logic for reading messages from radio in Startup mode
        """
        super(Startup, self).read_radio()
        # If primary radio is iridium and enough time has passed
        if self.sfr.vars.PRIMARY_RADIO == "Iridium" and \
                time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, store them in sfr
            try:
                self.sfr.devices["Iridium"].next_msg()
            except RuntimeError as e:
                print(e)  # TODO: IMPLEMENT CONTINGENCIES
            self.last_iridium_poll_time = time.time()
        # If primary radio is aprs and enough time has passed
        elif self.sfr.vars.PRIMARY_RADIO == "APRS" and \
                time.time() - self.last_iridium_poll_time > self.SECONDARY_IRIDIUM_WAIT_TIME:
            # get all messages from iridium, store them in sfr
            try:
                self.sfr.devices["Iridium"].next_msg()
            except RuntimeError as e:
                print(e)  # TODO: IMPLEMENT CONTINGENCIES
            self.last_iridium_poll_time = time.time()
        # If APRS is on for whatever reason
        if self.sfr.devices["APRS"] is not None:
            # add aprs messages to sfr
            self.sfr.vars.APRS_RECEIVED_COMMAND.append(self.sfr.devices["APRS"].next_msg())
        # commands will be executed in the mode.py's super method for execute_cycle using a command executor

    def check_conditions(self) -> bool:
        super(Startup, self).check_conditions()
        if self.sfr.vars.CONTACT_ESTABLISHED:  # if contact established, get out of charging
            return False
        else:
            return True

    def switch_mode(self):
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
