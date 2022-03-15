import os
import time
from Drivers.transmission_packet import TransmissionPacket, FullPacket
from Drivers.aprs import APRS
from Drivers.iridium import Iridium
from lib.exceptions import wrap_errors, LogicalError, CommandExecutionException, NoSignalException, IridiumError
from MainControlLoop.Mode.outreach.jokes.jokes_game import JokesGame


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
            "MLK": self.MLK,
            "MDF": self.MDF,
            "DLN": self.DLN,
            "DLF": self.DLF,
            "DDF": self.DDF,
            "GCM": self.GCM,
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
            "ARS": self.ARS,
            "AMS": self.AMS,
            "SUV": self.SUV,
            "SLV": self.SLV,
            "SDT": self.SDT,
            "SSF": self.SSF,
            "SFA": self.SFA,
            "SFR": self.SFR,
            "USM": self.USM,
            "ITM": self.ITM,
            "IHB": self.IHB,
            "IPC": self.IPC,
            "IRB": self.IRB,
            "ICT": self.ICT,
            "ICE": self.ICE,
            "IAK": self.IAK,
            "ZMV": self.ZMV
        }

        # TODO: IMPLEMENT FULLY: Currently based off of Alan's guess of what we need
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
        print("Executing Command: " + packet.descriptor, file = open("pfs-output.txt", "a"))
        to_log = {
            "ts0": (t := time.time()) // 100000 * 100000,  # first 5 digits
            "ts1": int(t) % 100000,  # last 5 digits
            "radio": self.sfr.vars.PRIMARY_RADIO,
            "command": packet.descriptor,
            "arg": ":".join([str(s) for s in packet.args]),
            "registry": "Primary",
            "msn": packet.msn,
            "result": ":".join([str(s) for s in packet.return_data]),
        }
        packet.set_time()
        if packet.descriptor == "GRB":  # Handle garbled iridium messages
            self.transmit(packet, packet.args, string=True)
            return
        try:
            result = registry[packet.descriptor](packet)  # EXECUTES THE COMMAND
            to_log["result"] = ":".join([str(s) for s in result])
        except CommandExecutionException as e:
            self.transmit(packet, [repr(e)], string=True)
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
    def transmit(self, packet: TransmissionPacket, data: list = None,
                 string: bool = False, add_to_queue: bool = True):
        """
        Transmit a message over primary radio
        :param packet: (TransmissionPacket) packet of received transmission
        :param data: (list) of data, or a single length list of error message
        :param string: (bool) whether transmission is a string message
        :param add_to_queue: (bool) whether to append message to queue
        :return: (bool) transmission successful
        """
        print(packet, file=open("pfs-output.txt", "a"))
        if string:
            packet.numerical = False
        if data is not None:
            packet.return_data = data
        # If primary radio is off, append to queue
        if self.sfr.devices[self.sfr.vars.PRIMARY_RADIO] is None and add_to_queue:
            self.sfr.vars.transmit_buffer += Iridium.split_packet(packet)  # Split packet and extend
            return False
        # Split the packet and transmit components
        packets = self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].split_packet(packet)
        while len(packets) > 0:
            try:
                self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit(packets[0])  # Attempt to transmit first element
            except NoSignalException:  # If there's no connectivity, append remaining packets to buffer
                print("No Iridium connectivity, appending to buffer...", file = open("pfs-output.txt", "a"))
                if add_to_queue:  # Only append if we're allowed to do so
                    self.sfr.vars.transmit_buffer += packets
                return False
            except Exception:  # If we encounter another problem
                # we want to add the packet to the transmission buffer before raising to handle in mission_control
                if add_to_queue:
                    self.sfr.vars.transmit_buffer += packets
                raise
            packets.pop(0)  # Remove first element in queue if no problems were encountered
        return True

    @wrap_errors(LogicalError)
    def transmit_queue(self):
        """
        Attempt to transmit entire transmission queue
        """
        print("Attempting to transmit queue", file = open("pfs-output.txt", "a"))
        while len(self.sfr.vars.transmit_buffer) > 0:  # attempt to transmit buffer
            if not self.transmit_from_buffer(self.sfr.vars.transmit_buffer[0]):  # Attempt to transmit
                print("Signal strength lost!", file = open("pfs-output.txt", "a"))
                # note: function will still return true if we lose signal midway, messages will be transmitted next
                # execute cycle
                break  # If transmission has failed, exit loop
            self.sfr.vars.transmit_buffer.pop(0)  # Remove this packet from queue
            print(f"Transmitted {p}", file = open("pfs-output.txt", "a"))

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
        except NoSignalException:
            print("No Iridium connectivity, aborting transmit", file = open("pfs-output.txt", "a"))
            return False

    @wrap_errors(LogicalError)
    def switch_mode(self, mode):
        """
        Switches current mode to given mode, raises exception if mode switch fails
        :param mode: mode to switch to
        """
        if not self.sfr.switch_mode(mode):
            raise CommandExecutionException("Necessary devices locked off!")
        return True

    @wrap_errors(CommandExecutionException)
    def MCH(self, packet: TransmissionPacket) -> list:
        """
        Switches current mode to charging mode
        """
        if str(self.sfr.MODE) == "Charging":
            raise CommandExecutionException("Already in Charging")
        self.transmit(packet, result := [self.switch_mode(self.sfr.modes_list["Charging"](
            self.sfr, self.sfr.modes_list[list(self.sfr.modes_list.keys())[int(packet.args[0])]]))])
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
    def MLK(self, packet: TransmissionPacket) -> list:
        """
        Enable Mode Lock
        """
        self.sfr.vars.MODE_LOCK = True
        self.transmit(packet, result := [])
        return result

    @wrap_errors(CommandExecutionException)
    def MDF(self, packet: TransmissionPacket) -> list:
        """
        Disable mode lock
        """
        self.sfr.vars.MODE_LOCK = False
        self.transmit(packet, result := [])
        return result

    @wrap_errors(CommandExecutionException)
    def DLN(self, packet: TransmissionPacket) -> list:
        """
        Lock a device on
        """
        if (dcode := int(packet.args[0])) < 0 or dcode > 3:  # Any components after index 3 should not be locked off
            raise CommandExecutionException("Invalid Device Code")
        if not self.sfr.lock_device_on(component=self.sfr.COMPONENTS[dcode], force=True):
            raise CommandExecutionException("Device lock failed!")
        self.transmit(packet, result := [dcode])
        return result

    @wrap_errors(CommandExecutionException)
    def DLF(self, packet: TransmissionPacket) -> list:
        """
        Lock a device off
        """
        if (dcode := int(packet.args[0])) < 0 or dcode > 3:
            raise CommandExecutionException("Invalid Device Code")
        if not self.sfr.lock_device_off(component=self.sfr.COMPONENTS[dcode], force=True):
            raise CommandExecutionException("Device Lock Failed!")
        self.transmit(packet, result := [dcode])
        return result

    @wrap_errors(CommandExecutionException)
    def DDF(self, packet: TransmissionPacket) -> list:
        """
        Disable Device Lock
        """
        if (dcode := int(packet.args[0])) < 0 or dcode > 3:
            raise CommandExecutionException("Invalid Device Code")
        # returns True if it was previously locked (otherwise False)
        if not self.sfr.unlock_device(self.sfr.COMPONENTS[dcode]):
            raise CommandExecutionException("Device not locked")
        self.transmit(packet, result := [dcode])
        return result

    @wrap_errors(CommandExecutionException)
    def GCM(self, packet: TransmissionPacket) -> list:
        """
        Transmits current mode as string
        """
        self.transmit(packet, result := [str(self.sfr.MODE)], string=True)
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
    def GPL(self, packet: TransmissionPacket, force_queue=False) -> list:
        """
        Transmit proof of life (appends only once to queue unless force_queue is true, then always appends)
        Max one proof of life ping in transmit buffer unless force_queue is used
        :param packet: packet to transmit
        :type packet: TransmissionPacket
        :param force_queue: whether to force this packet into queue
        :type force_queue: bool
        """
        packet.descriptor = "GPL"
        self.transmit(packet, result := [self.sfr.battery.telemetry["VBAT"](),
                                         sum(self.sfr.recent_gen()),
                                         sum(self.sfr.recent_power()),
                                         self.sfr.devices["Iridium"].check_signal_passive()
                                         if self.sfr.devices["Iridium"] is not None else 0],
                      # Append to queue either if force_queue is true or if no other GPL ping has been added to queue
                      add_to_queue=force_queue or all(i.descriptor != "GPL" for i in self.sfr.vars.transmit_buffer))
        return result

    @wrap_errors(CommandExecutionException)
    def GPR(self, packet: TransmissionPacket):
        """
        Transmits primary radio
        """
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
        if self.sfr.devices["IMU"] is None:
            tumble = ((0, 0, 0), (0, 0, 0))
        else:
            tumble = self.sfr.devices["IMU"].get_tumble()
        hist_consumption = self.sfr.analytics.historical_consumption(50)
        hist_generation = self.sfr.analytics.historical_generation(50)

        self.transmit(packet, result := [
            hist_consumption.mean() if hist_consumption.shape[0] > 0 else 0,  # Average power consumption
            hist_generation.mean() if hist_generation.shape[0] > 0 else 0,  # Average solar panel generation
            self.sfr.vars.ORBITAL_PERIOD,
            self.sfr.analytics.sunlight_ratio(50),  # Sunlight ratio over last 50 orbits
            self.sfr.vars.SIGNAL_STRENGTH_MEAN,
            self.sfr.vars.SIGNAL_STRENGTH_VARIABILITY,
            self.sfr.vars.BATTERY_CAPACITY_INT,
            *tumble[0],
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
        self.transmit(packet, result := self.sfr.vars.encode())
        return result

    @wrap_errors(CommandExecutionException)
    def GID(self, packet: TransmissionPacket) -> list:
        """
        Transmit signal strength mean and variability
        """
        print("Attempting to transmit science results", file = open("pfs-output.txt", "a"))
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
        else:
            tum = self.sfr.devices["IMU"].get_tumble()
        self.transmit(packet, result := [*tum[0], *tum[1]])
        return result

    @wrap_errors(CommandExecutionException)
    def GMT(self, packet: TransmissionPacket) -> list:
        """
        Transmit magnitude IMU tumble
        """
        if self.sfr.devices["IMU"] is None:
            tum = ((0, 0, 0), (0, 0, 0))
        else:
            tum = self.sfr.devices["IMU"].get_tumble()
        mag = (tum[0][0] ** 2 + tum[0][1] ** 2 + tum[0][2] ** 2) ** 0.5
        self.transmit(packet, result := [mag])
        return result

    @wrap_errors(CommandExecutionException)
    def GTS(self, packet: TransmissionPacket) -> list:
        """
        Transmits time since last mode switch
        """
        dif = time.time() - self.sfr.vars.LAST_MODE_SWITCH
        self.transmit(packet, result := [int(dif / 100000) * 100000, int(dif % 100000)])
        return result

    @wrap_errors(CommandExecutionException)
    def AAP(self, packet: TransmissionPacket) -> list:
        """
        Transmits average power draw over n data points
        """
        df = self.sfr.analytics.historical_consumption(int(packet.args[0]))
        self.transmit(packet, result := [df.mean() if df.shape[0] > 0 else 0])
        return result

    @wrap_errors(CommandExecutionException)
    def APW(self, packet: TransmissionPacket) -> list:
        """
        Transmits last n power draw datapoints
        """
        self.transmit(packet, result := self.sfr.analytics.historical_consumption(int(packet.args[0]))  # Read logs
                      .to_numpy()  # Convert dataframe to numpy array
                      .tolist())  # Convert numpy array to list
        return result

    @wrap_errors(CommandExecutionException)
    def ASV(self, packet: TransmissionPacket) -> list:
        """
        Transmits last n signal strength datapoints
        """
        self.transmit(packet, result := self.sfr.logs["iridium"].read()  # Read log
                      .tail(int(packet.args[0]))  # Get last n rows
                      .to_numpy()  # Convert to numpy array
                      .flatten()  # Compress to 1d
                      .tolist())  # Convert to list
        return result

    @wrap_errors(CommandExecutionException)
    def ASG(self, packet: TransmissionPacket) -> list:
        """
        Transmits last n solar generation datapoints
        """
        self.transmit(packet, result := self.sfr.analytics.historical_generation(int(packet.args[0]))  # Last n rows
                      .to_numpy()  # Convert to numpy array
                      .flatten()  # Compress to 1d
                      .tolist())  # Convert to list
        return result

    @wrap_errors(CommandExecutionException)
    def ATB(self, packet: TransmissionPacket) -> list:
        """
        Transmits last n IMU tumble datapoints
        """
        self.transmit(packet, result := self.sfr.logs["imu"].read()  # Read logs
                      .tail(int(packet.args[0]))  # Last n rows
                      .to_numpy()  # Convert to numpy array
                      .flatten()  # Convert to 1d array
                      .tolist())  # Convert to python list for transmission
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
        df = self.sfr.logs["command"].read()  # Read logs
        search = (df[df["msn"] == packet.args[0]]  # Rows of dataframe where msn is target
                  ["result"]  # Result column
                  [0]  # First item (first time we had a command with this msn, if multiple)
                  .split(":"))  # Split over : to return the result (logged as a : separated string) as a list
        self.transmit(packet, result := [float(i) for i in search])  # Cast strings to floats for transmission
        return result

    @wrap_errors(CommandExecutionException)
    def SUV(self, packet: TransmissionPacket) -> list:
        """
        Set upper threshold for mode switch
        """
        self.sfr.vars.UPPER_THRESHOLD = self.sfr.analytics.volt_to_charge(float(packet.args[0]))
        self.transmit(packet, result := [self.sfr.vars.UPPER_THRESHOLD])
        return result

    @wrap_errors(CommandExecutionException)
    def SLV(self, packet: TransmissionPacket) -> list:
        """
        Set lower threshold for mode switch
        """
        self.sfr.vars.LOWER_THRESHOLD = self.sfr.analytics.volt_to_charge(float(packet.args[0]))
        self.transmit(packet, result := [self.sfr.vars.LOWER_THRESHOLD])
        return result

    @wrap_errors(CommandExecutionException)
    def SDT(self, packet: TransmissionPacket) -> list:
        """
        Set detumble threshold for antenna deployment
        This function is kinda pointless
        """
        self.sfr.vars.DETUMBLE_THRESHOLD = float(packet.args[0])
        self.transmit(packet, result := [self.sfr.vars.DETUMBLE_THRESHOLD])
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
        if int(packet.args[0]) < 0 or int(packet.args[0]) > 3:
            raise CommandExecutionException("Invalid device code!")
        if self.sfr.COMPONENTS[int(packet.args[0])] in self.sfr.vars.FAILURES:
            raise CommandExecutionException("Component already marked as failed!")
        self.sfr.vars.FAILURES.append(self.sfr.COMPONENTS[int(packet.args[0])])
        self.transmit(packet, result := [sum([1 << i for i in range(len(self.sfr.COMPONENTS))
                                              if self.sfr.COMPONENTS[i] in self.sfr.vars.FAILURES])])
        return result

    @wrap_errors(CommandExecutionException)
    def SFR(self, packet: TransmissionPacket) -> list:
        """
        Removes component to failed components list
        """
        if int(packet.args[0]) < 0 or int(packet.args[0]) > len(self.sfr.COMPONENTS):
            raise CommandExecutionException("Invalid device code!")
        if self.sfr.COMPONENTS[int(packet.args[0])] not in self.sfr.vars.FAILURES:
            raise CommandExecutionException("Component not marked as failed!")
        self.sfr.vars.FAILURES.remove(self.sfr.COMPONENTS[int(packet.args[0])])
        self.transmit(packet, result := [sum([1 << i for i in range(len(self.sfr.COMPONENTS))
                                              if self.sfr.COMPONENTS[i] in self.sfr.vars.FAILURES])])
        return result

    @wrap_errors(CommandExecutionException)
    def USM(self, packet: TransmissionPacket) -> list:
        """
        Transmits down summary statistics about our mission
        Transmits:
        1. Time since mission start
        2. Time since last satellite startup
        3. Total energy consumed over mission
        4. Total energy generated over mission
        5. Total amount of data transmitted
        6. Orbital decay (seconds of period lost over mission duration)
        7. Total number of iridium commands received
        8. Total number of aprs commands received
        9. Total number of iridium signal strength measurements taken
        10. Total number of power consumption measurements
        11. Total number of power generation measurements
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
            (df := self.sfr.logs["command"].read())[df["radio"] == "Iridium"].shape[0],
            (df := self.sfr.logs["command"].read())[df["radio"] == "APRS"].shape[0],
            self.sfr.logs["iridium"].read().shape[0],
            self.sfr.logs["power"].read().shape[0],
            self.sfr.logs["solar"].read().shape[0]
        ])
        return result

    @wrap_errors(CommandExecutionException)
    def ITM(self, packet: TransmissionPacket) -> list:
        """
        Transmits No-op acknowledgement
        """
        self.transmit(packet, result := [])
        return result

    @wrap_errors(CommandExecutionException)
    def IHB(self, packet: TransmissionPacket, force_queue=False) -> list:
        """
        Sends heartbeat signal with summary of data, appends only once to queue unless force_queue is True
        :param packet: packet to transmit
        :type packet: TransmissionPacket
        :param force_queue: whether to force this packet into the queue
        :type force_queue: bool
        """
        packet.descriptor = "IHB"  # Manually set the descriptor so we can check if this packet has already been added
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
            (df := self.sfr.logs["command"].read())[df["radio"] == "Iridium"].shape[0],
            (df := self.sfr.logs["command"].read())[df["radio"] == "APRS"].shape[0],
            self.sfr.logs["iridium"].read().shape[0],
            self.sfr.logs["power"].read().shape[0],
            self.sfr.logs["solar"].read().shape[0]
        ], add_to_queue=force_queue or all(i.descriptor != "IHB" for i in self.sfr.vars.transmit_buffer))
        # Append to queue either if force_queue is true or if no other GPL ping has been added to queue
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
            self.sfr.crash()  # Exit script, eps will reset after 16 minutes without ping
        return result

    @wrap_errors(CommandExecutionException)
    def IRB(self, packet: TransmissionPacket) -> None:
        """
        Reboot pi
        """
        self.transmit(packet, [])
        os.system("sudo reboot")

    def ICT(self, packet: TransmissionPacket):
        """
        Clears transmission queue, only to be used in an emergency
        """
        self.sfr.vars.transmit_buffer = []
        self.transmit(packet, result := [])
        return result

    @wrap_errors(CommandExecutionException)
    def ICE(self, packet: TransmissionPacket):
        """
        Remote code execution
        Runs exec on string
        """
        print(packet.args[0], file = open("pfs-output.txt", "a"))
        sfr = self.sfr

        class JankExec:
            """
            Class that allows exec to consistently access sfr, AND local variables (result, string)
            https://stackoverflow.com/questions/1463306/how-does-exec-work-with-locals
            """

            def __init__(self, execstr):
                self.sfr = sfr
                self.result = []
                self.string = False
                exec(f"{execstr}")
                # Set self.result and self.string inside the exec string if return data is needed

        ex = JankExec(packet.args[0])
        print(ex.result, ex.string, file = open("pfs-output.txt", "a"))
        self.transmit(packet, ex.result, ex.string)
        return ex.result

    @wrap_errors(CommandExecutionException)
    def IAK(self, packet: TransmissionPacket):
        """
        Acknowledges attempt to establish contact
        Changes beacon function to heartbeat function in mode
        """
        self.sfr.vars.CONTACT_ESTABLISHED = True
        self.transmit(packet, result := [])
        # Redefine heartbeat clock and function to default mode heartbeat
        # Beacons heartbeat instead of proof of life
        self.sfr.MODE.heartbeat_clock = (m := self.sfr.modes_list["Mode"](self.sfr)).heartbeat_clock
        self.sfr.MODE.heartbeat = m.heartbeat
        return result

    def ZMV(self, packet: TransmissionPacket):
        if str(self.sfr.MODE) != "Outreach":
            raise CommandExecutionException("Cannot use outreach mode function if not in outreach mode")
        self.sfr.MODE.game_queue.append(packet.args[0])
        self.transmit(packet, result := [])
        return result
