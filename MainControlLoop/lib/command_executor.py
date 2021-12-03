import time
import pandas as pd
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket
from MainControlLoop.lib.exceptions import RedundantCommandInputError, InvalidCommandInputError


class CommandExecutor:
    def __init__(self, sfr):
        self.sfr = sfr
        self.TJ_PREFIX = "TJ;"
        self.OUTREACH_PREFIX = "OUT;"

        self.primary_registry = {  # primary command registry for BOTH Iridium and APRS
            "MCH": self.MCH,
            "MSC": self.MSC,
            "MOU": self.MOU,
            "MRP": self.MRP,
            "MLK": self.MLK,
            "MDF": self.MDF,
            "DLK": self.DLK,
            "DDF": self.DDF,
            "GCR": self.GCR,
            "GVT": self.GVT,
            "GPL": self.GPL,
            "GCD": self.GCD,
            "GPW": self.GPW,
            "GOP": self.GOP,
            "GCS": self.GCS,
            "GSV": self.GSV,
            "GSG": self.GSG,
            "GTB": self.GTB,
            "GMT": self.GMT,
            "GST": self.GST,
            "GTS": self.GTS,
            "AAP": self.AAP,
            "APW": self.APW,
            "ASV": self.ASV,
            "ASG": self.ASG,
            "ATB": self.ATB,
            "ARS": self.ARS,
            "AMS": self.AMS,
            "SUV": self.SUV,
            "SLV": self.SLV,
            "USM": self.USM,
            "ULG": self.ULG,
            "ITM": self.ITM,
            "IPC": self.IPC
        }

        # IMPLEMENT FULLY
        self.secondary_registry = {  # Secondary command registry for APRS, in outreach mode
            # Reads and transmits battery voltage
            "BVT": self.BVT
        }
        self.arg_registry = {
            # Set of commands that require arguments, for either registry, for error checking reasons only
            "UVT",
            "LVT",
            "PWD",
            "SSD",
            "SOD",
            "TBD",
            "DLK",
            "DLF",
            "REP",
            "SZE"
        }

    def execute(self, packet: TransmissionPacket):
        for command_packet in self.sfr.vars.command_buffer:
            try:
                function = self.primary_registry[command_packet.command_string]
                function(command_packet)
            except Exception as e:
                self.transmit(command_packet, [repr(e)], True)
        self.sfr.vars.command_buffer.clear()

        for command in self.sfr.vars.outreach_buffer:
            try:
                function = self.secondary_registry[command.command_string]
                function(command)
            except Exception as e:
                self.transmit(command, [repr(e)], True)
        self.sfr.vars.outreach_buffer.clear()

    def transmit(self, packet: TransmissionPacket, data: list, error=False):
        """
        Transmit a message over radio that received command
        :param packet: (TransmissionPacket) packet of received transmission
        :param data: (list) of data, or a single length list of error message
        :param error: (bool) whether transmission is an error message
        """
        if error:
            packet.return_code = "ERR"
        else:
            packet.return_code = "0OK"
        packet.return_data = data
        self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit(packet)

    def MCH(self, packet: TransmissionPacket):
        """
        Switches current mode to charging mode
        """
        if str(self.sfr.mode_obj) == "Charging":
            raise RedundantCommandInputError("Already in Charging")
        self.sfr.vars.MODE = self.sfr.modes_list["Charging"]
        self.transmit(packet, [])

    def MSC(self, packet: TransmissionPacket):
        """
        Switches current mode to science mode
        """
        if str(self.sfr.mode_obj) == "Science":
            raise RedundantCommandInputError("Already in Science")
        self.sfr.vars.MODE = self.sfr.modes_list["Science"]
        self.transmit(packet, [])

    def MOU(self, packet: TransmissionPacket):
        """
        Switches current mode to outreach mode
        """
        if str(self.sfr.mode_obj) == "Outreach":
            raise RedundantCommandInputError("Already in Outreach")
        self.sfr.vars.MODE = self.sfr.modes_list["Outreach"]
        self.transmit(packet, [])

    def MRP(self, packet: TransmissionPacket):
        pass

    def MLK(self, packet: TransmissionPacket): # TODO: Implement
        """
        Enable Mode Lock
        """
        self.sfr.vars.MODE_LOCK = True

    def MDF(self, packet: TransmissionPacket):  # TODO: Implement
        """
        Disable mode lock
        """
        self.sfr.vars.MODE_LOCK = False

    def DLK(self, packet: TransmissionPacket): # TODO: Test
        """
        Enable Device Lock
        """
        dcode = packet.args[0]
        device_codes = [
            "Iridium",
            "APRS",
            "IMU",
            "Antenna Deployer"
        ]
        if dcode < 0 or dcode >= len(device_codes):
            raise InvalidCommandInputError("Invalid Device Code")
        if self.sfr.vars.LOCKED_DEVICES[device_codes[dcode]]:
            raise RuntimeError("Device already locked")
        else:
            self.sfr.vars.LOCKED_DEVICES[device_codes[dcode]] = True
            self.transmit(packet, [dcode])

    def DDF(self, packet: TransmissionPacket):  # TODO: Test
        """
        Disable Device Lock
        """

        dcode = packet.args[0]
        device_codes = [
            "Iridium",
            "APRS",
            "IMU",
            "Antenna Deployer"
        ]
        if dcode < 0 or dcode >= len(device_codes):
            raise InvalidCommandInputError("Invalid Device Code")
        if self.sfr.vars.LOCKED_DEVICES[device_codes[dcode]]:
            self.sfr.vars.LOCKED_DEVICES[device_codes[dcode]] = False
            self.transmit(packet, [dcode])
        else:
            raise RuntimeError("Device not locked")

    def GCR(self, packet: TransmissionPacket):
        pass

    def GVT(self, packet: TransmissionPacket):
        """
        Reads and Transmits Battery Voltage
        """
        self.transmit(packet, [self.sfr.eps.telemetry["VBCROUT"]()])

    def GPL(self, packet: TransmissionPacket):  # TODO: FIX
        """
        Transmit proof of life
        """
        self.transmit(packet, [self.sfr.eps.telemetry["VBCROUT"](),
                                sum(self.sfr.recent_gen()),
                                sum(self.sfr.recent_power())])

    def GCD(self, packet: TransmissionPacket):  # TODO: implement
        pass

    def GPW(self, packet: TransmissionPacket):
        """
        Transmit total power draw of satellite
        """
        self.transmit(packet, [sum(self.sfr.recent_power())])

    def GOP(self, packet: TransmissionPacket):
        """
        Transmits current orbital period
        """
        self.transmit(packet, [self.sfr.vars.ORBITAL_PERIOD], False)

    def GCS(self, packet: TransmissionPacket):
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
        orbital_period = self.sfr.analytics.calc_orbital_period()  # Calculate orbital period
        sunlight_ratio = sunlight_period / orbital_period  # How much of our orbit we spend in sunlight
        tumble = self.sfr.imu.getTumble()  # Current tumble
        result = [avg_pwr, avg_solar, orbital_period, sunlight_ratio,
                  self.sfr.vars.SIGNAL_STRENTH_VARIABILITY, self.sfr.vars.BATTERY_CAPACITY_INT, *tumble[0], *tumble[1]]
        self.transmit(packet, result)

    def GSV(self, packet: TransmissionPacket):
        """
        Transmit signal strength variability
        """
        self.transmit(packet, [self.sfr.vars.SIGNAL_STRENTH_VARIABILITY])

    def GSG(self, packet: TransmissionPacket):
        """
        Transmit solar generation
        """
        self.transmit(packet, [sum(self.sfr.recent_gen())])

    def GTB(self, packet: TransmissionPacket):
        """
        Transmit full IMU tumble
        """
        tum = self.sfr.imu.getTumble()
        self.transmit(packet, [*tum[0], *tum[1]])

    def GMT(self, packet: TransmissionPacket): # TODO: Make Not Temporary
        """
        Transmit magnitude IMU tumble
        """ # Temporary

        tum = self.sfr.imu.getTumble()
        mag = (tum[0][0]**2 + tum[0][1]**2 + tum[0][2]**2)**0.5
        self.transmit(packet, [mag])

    def GST(self, packet: TransmissionPacket):
        pass

    def GTS(self, packet: TransmissionPacket):
        pass

    def AAP(self, packet: TransmissionPacket):
        pass

    def APW(self, packet: TransmissionPacket): # TODO: Test
        """
        Transmits last n power draw datapoints
        """

        data = pd.read_csv(self.sfr.pwr_log_path) # Read logs

        returns = []

        for i in range(packet.args[0]):
            returns.append(data[len(data)-i])

        self.transmit(packet, returns)

    def ASV(self, packet: TransmissionPacket):
        pass

    def ASG(self, packet: TransmissionPacket): # TODO: Test
        """
        Transmits last n solar generation datapoints
        """

        data = pd.read_csv(self.sfr.solar_log_path) # Read logs

        returns = []

        for i in range(packet.args[0]):
            returns.append(data[len(data)-i])

        self.transmit(packet, returns)

    def ATB(self, packet: TransmissionPacket): # TODO: Implement
        """
        Transmits last n IMU tumble datapoints
        """
        pass

    def ARS(self, packet: TransmissionPacket): # TODO: Implement
        """
        Transmit the expected data return size of a given command
        """

        cmd = packet[0] # only packet value; encoded command identifier
        size = 0 # return variable

        # TODO: Parse encoded command value and return value

        self.transmit(packet, [cmd, size])

    def AMS(self, packet: TransmissionPacket):
        """
        Repeat result of command with given MSN
        """  # TODO: Fix this
        msn = packet[0]  # Read Packet Value
        df = pd.read_csv(self.COMMAND_LOG_PATH)
        try:
            self.transmit(packet, [df[df["msn"] == msn].to_csv().strip("\n")])
        except Exception as e:
            print(e)
            raise RuntimeError("Command does not exist in log!")

    def SUV(self, packet: TransmissionPacket):
        v = packet.args[0]  # get only argument from arg list
        self.sfr.vars.UPPER_THRESHOLD = float(v)
        self.transmit(packet, [v])

    def SLV(self, packet: TransmissionPacket):
        v = packet.args[0]
        self.sfr.vars.LOWER_THRESHOLD = float(v)
        self.transmit(packet, [v])

    def USM(self, packet: TransmissionPacket):
        """
        Transmits down summary statistics about our mission
        """

    def ULG(self, packet: TransmissionPacket):  # TODO: Implement
        """
        Transmit full rssi data logs
        """

    def ITM(self, packet: TransmissionPacket):
        """
        Transmits an OK code
        """
        self.transmit(packet, [])

    def IPC(self, packet: TransmissionPacket):  # TODO: Implement, how to power cycle satelitte without touching CPU power
        self.sfr.mode_obj.instruct["All Off"](exceptions=[])
        time.sleep(.5)
        self.sfr.eps.commands["Bus Reset"](["Battery", "5V", "3.3V", "12V"])



































