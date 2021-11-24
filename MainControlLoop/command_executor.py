import time
import pandas as pd
from datetime import datetime


class CommandExecutor:
    def __init__(self, sfr):
        self.sfr = sfr
        self.TJ_PREFIX = "TJ;"
        self.OUTREACH_PREFIX = "OUT;"

        self.primary_registry = { #primary command registry for BOTH Iridium and APRS
            "NOP": self.NOP,  # Test method, transmits OK code
            "BVT": self.BVT,  # Reads and transmits battery voltage
            "CHG": self.CHG,  # Enters charging mode
            "SCI": self.SCI,  # Enters science mode
            "OUT": self.OUT,  # Enters outreach mode
            "RST": self.RST,  # Reset power to the entire satellite (!!!!)
            "WVE": self.WVE,  # Transmit proof of life through Iridium to ground station
            "PWR": self.PWR,  # Transmit total power draw of connected components
            "SSV": self.SSV,  # Calculate and transmit Iridium signal strength variability
            "SVF": None,  # TODO: Implement  # Transmit full rssi data logs
            "SOL": self.SOL,  # Transmit current solar panel production
            "TBL": self.TBL,  # Transmits tumble value (Magnitude of gyroscope vector)
            "TBF": self.TBF,  # Transmits 3 axis gyroscope and magnetometer readings (full tumble readouts)
            "MLK": self.MLK,  # Mode lock
            "ORB": self.ORB,  # Orbital period
            "UVT": self.UVT,  # Set upper threshold
            "LVT": self.LVT,  # Set lower threshold
            "DLK": self.DLK,  # Device lock
            "REP": self.REP,  # Repeat result of a command with a given msn number (IRIDIUM ONLY)
            "GRB": self.GRB,  # Return a garbled message error if one is received
        }

        # IMPLEMENT FULLY
        self.aprs_secondary_registry = {  # Secondary command registry for APRS, in outreach mode
            # Reads and transmits battery voltage
            "BVT": lambda: self.sfr.devices["Iridium"].transmit(str(self.sfr.eps.telemetry["VBCROUT"]())),
        }
        self.arg_registry = { # Set of commands that require arguments, for either registry, for error checking reasons only
            "UVT",
            "LVT",
            "DLK"
        } 

    def execute(self):
        # IRIDIUM
        for iridium_command in self.sfr.iridium_command_buffer:
            command, arguments, message_number = iridium_command
            try:
                self.primary_registry[command](*arguments)
            except Exception as e:
                self.error("Iridium", message_number, repr(e))
        self.sfr.iridium_command_buffer.clear()

        # APRS
        for aprs_command in self.sfr.aprs_command_buffer:
            command, arguments, message_number = aprs_command
            try:
                self.primary_registry[command](*arguments)
            except Exception as e:
                self.error("APRS", command, repr(e))
        self.sfr.aprs_command_buffer.clear()

        # APRS OUTREACH
        for aprs_outreach in self.sfr.aprs_outreach_buffer:
            command, arguments, message_number = aprs_outreach
            try:
                self.aprs_secondary_registry[command](*arguments)
            except Exception as e:
                self.error("APRS", command, repr(e))
        self.sfr.aprs_outreach_buffer.clear()

    def error(self, radio, command, description):
        """
        Transmit an error message over radio that received command
        :param radio: (str) radio which received erraneous command, "Iridium" or "APRS"
        :param command: (str) command which failed in case of APRS, or MSN number of failed command in case of Iridium
        :param description: (str) detailed description of failure
        """
        if radio == "Iridium":
            self.sfr.devices["Iridium"].transmit("ERR", command, [description], discardmtbuf=True)
        elif radio == "APRS":
            self.sfr.devices["APRS"].transmit(f"ERR:{command}{description}")

    def transmit(self, message: str, command, datetime, data):
        """
        Transmits time + message string from primary radio to ground station

        :param message:
        """
        # TODO: how to handle if Iridium or APRS is off
        if self.sfr.PRIMARY_RADIO == "Iridium":
            self.sfr.devices["Iridium"].transmit(message, command, datetime, data)
        elif self.sfr.PRIMARY_RADIO == "APRS":
            self.sfr.devices["APRS"].transmit(message, command, datetime, )

    def NOP(self):
        """
        Transmits an OK code
        """

    def BVT(self):
        """
        Reads and Transmits Battery Voltage
        """
        self.transmit(str(self.sfr.eps.telemetry["VBCROUT"]()))

    def CHG(self):
        """
        Switches current mode to charging mode
        """
        if str(self.sfr.mode_obj) == "Charging":
            self.transmit("Already in Charging, No Switch")
        else:
            self.sfr.vars.MODE = self.sfr.modes_list["Charging"]
            self.transmit("Switched to Charging, Successful")

    def SCI(self):
        """
        Switches current mode to science mode
        """
        if str(self.sfr.mode_obj) == "Science":
            self.transmit("Already in Science, No Switch")
        else:
            self.sfr.vars.MODE = self.sfr.modes_list["Science"]
            self.transmit("Switched to Charging, Successful")

    def OUT(self):
        """
        Switches current mode to outreach mode
        """
        if str(self.sfr.mode_obj) == "Outreach":
            self.transmit("NO SWITCH")
        else:
            self.sfr.vars.MODE = self.sfr.modes_list["Outreach"]
            self.transmit("SWITCH OUTREACH")

    def UVT(self, v):  # TODO: Implement
        self.sfr.vars.UPPER_THRESHOLD = float(v)

    def LVT(self, v):  # TODO: Implement
        self.sfr.vars.LOWER_THRESHOLD = float(v)

    def RST(self):  #TODO: Implement, how to power cycle satelitte without touching CPU power
        self.sfr.mode_obj.instruct["All Off"](exceptions=[])
        self.sfr.wait(.5)
        self.sfr.eps.commands["Bus Reset"](["Battery", "5V", "3.3V", "12V"])

    def WVE(self):
        """
        Transmits proof of life via Iridium, along with critical component data
        using iridium.wave (not transmit function)
        """
        self.sfr.devices["Iridium"].wave(self.sfr.eps.telemetry["VBCROUT"](), self.sfr.eps.solar_power(),
                                    self.sfr.eps.total_power(4))

    def PWR(self):
        """
        Transmit total power draw of satellite
        """
        self.transmit(str(self.sfr.eps.total_power(3)[0]))

    def SSV(self):
        """
        Transmit signal strength variability
        """
        self.transmit(str(self.sfr.vars.SIGNAL_STRENTH_VARIABILITY))
    
    def SOL(self):
        """
        Transmit solar generation
        """

    def TBL(self):
        """
        Transmit magnitude IMU tumble
        """

    def TBF(self):
        """
        Transmit full IMU tumble
        """

    def MLK(self):
        """
        Enable Mode Lock
        """

    def DLK(self, a, b):
        """
        Enable Device Lock
        """
        device_codes = {
            "00": "Iridium",
            "01": "APRS",
            "02": "IMU",
            "03": "Antenna Deployer"
        }
        try:
            if self.sfr.vars.LOCKED_DEVICES[device_codes[a + b]]:
                self.sfr.vars.LOCKED_DEVICES[device_codes[a + b]] = False
                self.transmit(device_codes[a + b] + " UNLOCKED")
            else:
                self.sfr.vars.LOCKED_DEVICES[device_codes[a + b]] = True
                self.transmit(device_codes[a + b] + " LOCKED")
        except KeyError:
            self.error(self.sfr.vars.PRIMARY_RADIO, "D")

    def SUM(self):
        """
        Transmits down summary statistics about our mission
        """

    def STS(self):
        """
        Transmits down information about the satellite's current status
        """

    def ORB(self):
        """
        Transmits current orbital period
        """
        self.transmit(str(self.sfr.vars.ORBITAL_PERIOD))
    
    def REP(self, msn):
        """
        Repeat result of command with given MSN
        """
        df = pd.read_csv(self.COMMAND_LOG_PATH)
        try:
            self.transmit(df[df["msn"] == msn].to_csv().strip("\n"))
        except Exception as e:
            print(e)
            self.transmit("Command does not exist in log!")

    def GRB(self, **kwargs):
        """
        Transmit a garbled message error
        """
        