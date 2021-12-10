import time, datetime
import pandas as pd
import os
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket
from MainControlLoop.lib.exceptions import *


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
            to_log = pd.DataFrame([
                {"timestamp": (t := datetime.datetime.utcnow()).timestamp()},
                {"radio": self.sfr.PRIMARY_RADIO},  # TODO: FIX
                {"command": command_packet.command_string},
                {"arg": ":".join(command_packet.args)},
                {"registry": "Primary"},
                {"msn": command_packet.msn}
            ])
            command_packet.timestamp = (t.day, t.hour, t.minute)
            try:
                to_log["result"] = self.primary_registry[command_packet.command_string](command_packet)
            except Exception as e:
                self.transmit(command_packet, [repr(e)], True)
                to_log["result"] = "ERR:" + type(e).__name__
            finally:
                to_log.to_csv(self.sfr.command_log_path, mode="a", header=False)
                self.sfr.LAST_COMMAND_RUN = time.time()
        self.sfr.vars.command_buffer.clear()

        for command_packet in self.sfr.vars.outreach_buffer:
            to_log = pd.DataFrame([
                {"timestamp": (t := datetime.datetime.utcnow()).timestamp()},
                {"radio": self.sfr.PRIMARY_RADIO},  # TODO: FIX
                {"command": command_packet.command_string},
                {"arg": ":".join(command_packet.args)},
                {"registry": "Secondary"},
                {"msn": command_packet.msn}
            ])
            command_packet.timestamp = (t.day, t.hour, t.minute)
            try:
                to_log["result"] = self.secondary_registry[command_packet.command_string](command_packet)
            except (InvalidCommandInputError, RedundantCommandInputError) as e:
                self.transmit(command_packet, [repr(e)], True)
                to_log["result"] = "ERR:" + type(e).__name__
            finally:
                to_log.to_csv(self.sfr.command_log_path, mode="a", header=False)
                self.sfr.LAST_COMMAND_RUN = time.time()
        self.sfr.vars.outreach_buffer.clear()

    def transmit(self, packet: TransmissionPacket, data: list, error=False):
        """
        Transmit a message over primary radio
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
        self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit(packet)
        self.sfr.vars.transmit_buffer.append(packet)


    def MCH(self, packet: TransmissionPacket) -> list:
        """
        Switches current mode to charging mode
        """
        if str(self.sfr.mode_obj) == "Charging":
            raise RedundantCommandInputError("Already in Charging")
        self.sfr.vars.MODE = self.sfr.modes_list["Charging"]
        self.transmit(packet, result := [])
        return result

    def MSC(self, packet: TransmissionPacket) -> list:
        """
        Switches current mode to science mode
        """
        if str(self.sfr.mode_obj) == "Science":
            raise RedundantCommandInputError("Already in Science")
        self.sfr.vars.MODE = self.sfr.modes_list["Science"]
        self.transmit(packet, result := [])
        return result

    def MOU(self, packet: TransmissionPacket) -> list:
        """
        Switches current mode to outreach mode
        """
        if str(self.sfr.mode_obj) == "Outreach":
            raise RedundantCommandInputError("Already in Outreach")
        self.sfr.vars.MODE = self.sfr.modes_list["Outreach"]
        self.transmit(packet, result := [])
        return result

    def MRP(self, packet: TransmissionPacket) -> list:
        """
        Switches current mode to Repeater mode
        """
        if str(self.sfr.mode_obj) == "Repeater":
            raise RedundantCommandInputError("Already in Repeater")
        self.sfr.vars.MODE = self.sfr.modes_list["Repeater"]
        self.transmit(packet, result := [])
        return result

    def MLK(self, packet: TransmissionPacket) -> list:
        """
        Enable Mode Lock
        """
        self.sfr.vars.MODE_LOCK = True
        self.transmit(packet, result := [])  # OK code
        return result

    def MDF(self, packet: TransmissionPacket) -> list:
        """
        Disable mode lock
        """
        self.sfr.vars.MODE_LOCK = False
        self.transmit(packet, result := [])  # OK code
        return result

    def DLK(self, packet: TransmissionPacket) -> list:
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
            raise RedundantCommandInputError("Device already locked")
        else:
            self.sfr.vars.LOCKED_DEVICES[device_codes[dcode]] = True
            self.transmit(packet, result := [dcode])
        return result

    def DDF(self, packet: TransmissionPacket) -> list:
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
            self.transmit(packet, result := [dcode])
        else:
            raise RedundantCommandInputError("Device not locked")
        return result

    def GCR(self, packet: TransmissionPacket) -> list:
        """
        Transmits time since last command run
        """
        self.transmit(packet, result := [time.time() - self.sfr.LAST_COMMAND_RUN])
        return result

    def GVT(self, packet: TransmissionPacket) -> list:
        """
        Reads and Transmits Battery Voltage
        """
        self.transmit(packet, result := [self.sfr.eps.telemetry["VBCROUT"]()])
        return result

    def GPL(self, packet: TransmissionPacket) -> list:
        """
        Transmit proof of life
        """
        
        self.transmit(packet, result := [self.sfr.eps.telemetry["VBCROUT"](),
                                sum(self.sfr.recent_gen()),
                                sum(self.sfr.recent_power())])
        return result

    def GCD(self, packet: TransmissionPacket) -> list:
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
        return result

    def GPW(self, packet: TransmissionPacket) -> list:
        """
        Transmit total power draw of satellite
        """
        self.transmit(packet, result := [sum(self.sfr.recent_power())])
        return result

    def GOP(self, packet: TransmissionPacket) -> list:
        """
        Transmits current orbital period
        """
        self.transmit(packet, result := [self.sfr.vars.ORBITAL_PERIOD], False)
        return result

    def GCS(self, packet: TransmissionPacket) -> list:
        """
        Transmits down information about the satellite's current status
        Transmits all sfr fields as str
        """
        self.transmit(packet, result := [self.sfr.vars.encode()])
        return result

    def GSV(self, packet: TransmissionPacket) -> list:
        """
        Transmit signal strength variability
        """
        self.transmit(packet, result := [self.sfr.vars.SIGNAL_STRENTH_VARIABILITY])
        return result

    def GSG(self, packet: TransmissionPacket) -> list:
        """
        Transmit solar generation
        """
        self.transmit(packet, result := [sum(self.sfr.recent_gen())])
        return result

    def GTB(self, packet: TransmissionPacket) -> list:
        """
        Transmit full IMU tumble
        """
        tum = self.sfr.imu.getTumble()
        self.transmit(packet, result := [*tum[0], *tum[1]])
        return result

    def GMT(self, packet: TransmissionPacket) -> list:
        """
        Transmit magnitude IMU tumble
        """
        tum = self.sfr.imu.getTumble()
        mag = (tum[0][0]**2 + tum[0][1]**2 + tum[0][2]**2)**0.5
        self.transmit(packet, result := [mag])
        return result

    def GTS(self, packet: TransmissionPacket) -> list:
        """
        Transmits time since last mode switch
        """
        self.transmit(packet, result := [time.time() - self.sfr.LAST_MODE_SWITCH])
        return result

    def AAP(self, packet: TransmissionPacket) -> list:
        """
        Transmits average power draw over n data points
        """
        self.transmit(packet, result := [
            self.sfr.analytics.historical_consumption([1 for _ in range(10)], packet.args[0])])
        return result

    def APW(self, packet: TransmissionPacket) -> list:  # TODO: Test
        """
        Transmits last n power draw datapoints
        """
        df = pd.read_csv(self.sfr.pwr_log_path).tail(packet.args[0])  # Read logs
        self.transmit(packet, result := [j for j in [i for i in df.values.tolist()]])
        return result

    def ASV(self, packet: TransmissionPacket) -> list:
        """
        Transmits last n signal strength datapoints
        """
        df = pd.read_csv(self.sfr.iridium_data_path).tail(packet.args[0])  # Read logs
        self.transmit(packet, result := [j for j in [i for i in df.values.tolist()]])
        return result

    def ASG(self, packet: TransmissionPacket) -> list:  # TODO: Test
        """
        Transmits last n solar generation datapoints
        """
        df = pd.read_csv(self.sfr.solar_log_path).tail(packet.args[0])  # Read logs
        self.transmit(packet, result := [j for j in [i for i in df.values.tolist()]])
        return result

    def ATB(self, packet: TransmissionPacket) -> list:
        """
        Transmits last n IMU tumble datapoints
        """
        df = pd.read_csv(self.sfr.imu_log_path).tail(packet.args[0])  # Read logs
        self.transmit(packet, result := [j for j in [i for i in df.values.tolist()]])
        return result
    
    def ARS(self, packet: TransmissionPacket) -> list:  #TODO: FIX
        """
        Transmits expected size of a given command
        """
        packet.args[0].timestamp = (t := (time.time()).day, t.hour, t.minute)
        packet.args[0].simulate = True  # Don't transmit results
        try:  # Attempt to run command, store result
            command_result = self.primary_registry[packet.args[0].command_string](packet.args[0])
        except Exception as e:  # Store error as a string
            command_result = [repr(e)]
        # Transmit number of bytes taken up by command result
        if self.sfr.vars.PRIMARY_RADIO == "Iridium":  # Factor in Iridium encoding procedures
            # Remove first 7 mandatory bytes from calculation
            self.transmit(packet, result := [len(self.sfr.devices["Iridium"].encode(
                packet.args[0].command_string, packet.args[0].return_code, packet.args[0].msn, 
                packet.args[0].timestamp, packet.args[0].return_data)[6:])])
        else:  # APRS doesn't encode
            # Only factor in size of return data
            self.transmit(packet, result := [len(':'.join(self.return_data))])
        return result

    def AMS(self, packet: TransmissionPacket) -> list:
        """
        Repeat result of command with given MSN
        """
        msn = packet.args[0]  # Read Packet Value
        df = pd.read_csv(self.sfr.command_log_path)
        # If search for msn returns results
        if len(row := df[df["msn"] == msn]) != 0:
            # Transmit last element of log with given msn if duplicates exist
            self.transmit(packet, result := [float(i) for i in row["result"][-1].split(":")])
        else:
            raise CommandExecutorRuntimeException("Command does not exist in log!")
        return result

    def SUV(self, packet: TransmissionPacket) -> list:
        """
        Set upper threshold for mode switch
        """
        v = packet.args[0]  # get only argument from arg list
        self.sfr.vars.UPPER_THRESHOLD = float(v)
        self.transmit(packet, result := [v])
        return result

    def SLV(self, packet: TransmissionPacket) -> list:
        """
        Set lower threshold for mode switch
        """
        v = packet.args[0]
        self.sfr.vars.LOWER_THRESHOLD = float(v)
        self.transmit(packet, result := [v])
        return result

    def USM(self, packet: TransmissionPacket) -> list:
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
        self.transmit(packet, result := [
            time.time() - self.sfr.vars.START_TIME,
            time.time() - self.sfr.vars.LAST_STARTUP,
            self.sfr.analytics.total_power_consumed(),
            self.sfr.analytics.total_power_generated(),
            self.sfr.analytics.total_data_transmitted(),
            self.sfr.analytics.orbital_decay(),
            len((df := pd.read_csv(self.sfr.command_log))[df["radio"] == "Iridium"]),
            len((df := pd.read_csv(self.sfr.command_log))[df["radio"] == "APRS"]),
            len(pd.read_csv(self.sfr.iridium_data_path)),
            len(pd.read_csv(self.sfr.pwr_log_path)),
        ])
        return result

    def ULG(self, packet: TransmissionPacket) -> list:
        """
        Transmit full rssi data logs
        """
        with open(self.sfr.command_log_path, "r") as f:
            self.transmit(packet, result := [f.read()])
        return result

    def ITM(self, packet: TransmissionPacket) -> list:
        """
        Transmits an OK code
        """
        self.transmit(packet, result := [])
        return result

    def IPC(self, packet: TransmissionPacket) -> list:  # TODO: Implement, how to power cycle satelitte without touching CPU power
        """
        Power cycle satellite
        """
        self.sfr.mode_obj.instruct["All Off"](exceptions=[])
        time.sleep(.5)
        self.sfr.eps.commands["Bus Reset"](["Battery", "5V", "3.3V", "12V"])
        self.transmit(packet, result := [])
        return result
    
    def IRB(self, packet: TransmissionPacket) -> None:
        """
        Reboot pi
        """
        self.transmit(packet, result := [])
        time.sleep(5)
        os.system("sudo reboot")

