import time
import pandas as pd
from datetime import datetime


class CommandExecutor:
    def __init__(self, sfr):
        self.sfr = sfr
        self.TJ_PREFIX = "TJ;"
        self.OUTREACH_PREFIX = "OUT;"

        self.GARBLED = "GRB" #String for garbled message

        self.primary_registry = { #primary command registry for BOTH Iridium and APRS
            "NOP": lambda: self.transmit("0OK"),  # Test method, transmits "Hello"
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

    def execute(self) -> None:
        """
        Execute all commands in buffers
        """
        #  TODO: CHECK FOR GARBLED MESSAGES, IF NEEDED
        if self.sfr.devices["Iridium"] is not None:  # if iridium is on
            # IRIDIUM
            while len(self.sfr.vars.IRIDIUM_RECEIVED_COMMAND) > 0:  # Iterate through all received commands
                command, msn = self.sfr.vars.IRIDIUM_RECEIVED_COMMAND.pop(0)
                self.exec_cmd(command, "Iridium", self.primary_registry, msn)
        # APRS
        if self.sfr.devices["APRS"] is not None:  # if APRS is on
            if self.sfr.vars.APRS_RECEIVED_COMMAND != []:  # If message was received
                raw_command = self.sfr.vars.APRS_RECEIVED_COMMAND
                if raw_command.find(self.TJ_PREFIX) != -1:  # If message is from us #TODO: INSTEAD OF ASSUMING IT IS AT THE END OF THE STRING, LOOK FOR : end character
                    command = raw_command[raw_command.find(self.TJ_PREFIX) + len(self.TJ_PREFIX):].strip() # Extract command
                    self.exec_cmd(command, "APRS", self.primary_registry)
                elif raw_command.find(self.OUTREACH_PREFIX) != -1:  # If command is from outreach
                    command = raw_command[raw_command.find(self.OUTREACH_PREFIX) + len(self.OUTREACH_PREFIX):].strip() # Extract command
                    self.exec_cmd(command, "APRS", self.aprs_secondary_registry)
                self.sfr.vars.APRS_RECEIVED_COMMAND.pop(0)  # Clear buffer

    def exec_cmd(self, command, radio, registry: dict, msn=-1):
        """
        Helper function for execute()
        :param command: (str) command as read from sfr
        :param radio: (str) radio reading the command
        :param registry: (dict) which command registry to use
        :param msn: (int) If radio is Iridium, MSN number of message
        """
        prcmd = command.split(":")  #list: command, arg

        if prcmd[0] in registry.keys():  # If command exists
            try:
                if len(prcmd) == 2 and prcmd[0] in self.arg_registry: #If an argument is included and the command actually requires an argument, execute with arg
                    registry[prcmd[0]](prcmd[1])
                elif len(prcmd) == 1 and prcmd[0] not in self.arg_registry: #If an argument is not included, and the command does not require an argument, execute without arg
                    registry[prcmd[0]]()
                else:
                    if radio == "Iridium":
                        self.error(radio, msn, "Incorrect number of arguments received")
                    else:
                        self.error(radio, prcmd[0], "Incorrect number of arguments received")
            except Exception as e:
                if radio == "Iridium":
                    self.error(radio, msn, "Exec error: " + str(e)) #returns exception
                else:
                    result = self.error(radio, prcmd[0], "Exec error: " + str(e))

        with open(self.COMMAND_LOG_PATH, "a") as f:
            f.write(f"{time.time()},{radio},{prcmd[0]},{prcmd[1]},{msn},{result}\n")

    def execute_(self):
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
