import time
import pandas as pd
from transmission_packet import TransmissionPacket
from datetime import datetime


class CommandExecutor:
    def __init__(self, sfr):
        self.sfr = sfr
        self.TJ_PREFIX = "TJ;"
        self.OUTREACH_PREFIX = "OUT;"

        self.primary_registry = {  # primary command registry for BOTH Iridium and APRS
            "NOP": self.NOP,  # Test method, transmits OK code
            "BVT": self.BVT,  # Reads and transmits battery voltage
            "CHG": self.CHG,  # Enters charging mode
            "SCI": self.SCI,  # Enters science mode
            "OUT": self.OUT,  # Enters outreach mode
            "RST": self.RST,  # Reset power to the entire satellite (!!!!)
            "POL": self.POL,  # Transmit proof of life through primary radio to ground station
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
        self.secondary_registry = {  # Secondary command registry for APRS, in outreach mode
            # Reads and transmits battery voltage
            "BVT": lambda: self.sfr.devices["Iridium"].transmit(str(self.sfr.eps.telemetry["VBCROUT"]())),
        }
        self.arg_registry = {
            # Set of commands that require arguments, for either registry, for error checking reasons only
            "UVT",
            "LVT",
            "DLK"
        }

    def execute(self, packet: TransmissionPacket):
        for command in self.sfr.vars.command_buffer:
            function = self.primary_registry[command.command_string]
            function(command)
        self.sfr.vars.command_buffer.clear()

        for command in self.sfr.vars.outreach_buffer:
            function = self.secondary_registry[command.command_string]
            function(command)
        self.sfr.vars.outreach_buffer.clear()

    def error(self, packet: TransmissionPacket, error_message: str):
        """
        Transmit an error message over radio that received command
        :param radio: (str) radio which received erraneous command, "Iridium" or "APRS"
        :param command: (str) command which failed in case of APRS, or MSN number of failed command in case of Iridium
        :param description: (str) detailed description of failure
        """
        packet.error = True
        self.transmit(packet, error_message)

    def transmit(self, packet: TransmissionPacket, message: str):
        """
        Transmits time + message string from primary radio to ground station

        :param packet: Transmission object
        """
        packet.return_message = message
        self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit(packet)

    def NOP(self, packet: TransmissionPacket):
        """
        Transmits an OK code
        """

    def BVT(self, packet: TransmissionPacket):
        """
        Reads and Transmits Battery Voltage
        """
        self.transmit(packet, str(self.sfr.eps.telemetry["VBCROUT"]()))

    def CHG(self, packet: TransmissionPacket):
        """
        Switches current mode to charging mode
        """
        if str(self.sfr.mode_obj) == "Charging":
            self.transmit(packet, "Already in Charging, No Switch")
        else:
            self.sfr.vars.MODE = self.sfr.modes_list["Charging"]
            self.transmit(packet, "Switched to Charging, Successful")

    def SCI(self, packet: TransmissionPacket):
        """
        Switches current mode to science mode
        """
        if str(self.sfr.mode_obj) == "Science":
            self.transmit(packet, "Already in Science, No Switch")
        else:
            self.sfr.vars.MODE = self.sfr.modes_list["Science"]
            self.transmit(packet, "Switched to Charging, Successful")

    def OUT(self, packet: TransmissionPacket):
        """
        Switches current mode to outreach mode
        """
        if str(self.sfr.mode_obj) == "Outreach":
            self.transmit(packet, "Already in Outreach, No Switch")
        else:
            self.sfr.vars.MODE = self.sfr.modes_list["Outreach"]
            self.transmit(packet, "Switched to Outreach, Successful")

    def UVT(self, packet: TransmissionPacket):  # TODO: Implement
        v = packet.args[0]  # get only argument from arg list
        self.sfr.vars.UPPER_THRESHOLD = float(v)
        self.transmit(packet, f"Set Upper Voltage Threshold to {v}, Successful")

    def LVT(self, packet: TransmissionPacket):  # TODO: Implement
        v = packet.args[0]
        self.sfr.vars.LOWER_THRESHOLD = float(v)
        self.transmit(packet, f"Set Lower Voltage Threshold to {v}, Successful")

    def RST(self,
            packet: TransmissionPacket):  # TODO: Implement, how to power cycle satelitte without touching CPU power
        self.sfr.mode_obj.instruct["All Off"](exceptions=[])
        time.sleep(.5)
        self.sfr.eps.commands["Bus Reset"](["Battery", "5V", "3.3V", "12V"])

    def POL(self, packet: TransmissionPacket):  # TODO: FIX
        """
        Transmit proof of life
        """
        self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].wave(self.sfr.eps.telemetry["VBCROUT"](),
                                                           self.sfr.eps.solar_power(),
                                                           self.sfr.eps.total_power(4))

    def PWR(self, packet: TransmissionPacket):
        """
        Transmit total power draw of satellite
        """
        self.transmit(str(self.sfr.eps.total_power(3)[0]))

    def SSV(self, packet: TransmissionPacket):
        """
        Transmit signal strength variability
        """
        self.transmit(str(self.sfr.vars.SIGNAL_STRENTH_VARIABILITY))

    def SOL(self, packet: TransmissionPacket):
        """
        Transmit solar generation
        """

    def TBL(self, packet: TransmissionPacket):
        """
        Transmit magnitude IMU tumble
        """

    def TBF(self, packet: TransmissionPacket):
        """
        Transmit full IMU tumble
        """

    def MLK(self, packet: TransmissionPacket):
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

    def SUM(self, packet: TransmissionPacket):
        """
        Transmits down summary statistics about our mission
        """

    def STS(self, packet: TransmissionPacket):
        """
        Transmits down information about the satellite's current status
        Transmits:
        1. Average power draw over last 50 data points
        2. Average solar panel generation over last 50 datapoints while in sunlight
        3. Orbital period
        4. Amount of one orbit which we spend in sunlight
        5. Iridium signal strength variability (default -1 if science mode incomplete)
        6. Current battery charge
        7. Current tumble
        """
        pdms = ["0x01", "0x02", "0x03", "0x04", "0x05", "0x06", "0x07", "0x08", "0x09", "0x0A"]
        pwr_data = pd.read_csv(self.sfr.pwr_log_path, header=0).tail(50)
        avg_pwr = pwr_data[[i + "_pwr" for i in pdms]].sum(axis=1).mean()  # Average power draw
        panels = ["panel1", "panel2", "panel3", "panel4"]
        solar_data = pd.read_csv(self.sfr.solar_log_path, header=0).tail(51)
        orbits_data = pd.read_csv(self.sfr.orbit_log_path, header=0).tail(51)
        # Filter out all data points which weren't taken in sunlight
        in_sun = pd.DataFrame([solar_data[i] for i in range(solar_data.shape[0])
                               if orbits_data[solar_data["timestamp"][i] -
                                              orbits_data["timestamp"] > 0]["phase"][-1] == "sunlight"])
        avg_solar = in_sun[panels].sum(axis=1).mean()  # Average solar panel generation
        # Calculate sunlight period
        sunlight_period = pd.Series([orbits_data["timestamp"][i + 1] - orbits_data["timestamp"][i]
                                     for i in range(orbits_data.shape[0] - 1)
                                     if orbits_data["phase"][i] == "sunlight"]).mean()
        # Calculate orbital period
        orbital_period = sunlight_period + pd.Series([orbits_data["timestamp"][i + 1] - orbits_data["timestamp"][i]
                                                      for i in range(orbits_data.shape[0] - 1)
                                                      if orbits_data["phase"][i] == "eclipse"]).mean()
        sunlight_ratio = sunlight_period / orbital_period  # How much of our orbit we spend in sunlight
        tumble = self.sfr.imu.getTumble()  # Current tumble
        result = [avg_pwr, avg_solar, orbital_period, sunlight_ratio,
                  self.sfr.vars.SIGNAL_STRENTH_VARIABILITY, self.sfr.vars.BATTERY_CAPACITY_INT, tumble]

    def ORB(self, packet: TransmissionPacket):
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
