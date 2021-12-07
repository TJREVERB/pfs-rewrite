import time, datetime
import pandas as pd
import os
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
            "AMS": self.AMS,
            "SUV": self.SUV,
            "SLV": self.SLV,
            "USM": self.USM,
            "ULG": self.ULG,
            "ITM": self.ITM,
            "IPC": self.IPC
        }

        # IMPLEMENT FULLY: Currently based off of Alan's guess of what we need
        self.secondary_registry = {  # Secondary command registry for APRS, in outreach mode
            # Reads and transmits battery voltage
            "GVT": self.GVT,
            "GPL": self.GPL,
            "GPW": self.GPW,
            "GSV": self.GSV,
            "GSG": self.GSG,
            "GTB": self.GTB,
            "GOP": self.GOP,
            "GCS": self.GCS,
            "USM": self.USM,
            "IPC": self.IPC
        }
        

    def execute(self):
        for command_packet in self.sfr.vars.command_buffer:
            try:
                function = self.primary_registry[command_packet.command_string]
                function(command_packet)
                t = datetime.datetime.utcnow()
                command_packet.timestamp = (t.day, t.hour, t.minute)
            except Exception as e:
                self.transmit(command_packet, [repr(e)], True)
        self.sfr.vars.command_buffer.clear()

        for command in self.sfr.vars.outreach_buffer:
            try:
                function = self.secondary_registry[command.command_string]
                function(command)
                t = datetime.datetime.utcnow()
                command_packet.timestamp = (t.day, t.hour, t.minute)
            except Exception as e:
                self.transmit(command, [repr(e)], True)
        self.sfr.vars.outreach_buffer.clear()
        self.sfr.LAST_COMMAND_RUN = time.time()

    def transmit(self, packet: TransmissionPacket, data: list, error=False):
        """
        Transmit a message over radio that received command
        :param packet: (TransmissionPacket) packet of received transmission
        :param data: (list) of data, or a single length list of error message
        :param error: (bool) whether transmission is an error message
        :return: (bool) transmission successful
        """
        if error:
            packet.return_code = "ERR"
        else:
            packet.return_code = "0OK"
        packet.return_data = data
        try:
            self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit(packet)
            return True
        except RuntimeError as e:
            print(e)
            self.sfr.vars.transmit_buffer.append(packet)
            return False

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
        """
        Switches current mode to Repeater mode
        """
        pass

    def MLK(self, packet: TransmissionPacket):
        """
        Enable Mode Lock
        """
        self.sfr.vars.MODE_LOCK = True
        self.transmit(packet, []) # OK code

    def MDF(self, packet: TransmissionPacket):
        """
        Disable mode lock
        """
        self.sfr.vars.MODE_LOCK = False
        self.transmit(packet, []) # OK code

    def DLK(self, packet: TransmissionPacket):
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

    def DDF(self, packet: TransmissionPacket):
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
        """
        Transmits time since last command run
        """
        data = time.time() - self.sfr.LAST_COMMAND_RUN
        self.transmit(packet, [data])

    def GVT(self, packet: TransmissionPacket):
        """
        Reads and Transmits Battery Voltage
        """
        self.transmit(packet, [self.sfr.eps.telemetry["VBCROUT"]()])

    def GPL(self, packet: TransmissionPacket):
        """
        Transmit proof of life
        """
        self.transmit(packet, [self.sfr.eps.telemetry["VBCROUT"](),
                                sum(self.sfr.recent_gen()),
                                sum(self.sfr.recent_power())])

    def GCD(self, packet: TransmissionPacket):
        """
        Transmits detailed critical data
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
        Transmits all sfr fields as str
        """
        self.transmit(packet, [str(i) for i in list(vars(self.sfr.vars).values())])

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

    def GMT(self, packet: TransmissionPacket):
        """
        Transmit magnitude IMU tumble
        """
        tum = self.sfr.imu.getTumble()
        mag = (tum[0][0]**2 + tum[0][1]**2 + tum[0][2]**2)**0.5
        self.transmit(packet, [mag])

    def GST(self, packet: TransmissionPacket):
        """
        Transmits RTC time currently
        """
        self.transmit(packet, [time.time()]) # Bad

    def GTS(self, packet: TransmissionPacket):
        """
        Transmits time since last mode switch
        """
        self.transmit(packet, [time.time() - self.sfr.LAST_MODE_SWITCH])

    def AAP(self, packet: TransmissionPacket):
        """
        Transmits average power draw over n data points
        """
        self.transmit(packet, [
            self.sfr.analytics.historical_consumption([1, 1, 1, 1, 1, 1, 1, 1, 1, 1], packet.args[0])])

    def APW(self, packet: TransmissionPacket):  # TODO: Test
        """
        Transmits last n power draw datapoints
        """
        df = pd.read_csv(self.sfr.pwr_log_path).tail(packet.args[0])  # Read logs
        self.transmit(packet, [j for j in [i for i in df.values.tolist()]])

    def ASV(self, packet: TransmissionPacket):
        """
        Transmits last n signal strength datapoints
        """
        df = pd.read_csv(self.sfr.iridium_data_path).tail(packet.args[0]) # Read logs
        self.transmit(packet, [j for j in [i for i in df.values.tolist()]])

    def ASG(self, packet: TransmissionPacket):  # TODO: Test
        """
        Transmits last n solar generation datapoints
        """
        df = pd.read_csv(self.sfr.solar_log_path).tail(packet.args[0]) # Read logs
        self.transmit(packet, [j for j in [i for i in df.values.tolist()]])

    def ATB(self, packet: TransmissionPacket):
        """
        Transmits last n IMU tumble datapoints
        """
        df = pd.read_csv(self.sfr.imu_log_path).tail(packet.args[0]) # Read logs
        self.transmit(packet, [j for j in [i for i in df.values.tolist()]])

    def AMS(self, packet: TransmissionPacket):
        """
        Repeat result of command with given MSN
        """
        msn = packet.args[0]  # Read Packet Value
        df = pd.read_csv(self.sfr.command_log_path)
        # If search for msn returns results
        if len(row := df[df["msn"] == msn]) != 0:
            # Transmit last element of log with given msn if duplicates exist
            self.transmit(packet, [float(i) for i in row["result"][-1].split(",")])
        else:
            raise RuntimeError("Command does not exist in log!")

    def SUV(self, packet: TransmissionPacket):
        """
        Set upper threshold for mode switch
        """
        v = packet.args[0]  # get only argument from arg list
        self.sfr.vars.UPPER_THRESHOLD = float(v)
        self.transmit(packet, [v])

    def SLV(self, packet: TransmissionPacket):
        """
        Set lower threshold for mode switch
        """
        v = packet.args[0]
        self.sfr.vars.LOWER_THRESHOLD = float(v)
        self.transmit(packet, [v])

    def USM(self, packet: TransmissionPacket):
        """
        Transmits down summary statistics about our mission
        Transmits:
        1. Time since mission start
        2. Time since last satellite startup
        3. Total power consumed over mission
        4. Total power generated over mission
        5. Total amount of data transmitted
        6. Orbital decay (seconds of period lost over mission duration)
        7. Total number of iridium commands received
        8. Total number of aprs commands received
        9. Total number of iridium signal strength measurements taken
        10. Total number of power consumption/generation measurements
        """
        self.transmit(packet, [
            time.time() - self.sfr.vars.START_TIME,
            time.time() - self.sfr.vars.LAST_STARTUP,
            self.sfr.analytics.total_power_consumed(),
            self.sfr.analytics.total_power_generated(),
            None,  # TODO: IMPLEMENT TOTAL DATA TRANSMITTED
            self.sfr.analytics.orbital_decay(),
            len((df := pd.read_csv(self.sfr.command_log))[df["radio"] == "Iridium"]),
            len((df := pd.read_csv(self.sfr.command_log))[df["radio"] == "APRS"]),
            len(pd.read_csv(self.sfr.iridium_data_path)),
            len(pd.read_csv(self.sfr.pwr_log_path)),
        ])

    def ULG(self, packet: TransmissionPacket):
        """
        Transmit full rssi data logs
        """
        with open(self.sfr.command_log_path, "r") as f:
            self.transmit(packet, [f.read()])

    def ITM(self, packet: TransmissionPacket):
        """
        Transmits an OK code
        """
        self.transmit(packet, [])

    def IPC(self, packet: TransmissionPacket):  # TODO: Implement, how to power cycle satelitte without touching CPU power
        """
        Power cycle satellite
        """
        self.sfr.mode_obj.instruct["All Off"](exceptions=[])
        time.sleep(.5)
        self.sfr.eps.commands["Bus Reset"](["Battery", "5V", "3.3V", "12V"])
        self.transmit(packet, [])
    
    def IRB(self, packet: TransmissionPacket):
        """
        Reboot pi
        """
        os.system("sudo reboot")
