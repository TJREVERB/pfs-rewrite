from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.outreach import Outreach
from MainControlLoop.Mode.repeater import Repeater
import datetime


class CommandExecutor:
    # command_registry = {
    #     "TST": lambda: self.iridium.transmit("Hello"),  # Test method, transmits "Hello"
    #     # Reads and transmits battery voltage
    #     "BVT": lambda: self.iridium.transmit(str(self.eps.telemetry["VBCROUT"]())),
    #     "CHG": self.charging_mode(),  # Enters charging mode
    #     "SCI": self.science_mode(self.NUM_DATA_POINTS, self.NUM_SCIENCE_MODE_ORBITS),  # Enters science mode
    #     "OUT": self.outreach_mode,  # Enters outreach mode
    #     "U": lambda value: setattr(self, "UPPER_THRESHOLD", value),  # Set upper threshold
    #     "L": lambda value: setattr(self, "LOWER_THRESHOLD", value),  # Set lower threshold
    #     # Reset power to the entire satellite (!!!!)
    #     "RST": lambda: [i() for i in [
    #         lambda: self.eps.commands["All Off"],
    #         lambda: time.sleep(.5),
    #         lambda: self.eps.commands["Bus Reset"], (["Battery", "5V", "3.3V", "12V"])
    #     ]],
    #     # Transmit proof of life through Iridium to ground station
    #     "IRI": lambda: self.iridium.wave(self.eps.telemetry["VBCROUT"](),
    #                                      self.eps.solar_power(),
    #                                      self.eps.total_power()),
    #     # Transmit total power draw of connected components
    #     "PWR": lambda: self.iridium.transmit(str(self.eps.total_power(3)[0])),
    #     # Calculate and transmit Iridium signal strength variability
    #     "SSV": lambda: self.iridium.transmit("SSV:" + str(self.sfr.signal_strength_variability())),
    #     # Transmit current solar panel production
    #     "SOL": lambda: self.iridium.transmit("SOL:" + str(self.eps.solar_power())),
    #     "TBL": lambda: self.aprs.write(self.imu.getTumble())  # Test method, transmits tumble value
    # }

    def __init__(self):
        pass

    def transmit(self, current_mode, message: str):
        """
        Transmits time + message string from primary radio to ground station
        """
        current_mode.sfr.defaults["PRIMARY_RADIO"].transmit(message)

    def TST(self, current_mode: Mode):
        """
        Tries to transmit proof of life back to ground station.
        TODO: error checking (if iridium doesn't work etc)
        """
        self.transmit(current_mode, "Hello")

    def BVT(self, current_mode: Mode):
        """
        Reads and Transmits Battery Voltage
        """
        self.transmit(current_mode, str(current_mode.sfr.eps.telemetry["VBCROUT"]()))

    def CHG(self, current_mode: Mode):
        """
        Switches current mode to charging mode
        """
        if str(current_mode) == "Charging":
            self.transmit(current_mode, "Already in charging mode, no mode switch executed")
        else:
            current_mode.sfr.defaults["MODE"] = Charging(current_mode.sfr)
            self.transmit(current_mode.sfr.defaults["MODE"], "Switched to charging mode")

    def SCI(self, current_mode: Mode):
        """
        Switches current mode to science mode
        """
        if str(current_mode) == "Science":
            self.transmit(current_mode, "Already in science mode, no mode switch executed")
        else:
            current_mode.sfr.defaults["MODE"] = Science(current_mode.sfr)
            self.transmit(current_mode.sfr.defaults["MODE"], "Switched to science mode")

    def OUT(self, current_mode: Mode):
        """
        Switches current mode to outreach mode
        """
        if str(current_mode) == "Outreach":
            self.transmit(current_mode, "Already in outreach mode, no mode switch executed")
        else:
            current_mode.sfr.defaults["MODE"] = Outreach(current_mode.sfr)
            self.transmit(current_mode.sfr.defaults["MODE"], "Switched to outreach mode")

    def U(self):  #TODO: Implement
        pass

    def L(self):  #TODO: Implement
        pass

    def RST(self):  #TODO: Implement, how to power cycle satelitte without touching CPU power
        pass

    def IRI(self, current_mode: Mode):
        """
        Transmits proof of life via Iridium, along with critical component data
        using iridium.wave (not transmit function)
        """
        current_mode.sfr.iridium.wave(current_mode.eps.telemetry["VBCROUT"](), current_mode.eps.solar_power(),
                                      current_mode.eps.total_power(4))

