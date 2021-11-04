from MainControlLoop.Mode.mode import Mode
import gc


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
        super().__init__(sfr, conditions={

        })

        self.limited_command_registry = {
            # Reads and transmits battery voltage
            "BVT": lambda: self.aprs.write("TJ;" + str(self.eps.telemetry["VBCROUT"]())),
            # Transmit total power draw of connected components
            "PWR": lambda: self.aprs.write("TJ;" + str(self.eps.total_power(3)[0])),
            # Calculate and transmit Iridium signal strength variability
            "SSV": lambda: self.aprs.write("TJ;SSV:" + str(self.sfr.signal_strength_variability())),
            # Transmit current solar panel production
            "SOL": lambda: self.aprs.write("TJ;SOL:" + str(self.eps.solar_power())),
        }

    def __str__(self):
        return "Outreach"