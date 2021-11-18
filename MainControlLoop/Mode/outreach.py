from MainControlLoop.Mode.mode import Mode


class Outreach(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)

        self.conditions = {
            "Low Battery": False
        }
        self.limited_command_registry = {
            # Reads and transmits battery voltage
            "BVT": lambda: self.sfr.devices["APRS"].write("TJ;" + str(self.eps.telemetry["VBCROUT"]())),
            # Transmit total power draw of connected components
            "PWR": lambda: self.sfr.devices["APRS"].write("TJ;" + str(self.eps.total_power(3)[0])),
            # Calculate and transmit Iridium signal strength variability
            "SSV": lambda: self.sfr.devices["APRS"].write("TJ;SSV:" + str(self.sfr.signal_strength_variability())),
            # Transmit current solar panel production
            "SOL": lambda: self.sfr.devices["APRS"].write("TJ;SOL:" + str(self.eps.solar_power())),
        }

    def __str__(self):
        return "Outreach"

    def start(self):
        super(Outreach, self).start()
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")
        self.instruct["All Off"](exceptions=["Iridium", "APRS"])

    def check_conditions(self):
        super(Outreach, self).check_conditions()
        if self.conditions["Low Battery"]:
            self.sfr.MODE = self.sfr.modes_list["Charging"]
            return False
        else:
            return True

    def update_conditions(self):
        super(Outreach, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() > self.sfr.LOWER_THRESHOLD

    def execute_cycle(self):
        super(Outreach, self).execute_cycle() 
        self.sfr.devices["APRS"].read()
        #TODO: FIX
        if self.sfr.APRS_RECIEVED_COMMAND != "":  # Check if there are any commands from outreach
            raw_command = self.sfr.APRS_RECIEVED_COMMAND
            command = raw_command[raw_command.find("TJ;") + 3:raw_command.find("TJ;") + 6] # TODO: Edit this to call command_executor
            self.limited_command_registry[command]()

    def terminate_mode(self):
        super(Outreach, self).terminate_mode()
        pass

    def __str__(self):
        return "Outreach"
