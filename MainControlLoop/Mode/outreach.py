from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.charging import Charging

import gc
import time


"""
        Satellite's control flow in OUTREACH mode.
        Enters OUTREACH mode, serves as outreach platform until charge depletes to LOWER_THRESHOLD
        Iridium and APRS are always on.
        
        self.sfr.MODE = "OUTREACH"
        self.eps.commands["All On"]()
        while self.eps.telemetry["VBCROUT"]() > self.LOWER_THRESHOLD:
            self.iridium.listen()
            self.aprs.read()
            self.command_interpreter()
            self.sfr.dump()
        self.sfr.MODE = "CHARGING"
        self.sfr.dump()  # Log mode switch
"""


class Outreach(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)

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
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")

    def check_conditions(self):
        if self.sfr.eps.telemetry["VBCROUT"]() > self.LOWER_THRESHOLD:  # if voltage greater than lower thres
            return True
        else:
            return False

    def execute_cycle(self):
        self.sfr.devices["APRS"].read()
            
        if self.sfr.APRS_RECIEVED_COMMAND != "":  # Check if there are any commands from outreach
            raw_command = self.sfr.APRS_RECIEVED_COMMAND
            command = raw_command[raw_command.find("TJ;") + 3:raw_command.find("TJ;") + 6]
            self.limited_command_registry[command]()

    
    def switch_modes(self):
        return Charging

    def terminate_mode(self):
        self.instruct["Pin Off"]("Iridium")
        self.instruct["Pin Off"]("APRS")