import datetime
import os
import time
import pandas as pd
from Drivers.transmission_packet import TransmissionPacket, FullPacket
from lib.exceptions import wrap_errors, LogicalError, CommandExecutionException, NoSignalException


class CommandExecutor:
    @wrap_errors(LogicalError)
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
            "DLN": self.DLN,
            "DLF": self.DLF,
            "DDF": self.DDF,
            "GCR": self.GCR,
            "GVT": self.GVT,
            "GPL": self.GPL,
            "GCD": self.GCD,
            "GPW": self.GPW,
            "GPR": self.GPR,
            "GOP": self.GOP,
            "GCS": self.GCS,
            "GID": self.GID,
            "GSM": self.GSM,
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
            "SSF": self.SSF,
            "USM": self.USM,
            "ULG": self.ULG,
            "ITM": self.ITM,
            "IPC": self.IPC,
            "IRB": self.IRB,
            "ICE": self.ICE,
            "IGO": self.IGO,
            "IAK": self.IAK
            #TODO: Add gamer mode commands once done with dev
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
            "ITM": self.ITM
        }

    @wrap_errors(LogicalError)
    def execute(self, packet: TransmissionPacket, registry: dict):
        """
        Execute a single command packet using the given command registry
        :param packet: packet for received command
        :param registry: command registry to use
        """
        print("Executing Command: " + packet.descriptor)
        to_log = {
            "ts0": (t := datetime.datetime.utcnow()).timestamp() // 100000 * 100000,  # first 5 digits
            "ts1": int(t.timestamp()) % 100000,  # last 5 digits
            "radio": self.sfr.vars.PRIMARY_RADIO,
            "command": packet.descriptor,
            "arg": ":".join([str(s) for s in packet.args]),
            "registry": "Primary",
            "msn": packet.msn,
            "result": ":".join([str(s) for s in packet.return_data]),
        }
        packet.set_time()
        if packet.descriptor == "GRB": # Handle garbled iridium messages
            self.transmit(packet, packet.args, string = True)
            return
        try:
            result = registry[packet.descriptor](packet)  # EXECUTES THE COMMAND
            to_log["result"] = ":".join([str(s) for s in result])
        except CommandExecutionException as e:
            self.transmit(packet, [repr(e)], True)
            to_log["result"] = "ERR:" + (type(e.exception).__name__ if e.exception is not None else repr(e.details))
        finally:
            self.sfr.logs["command"].write(to_log)
            self.sfr.vars.LAST_COMMAND_RUN = time.time()

    @wrap_errors(LogicalError)
    def execute_buffers(self):
        """
        Iterate through command and outreach buffers and execute all commands
        """
        # iterates through all commands in the buffer, then after executing all, empties buffer
        for command_packet in self.sfr.vars.command_buffer:
            self.execute(command_packet, self.primary_registry)
        self.sfr.vars.command_buffer = []

        for command_packet in self.sfr.vars.outreach_buffer:
            self.execute(command_packet, self.secondary_registry)
        self.sfr.vars.outreach_buffer = []

    @wrap_errors(LogicalError)
    def transmit(self, packet: TransmissionPacket, data: list, string=False):
        """
        Transmit a message over primary radio
        :param packet: (TransmissionPacket) packet of received transmission
        :param data: (list) of data, or a single length list of error message
        :param string: (bool) whether transmission is a string message
        :return: (bool) transmission successful
        """
        if string:
            packet.numerical = False
        if data is not None:
            packet.return_data = data
        if packet.outreach:
            for p in self.sfr.devices["APRS"].split_packet(packet):
                self.sfr.devices["APRS"].transmit(p)
            return True
        else:
            for p in self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].split_packet(packet):
                try:
                    self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit(p)
                    return True
                except NoSignalException as e:
                    print("No Iridium connectivity, appending to buffer...")
                    self.sfr.vars.transmit_buffer.append(p)
                    return False

    @wrap_errors(LogicalError)
    def transmit_from_buffer(self, packet: TransmissionPacket):
        """
        Transmit a message that has been read from buffer, do not append back to buffer
        Do not append data to packet
        Do not split packet
        :param packet: (TransmissionPacket) packet
        :return: (bool) transmission successful
        """
        try:
            self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit(packet)
            return True
        except NoSignalException as e:
            print("No Iridium connectivity, aborting transmit")
            return False

    @wrap_errors(LogicalError)
    def switch_mode(self, mode):
        """
        Switches current mode to given mode, raises exception if mode switch fails
        :param mode: mode to switch to
        """
        switch = self.sfr.switch_mode(mode)
        if not switch:
            raise CommandExecutionException("Necessary devices locked off!")
        return switch

    @wrap_errors(CommandExecutionException)
    def MCH(self, packet: TransmissionPacket) -> list:
        """
        Switches current mode to charging mode
        """
        if str(self.sfr.MODE) == "Charging":
            raise CommandExecutionException("Already in Charging")
        self.transmit(packet, result := [self.switch_mode(self.sfr.modes_list["Charging"](
            self.sfr, self.sfr.modes_list[list(self.sfr.modes_list.keys())[ int(packet.args[0]) ]]))])
        return result

    @wrap_errors(CommandExecutionException)
    def MSC(self, packet: TransmissionPacket) -> list:
        """
        Switches current mode to science mode
        """
        if str(self.sfr.MODE) == "Science":
            raise CommandExecutionException("Already in Science")
        self.transmit(packet, result := [self.switch_mode(self.sfr.modes_list["Science"](self.sfr))])
        return result

    @wrap_errors(CommandExecutionException)
    def MOU(self, packet: TransmissionPacket) -> list:
        """
        Switches current mode to outreach mode
        """
        if str(self.sfr.MODE) == "Outreach":
            raise CommandExecutionException("Already in Outreach")
        self.transmit(packet, result := [self.switch_mode(self.sfr.modes_list["Outreach"](self.sfr))])
        return result

    @wrap_errors(CommandExecutionException)
    def MRP(self, packet: TransmissionPacket) -> list:
        """
        Switches current mode to Repeater mode
        """
        if str(self.sfr.MODE) == "Repeater":
            raise CommandExecutionException("Already in Repeater")
        self.transmit(packet, result := [self.switch_mode(self.sfr.modes_list["Repeater"](self.sfr))])
        return result

    @wrap_errors(CommandExecutionException)
    def MLK(self, packet: TransmissionPacket) -> list:
        """
        Enable Mode Lock
        """
        self.sfr.vars.MODE_LOCK = True
        self.transmit(packet, result := [])  # OK code
        return result

    @wrap_errors(CommandExecutionException)
    def MDF(self, packet: TransmissionPacket) -> list:
        """
        Disable mode lock
        """
        self.sfr.vars.MODE_LOCK = False
        self.transmit(packet, result := [])  # OK code
        return result

    @wrap_errors(CommandExecutionException)
    def DLN(self, packet: TransmissionPacket) -> list:
        """
        Lock a device on
        """
        dcode = int(packet.args[0])
        device_codes = [
            "Iridium",
            "APRS",
            "IMU",
            "Antenna Deployer"
        ]
        if dcode < 0 or dcode >= len(device_codes):
            raise CommandExecutionException("Invalid Device Code")
        device_name = device_codes[dcode]
        self.sfr.lock_device_on(component=device_name, force=True)

        self.transmit(packet, result := [dcode])
        return result

    @wrap_errors(CommandExecutionException)
    def DLF(self, packet: TransmissionPacket) -> list:
        """
        Lock a device off
        """
        dcode = int(packet.args[0])
        device_codes = [
            "Iridium",
            "APRS",
            "IMU",
            "Antenna Deployer"
        ]
        if dcode < 0 or dcode >= len(device_codes):
            raise CommandExecutionException("Invalid Device Code")
        device_name = device_codes[dcode]
        self.sfr.lock_device_off(component=device_name, force=True)

        self.transmit(packet, result := [dcode])
        return result

    @wrap_errors(CommandExecutionException)
    def DDF(self, packet: TransmissionPacket) -> list:
        """
        Disable Device Lock
        """
        dcode = int(packet.args[0])
        device_codes = [
            "Iridium",
            "APRS",
            "IMU",
            "Antenna Deployer"
        ]
        if dcode < 0 or dcode >= len(device_codes):
            raise CommandExecutionException("Invalid Device Code")
        device_name = device_codes[dcode]
        success = self.sfr.unlock_device(device_name)  # returns True if it was previously locked (otherwise False)
        if success is False:
            raise CommandExecutionException("Device not locked")

        self.transmit(packet, result := [dcode, success])
        return result

    @wrap_errors(CommandExecutionException)
    def GCR(self, packet: TransmissionPacket) -> list:
        """
        Transmits time since last command run
        """
        dif = time.time() - self.sfr.vars.LAST_COMMAND_RUN
        self.transmit(packet, result := [int(dif / 100000) * 100000, int(dif % 100000)])
        return result

    @wrap_errors(CommandExecutionException)
    def GVT(self, packet: TransmissionPacket) -> list:
        """
        Reads and Transmits Battery Voltage
        """
        self.transmit(packet, result := [self.sfr.battery.telemetry["VBAT"]()])
        return result

    @wrap_errors(CommandExecutionException)
    def GPL(self, packet: TransmissionPacket) -> list:
        """
        Transmit proof of life
        """
        self.transmit(packet, result := [self.sfr.battery.telemetry["VBAT"](),
                                         sum(self.sfr.recent_gen()),
                                         sum(self.sfr.recent_power())])
        return result

    @wrap_errors(CommandExecutionException)
    def GPR(self, packet: TransmissionPacket):
        self.transmit(packet, result := [self.sfr.COMPONENTS.index(self.sfr.vars.PRIMARY_RADIO)])
        return result

    @wrap_errors(CommandExecutionException)
    def GCD(self, packet: TransmissionPacket) -> list:
        """
        Transmits detailed critical data
        Transmits:
        1. Average power draw over last 50 data points
        2. Average solar panel generation over last 50 datapoints while in sunlight
        3. Orbital period
        4. Amount of one orbit which we spend in sunlight
        5. Iridium signal strength mean (default -1 if science mode incomplete)
        6. Iridium signal strength variability (default -1 if science mode incomplete)
        7. Current battery charge
        8. Current tumble
        """
        self.transmit(packet, result := [
            self.sfr.analytics.historical_consumption(50).mean(),  # Average power consumption
            self.sfr.analytics.historical_generation(50).mean(),  # Average solar panel generation
            self.sfr.vars.ORBITAL_PERIOD,
            self.sfr.analytics.sunlight_ratio(50),  # Sunlight ratio over last 50 orbits
            self.sfr.vars.SIGNAL_STRENGTH_MEAN,
            self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY,
            self.sfr.vars.BATTERY_CAPACITY_INT,
            *(tumble := self.sfr.devices["IMU"].get_tumble())[0],
            *tumble[1]
        ])
        return result

    @wrap_errors(CommandExecutionException)
    def GPW(self, packet: TransmissionPacket) -> list:
        """
        Transmit total power draw of satellite
        """
        self.transmit(packet, result := [sum(self.sfr.recent_power())])
        return result

    @wrap_errors(CommandExecutionException)
    def GOP(self, packet: TransmissionPacket) -> list:
        """
        Transmits current orbital period
        """
        self.transmit(packet, result := [self.sfr.vars.ORBITAL_PERIOD], False)
        return result

    @wrap_errors(CommandExecutionException)
    def GCS(self, packet: TransmissionPacket) -> list:
        """
        Transmits down information about the satellite's current status
        Transmits all sfr fields as str
        """
        self.transmit(packet, result := [self.sfr.vars.encode()])
        return result

    @wrap_errors(CommandExecutionException)
    def GID(self, packet: TransmissionPacket) -> list:
        """
        Transmit signal strength mean and variability
        """
        print("Attempting to transmit science results")
        self.transmit(packet, result := [self.sfr.vars.SIGNAL_STRENGTH_MEAN,
                                         self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY])
        return result

    @wrap_errors(CommandExecutionException)
    def GSM(self, packet: TransmissionPacket) -> list:
        """
        Transmit signal strength mean
        """
        self.transmit(packet, result := [self.sfr.vars.SIGNAL_STRENGTH_MEAN])
        return result

    @wrap_errors(CommandExecutionException)
    def GSV(self, packet: TransmissionPacket) -> list:
        """
        Transmit signal strength variability
        """
        self.transmit(packet, result := [self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY])
        return result

    @wrap_errors(CommandExecutionException)
    def GSG(self, packet: TransmissionPacket) -> list:
        """
        Transmit solar generation
        """
        self.transmit(packet, result := [sum(self.sfr.recent_gen())])
        return result

    @wrap_errors(CommandExecutionException)
    def GTB(self, packet: TransmissionPacket) -> list:
        """
        Transmit full IMU tumble
        """
        if self.sfr.devices["IMU"] is None:
            tum = ((0, 0, 0), (0, 0, 0))
        tum = self.sfr.devices["IMU"].get_tumble()
        self.transmit(packet, result := [*tum[0], *tum[1]])
        return result

    @wrap_errors(CommandExecutionException)
    def GMT(self, packet: TransmissionPacket) -> list:
        """
        Transmit magnitude IMU tumble
        """
        tum = self.sfr.devices["IMU"].get_tumble()
        mag = (tum[0][0] ** 2 + tum[0][1] ** 2 + tum[0][2] ** 2) ** 0.5
        self.transmit(packet, result := [mag])
        return result

    @wrap_errors(CommandExecutionException)
    def GTS(self, packet: TransmissionPacket) -> list:
        """
        Transmits time since last mode switch
        """
        dif = time.time() - self.sfr.LAST_MODE_SWITCH
        self.transmit(packet, result := [int(dif / 100000) * 100000, int(dif % 100000)])
        return result

    @wrap_errors(CommandExecutionException)
    def AAP(self, packet: TransmissionPacket) -> list:
        """
        Transmits average power draw over n data points
        """
        ls = self.sfr.analytics.historical_consumption(int(packet.args[0]))
        self.transmit(packet, result := [ls.sum()/ls.size()])
        return result

    @wrap_errors(CommandExecutionException)
    def APW(self, packet: TransmissionPacket) -> list:
        """
        Transmits last n power draw datapoints
        """
        df = pd.read_csv(self.sfr.pwr_log_path).tail(int(packet.args[0]))  # Read logs
        self.transmit(packet, result := df.to_numpy().flatten().tolist())
        return result

    @wrap_errors(CommandExecutionException)
    def ASV(self, packet: TransmissionPacket) -> list:
        """
        Transmits last n signal strength datapoints
        """
        df = pd.read_csv(self.sfr.iridium_data_path).tail(int(packet.args[0]))  # Read logs
        self.transmit(packet, result := df.to_numpy().flatten().tolist())
        return result

    @wrap_errors(CommandExecutionException)
    def ASG(self, packet: TransmissionPacket) -> list:
        """
        Transmits last n solar generation datapoints
        """
        df = pd.read_csv(self.sfr.solar_log_path).tail(int(packet.args[0]))  # Read logs
        self.transmit(packet, result := df.to_numpy().flatten().tolist())
        return result

    @wrap_errors(CommandExecutionException)
    def ATB(self, packet: TransmissionPacket) -> list:
        """
        Transmits last n IMU tumble datapoints
        """
        df = pd.read_csv(self.sfr.imu_log_path).tail(int(packet.args[0]))  # Read logs
        self.transmit(packet, result := df.to_numpy().flatten().tolist())
        return result

    @wrap_errors(CommandExecutionException)
    def ARS(self, packet: TransmissionPacket) -> list:
        """
        Transmits expected size of a given command
        """
        sim_packet = FullPacket(packet.args[0], packet.args[1:], 0)
        sim_packet.set_time()
        sim_packet.simulate = True  # Don't transmit results
        try:  # Attempt to run command, store result
            self.primary_registry[sim_packet.descriptor](sim_packet)
        except Exception as e:  # Store error as a string
            result = [repr(e)]
            self.transmit(packet, result, string=True)
        else:
            # Transmit number of bytes taken up by command result
            if self.sfr.vars.PRIMARY_RADIO == "Iridium":  # Factor in Iridium encoding procedures
                # Remove first 7 mandatory bytes from calculation
                self.transmit(packet, result := [len(self.sfr.devices["Iridium"].encode(sim_packet))])
            else:  # APRS doesn't encode
                # Only factor in size of return data
                self.transmit(packet, result := [len(str(sim_packet.return_data))])
        return result

    @wrap_errors(CommandExecutionException)
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
            raise CommandExecutionException("Command does not exist in log!")
        return result

    @wrap_errors(CommandExecutionException)
    def SUV(self, packet: TransmissionPacket) -> list:
        """
        Set upper threshold for mode switch
        """
        v = packet.args[0]  # get only argument from arg list
        self.sfr.vars.UPPER_THRESHOLD = float(v)
        self.transmit(packet, result := [v])
        return result

    @wrap_errors(CommandExecutionException)
    def SLV(self, packet: TransmissionPacket) -> list:
        """
        Set lower threshold for mode switch
        """
        v = packet.args[0]
        self.sfr.vars.LOWER_THRESHOLD = float(v)
        self.transmit(packet, result := [v])
        return result

    @wrap_errors(CommandExecutionException)
    def SSF(self, packet: TransmissionPacket) -> list:
        """
        Enables or disables safe mode
        """
        self.sfr.vars.ENABLE_SAFE_MODE = bool(packet.args[0])
        self.transmit(packet, result := [])
        return result

    @wrap_errors(CommandExecutionException)
    def SFA(self, packet: TransmissionPacket) -> list:
        """
        Adds component to failed components list
        """
        device_codes = [
            "Iridium",
            "APRS",
            "IMU",
            "Antenna Deployer"
        ]
        if 0 > packet.args[0] < len(device_codes):
            raise CommandExecutionException("Invalid device code!")
        if device_codes[packet.args[0]] in self.sfr.vars.FAILURES:
            raise CommandExecutionException("Component already marked as failed!")
        self.sfr.vars.FAILURES.append(device_codes[packet.args[0]])
        self.transmit(packet, result := [sum([1 << i for i in range(len(device_codes))
            if device_codes[i] in self.sfr.vars.FAILURES])])
        return result

    @wrap_errors(CommandExecutionException)
    def SFR(self, packet: TransmissionPacket) -> list:
        """
        Removes component to failed components list
        """
        device_codes = [
            "Iridium",
            "APRS",
            "IMU",
            "Antenna Deployer"
        ]
        if 0 > packet.args[0] < len(device_codes):
            raise CommandExecutionException("Invalid device code!")
        if device_codes[packet.args[0]] not in self.sfr.vars.FAILURES:
            raise CommandExecutionException("Component not marked as failed!")
        self.sfr.vars.FAILURES.remove(device_codes[packet.args[0]])
        self.transmit(packet, result := [sum([1 << i for i in range(len(device_codes))
            if device_codes[i] in self.sfr.vars.FAILURES])])
        return result

    @wrap_errors(CommandExecutionException)
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
        startdif = time.time() - self.sfr.vars.START_TIME
        laststartdif = time.time() - self.sfr.vars.LAST_STARTUP
        self.transmit(packet, result := [
            int(startdif / 100000) * 100000,
            int(startdif % 100000),
            int(laststartdif / 100000) * 100000,
            int(laststartdif % 100000),
            self.sfr.analytics.total_energy_consumed(),
            self.sfr.analytics.total_energy_generated(),
            self.sfr.analytics.total_data_transmitted(),
            self.sfr.analytics.orbital_decay(),
            len((df := pd.read_csv(self.sfr.command_log))[df["radio"] == "Iridium"]),
            len((df := pd.read_csv(self.sfr.command_log))[df["radio"] == "APRS"]),
            len(pd.read_csv(self.sfr.iridium_data_path)),
            len(pd.read_csv(self.sfr.pwr_log_path)),
        ])
        return result

    @wrap_errors(CommandExecutionException)
    def ULG(self, packet: TransmissionPacket) -> list:
        """
        Transmit full rssi data logs
        """
        with open(self.sfr.command_log_path, "r") as f:
            self.transmit(packet, result := [f.read()])
        return result

    @wrap_errors(CommandExecutionException)
    def ITM(self, packet: TransmissionPacket) -> list:
        """
        Transmits an OK code
        """
        self.transmit(packet, result := [])
        return result

    @wrap_errors(CommandExecutionException)
    def IPC(self,
            packet: TransmissionPacket) -> list:
        """
        Power cycle satellite
        """
        self.transmit(packet, result := [])
        self.sfr.all_off(override_default_exceptions=True)
        time.sleep(.5)
        if not packet.simulate:
            exit(0)  # Exit script, eps will reset after 4 minutes without ping
        return result

    @wrap_errors(CommandExecutionException)
    def IRB(self, packet: TransmissionPacket) -> None:
        """
        Reboot pi
        """
        self.transmit(packet, [])
        os.system("sudo reboot")

    @wrap_errors(CommandExecutionException)
    def ICE(self, packet: TransmissionPacket):
        """Runs exec on string"""
        command = packet.args[0]
        exec(f"{command}")
        self.transmit(packet, result := [])
        return result

    @wrap_errors(CommandExecutionException)
    def IGO(self, packet: TransmissionPacket):
        """Exits remote code execution and attempts to restart MCL"""
        self.sfr.vars.ENABLE_SAFE_MODE = False
        self.transmit(packet, result := [])
        return result

    @wrap_errors(CommandExecutionException)
    def IAK(self, packet: TransmissionPacket):
        """
        Acknowledges attempt to establish contact
        """
        self.sfr.vars.CONTACT_ESTABLISHED = True
        self.transmit(packet, result := [])
        return result

    def ZMV(self, packet: TransmissionPacket):  # PROTO , not put in registry
        #TODO: packet can only have a single string arg, so you gotta figure out a delimiter for these and only use args[0]
        game_type, game_string, game_id = packet.args[0], packet.args[1], packet.args[2] 
        if str(self.sfr.MODE) != "Gamer":
            raise CommandExecutionException("Cannot use gamer mode function if not in gamer mode")
        self.sfr.MODE.game_queue.append(f"{game_type};{game_string};{game_id}")
        self.transmit(packet, result := [])
        return result

    def MGA(self, packet: TransmissionPacket):  # PROTO, not put in registry
        if str(self.sfr.MODE) == "Gamer":
            raise CommandExecutionException("Already in gamer mode")
        self.sfr.MODE.terminate_mode()
        self.sfr.MODE = self.sfr.modes_list["Gamer"](self.sfr)
        self.sfr.MODE.start()
        self.transmit(packet, result := [])
        return result
