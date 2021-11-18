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
    #         lambda: self.eps.ALL_OFF,
    #         lambda: time.sleep(.5),
    #         lambda: self.eps.BUS_RESET, (["Battery", "5V", "3.3V", "12V"])
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

    def __init__(self, sfr):
        self.sfr = sfr
        self.aprs_buffer = []
        self.iridium_buffer = []

    def transmit(self, message: str):
        """
        Transmits time + message string from primary radio to ground station
        """
        self.sfr.PRIMARY_RADIO.transmit(message)

    def TST(self):
        """
        Tries to transmit proof of life back to ground station.
        TODO: error checking (if iridium doesn't work etc)
        """
        self.transmit("Hello")

    def BVT(self):
        """
        Reads and Transmits Battery Voltage
        """
        self.transmit(str(current_mode.sfr.eps.telemetry["VBCROUT"]()))

    def CHG(self):
        """
        Switches current mode to charging mode
        """
        if str(current_mode) == "Charging":
            self.transmit(current_mode, "Already in charging mode, no mode switch executed")
        else:
            current_mode.sfr.MODE = Charging(current_mode.sfr)
            self.transmit(current_mode.sfr.MODE, "Switched to charging mode")

    def SCI(self):
        """
        Switches current mode to science mode
        """
        if str(current_mode) == "Science":
            self.transmit(current_mode, "Already in science mode, no mode switch executed")
        else:
            current_mode.sfr.MODE = Science(current_mode.sfr)
            self.transmit(current_mode.sfr.MODE, "Switched to science mode")

    def OUT(self):
        """
        Switches current mode to outreach mode
        """
        if str(current_mode) == "Outreach":
            self.transmit(current_mode, "Already in outreach mode, no mode switch executed")
        else:
            current_mode.sfr.MODE = Outreach(current_mode.sfr)
            self.transmit(current_mode.sfr.MODE, "Switched to outreach mode")

    def U(self):  #TODO: Implement
        pass

    def L(self):  #TODO: Implement
        pass

    def RST(self):  #TODO: Implement, how to power cycle satelitte without touching CPU power
        pass

    def IRI(self):
        """
        Transmits proof of life via Iridium, along with critical component data
        using iridium.wave (not transmit function)
        """
        current_mode.sfr.iridium.wave(current_mode.eps.telemetry["VBCROUT"](), current_mode.eps.solar_power(),
                                      current_mode.eps.total_power(4))

    def execute(self):
        pass  # executes command buffers


    def exec_command(self, raw_command, registry) -> bool: #TODO: MOVE TJ; EXTRACTION TO APRS DRIVER; IRIDIUM SHOULD NOT USE THE PREFIX
        if raw_command == "":
            return True
        # Attempts to execute command
        try:
            # Extracts 3-letter code from raw message
            command = raw_command[raw_command.find("TJ;") + 3:raw_command.find("TJ;") + 6]
            # Executes command associated with code and logs result
            with open("log.txt", "a") as f:
                # Executes command
                if command[1:].isdigit():
                    result = registry[command[0]](int(command[1]) + float(command[2]) / 10)
                else:
                    result = registry[command]()
                # Timestamp + tab + code + tab + result of command execution + newline
                f.write(str(time.time()) + "\t" + command + "\t" + result + "\n")
            return True
        except Exception:
            return False

"""
Dev notes:
when manual overriding a mode, make sure to terminate previous mode first
make sure to lock device when manually turning it on or off
"""