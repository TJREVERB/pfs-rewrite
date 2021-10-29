

class CommandExecutor:
    command_registry = {
        "TST": lambda: self.iridium.commands["Transmit"]("TJ;Hello"),  # Test method, transmits "Hello"
        # Reads and transmits battery voltage
        "BVT": lambda: self.iridium.commands["Transmit"]("TJ;" + str(self.eps.telemetry["VBCROUT"]())),
        "CHG": self.charging_mode(),  # Enters charging mode
        "SCI": self.science_mode(self.NUM_DATA_POINTS, self.NUM_SCIENCE_MODE_ORBITS),  # Enters science mode
        "OUT": self.outreach_mode,  # Enters outreach mode
        "U": lambda value: setattr(self, "UPPER_THRESHOLD", value),  # Set upper threshold
        "L": lambda value: setattr(self, "LOWER_THRESHOLD", value),  # Set lower threshold
        # Reset power to the entire satellite (!!!!)
        "RST": lambda: [i() for i in [
            lambda: self.eps.commands["All Off"],
            lambda: time.sleep(.5),
            lambda: self.eps.commands["Bus Reset"], (["Battery", "5V", "3.3V", "12V"])
        ]],
        # Transmit proof of life through Iridium to ground station
        "IRI": lambda: self.iridium.wave(self.eps.telemetry["VBCROUT"](),
                                         self.eps.solar_power(),
                                         self.eps.total_power()),
        # Transmit total power draw of connected components
        "PWR": lambda: self.iridium.commands["Transmit"]("TJ;" + str(self.eps.total_power(3)[0])),
        # Calculate and transmit Iridium signal strength variability
        "SSV": lambda: self.iridium.commands["Transmit"]("TJ;SSV:" + str(self.sfr.signal_strength_variability())),
        # Transmit current solar panel production
        "SOL": lambda: self.iridium.commands["Transmit"]("TJ;SOL:" + str(self.eps.solar_power())),
        "TBL": lambda: self.aprs.write("TJ;" + self.imu.getTumble())  # Test method, transmits tumble value
    }
    def __init__(self):
        pass

    def TST():