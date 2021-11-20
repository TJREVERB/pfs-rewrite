import time


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
            # Reset power to the entire satellite (!!!!)
            "RST": self.RST,
            # Transmit proof of life through Iridium to ground station
            "WVE": self.WVE,
            # Transmit total power draw of connected components
            "PWR": self.PWR,
            # Calculate and transmit Iridium signal strength variability
            "SSV": self.SSV,
            "SVF": None,  # TODO: Implement #Transmit full rssi data logs
            # Transmit current solar panel production
            "SOL": self.SOL,
            "TBL": self.TBL,  # Transmits tumble value (Magnitude of gyroscope vector)
            "TBF": self.TBF,  # Transmits 3 axis gyroscope and magnetometer readings (full tumble readouts)
            "MLK": self.MLK,
            "ORB": self.ORB,
            "UVT": self.UVT, # Set upper threshold
            "LVT": self.LVT, # Set lower threshold
            "DLK": self.DLK,
        }

        # IMPLEMENT FULLY
        self.aprs_secondary_registry = { #Secondary command registry for APRS, in outreach mode
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
        if self.sfr.devices["Iridium"] is not None:  # if iridium is on
            # IRIDIUM
            while len(self.sfr.IRIDIUM_RECEIVED_COMMAND) > 0:  # Iterate through all received commands
                cmd = self.sfr.IRIDIUM_RECEIVED_COMMAND.pop(0)
                msn = cmd[1]
                prcmd = cmd[0].split(":") 

                if prcmd[0] in self.primary_registry.keys():  # If command exists
                    try:
                        if len(prcmd) == 2 and prcmd[0] in self.arg_registry: #If an argument is included and the command actually requires an argument, execute with arg
                            self.primary_registry[prcmd[0]](prcmd[1])
                        elif len(prcmd) == 1 and prcmd[0] not in self.arg_registry: #If an argument is not included, and the command does not require an argument, execute without arg
                            self.primary_registry[prcmd[0]]() 
                        else:
                            self.error("Iridium", msn, "Incorrect number of arguments received")
                    except Exception as e:
                        self.error("Iridium", msn, "Exec error: " + str(e)) #returns exception
        # APRS TODO: fix this absolute monstrosity of code
        if self.sfr.devices["APRS"] is not None:  # if APRS is on
            if self.sfr.APRS_RECEIVED_COMMAND != "":  # If message was received
                raw_command = self.sfr.APRS_RECEIVED_COMMAND
                if raw_command.find(self.TJ_PREFIX) != -1:  # If message is from us
                    command = raw_command[raw_command.find(self.TJ_PREFIX) +  # Extract command
                                            len(self.TJ_PREFIX):
                                            raw_command.find(self.TJ_PREFIX) +
                                            len(self.TJ_PREFIX) + 3]
                    
                    if command in self.primary_registry.keys():  # If command is real
                        self.primary_registry[command]()  # Execute command
                    elif i[0] in self.aprs_primary_registry["Arguments"].keys:  # If command has arguments
                        self.aprs_primary_registry["Arguments"][i[0]](i[1], i[2])  # Execute command
                    else:
                        self.error("APRS", command)  # Transmit error message
                elif raw_command.find(self.OUTREACH_PREFIX) != -1:  # If command is from outreach
                    command = raw_command[raw_command.find(self.OUTREACH_PREFIX) +  # Extract command
                                            len(self.OUTREACH_PREFIX):
                                            raw_command.find(self.OUTREACH_PREFIX) +
                                            len(self.OUTREACH_PREFIX) + 3]
                    if command in self.aprs_secondary_registry.keys:  # If command is real
                        self.aprs_secondary_registry[command]()  # Execute command
                    elif i[0] in self.aprs_secondary_registry["Arguments"].keys:  # If command has arguments
                        self.aprs_secondary_registry["Arguments"][i[0]](i[1], i[2])  # Execute command
                    else:
                        self.error("APRS", command)  # Transmit error message
                self.sfr.APRS_RECEIVED_COMMAND = ""  # Clear buffer
    
    def error(self, radio, command, description):
        """
        Transmit an error message over radio that received command
        :param radio: (str) radio which received erraneous command, "Iridium" or "APRS"
        :param command: (str) command which failed in case of APRS, or MSN number of failed command in case of Iridium
        :param description: (str) detailed description of failure
        """
        if radio == "Iridium":
            self.sfr.devices["Iridium"].transmit("ERR" + command + description) #DO NOT ADD PUNCTUATION TO IRIDIUM MESSAGES, IT MESSES UP ENCODING
        elif radio == "APRS":
            self.sfr.devices["APRS"].transmit("ERR:" + command + ":" + description)

    def transmit(self, message: str):
        """
        Transmits time + message string from primary radio to ground station
        """
        # TODO: how to handle if Iridium or APRS is off
        if self.sfr.PRIMARY_RADIO == "Iridium":
            self.sfr.devices["Iridium"].transmit(message)
        elif self.sfr.PRIMARY_RADIO == "APRS":
            self.sfr.devices["APRS"].transmit(message)

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
            self.transmit("NO SWITCH")
        else:
            self.sfr.MODE = self.sfr.modes_list["Charging"]
            self.transmit("SWITCH CHARGING")

    def SCI(self):
        """
        Switches current mode to science mode
        """
        if str(self.sfr.mode_obj) == "Science":
            self.transmit("Already in science mode, no mode switch executed")
        else:
            self.sfr.MODE = self.sfr.modes_list["Science"]
            self.transmit("SWITCH SCIENCE")

    def OUT(self):
        """
        Switches current mode to outreach mode
        """
        if str(self.sfr.mode_obj) == "Outreach":
            self.transmit("NO SWITCH")
        else:
            self.sfr.MODE = self.sfr.modes_list["Outreach"]
            self.transmit("SWITCH OUTREACH")

    def UVT(self, v):  #TODO: Implement
        self.sfr.UPPER_THRESHOLD = float(v)

    def LVT(self, v):  #TODO: Implement
        self.sfr.LOWER_THRESHOLD = float(v)

    def RST(self):  #TODO: Implement, how to power cycle satelitte without touching CPU power
        self.sfr.mode_obj.instruct["All Off"](exceptions=[])
        time.sleep(.5)
        self.sfr.eps.commands["Bus Reset"](["Battery", "5V", "3.3V", "12V"])

    def WVE(self):
        """
        Transmits proof of life via Iridium, along with critical component data
        using iridium.wave (not transmit function)
        """
        self.sfr.iridium.wave(self.sfr.eps.telemetry["VBCROUT"](), self.sfr.eps.solar_power(),
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
        self.transmit(str(self.sfr.SIGNAL_STRENTH_VARIABILITY))
    
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
            if self.sfr.locked_devices[device_codes[a + b]]:
                self.sfr.locked_devices[device_codes[a + b]] = False
                self.transmit(device_codes[a + b] + " UNLOCKED")
            else:
                self.sfr.locked_devices[device_codes[a + b]] = True
                self.transmit(device_codes[a + b] + " LOCKED")
        except KeyError:
            self.error(self.sfr.PRIMARY_RADIO, "D")

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
        self.transmit(str(self.sfr.ORBITAL_PERIOD))
