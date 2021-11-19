import time


class CommandExecutor:
    def __init__(self, sfr):
        self.sfr = sfr
        self.TJ_PREFIX = "TJ;"
        self.OUTREACH_PREFIX = "OUT;"
        self.aprs_primary_registry = {
            "NOP": lambda: self.transmit("Hello"),  # Test method, transmits "Hello"
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
            "TBL": self.TBL,  # Transmits tumble value
            "MLK": self.MLK,
            "Arguments": { #this doesn't make sense, we'd have to call primary_registry["arguments"].keys() to check if a string is one of these commands
                "U": self.U,  # Set upper threshold
                "L": self.L,  # Set lower threshold
                "D": self.D
            }
        }
        # IMPLEMENT FULLY
        self.aprs_secondary_registry = {
            # Reads and transmits battery voltage
            "BVT": lambda: self.sfr.devices["Iridium"].transmit(str(self.sfr.eps.telemetry["VBCROUT"]())),
            "Arguments": { #this doesn't make sense
            }
        }
    
    def execute(self) -> None:
        """
        Execute all commands in buffers
        """
        if self.sfr.devices["Iridium"] is not None:  # if iridium is on
            # IRIDIUM
            for i in self.sfr.IRIDIUM_RECEIVED_COMMAND:  # Iterate through all received commands
                if i in self.iridium_registry.keys:  # If command exists
                    self.iridium_registry[i]()  # Execute command
                elif i[0] in self.iridium_registry["Arguments"].keys:  # If command has arguments
                    self.iridium_registry["Arguments"][i[0]](i[1], i[2])  # Execute command
                else:
                    self.error("Iridium", self.sfr.IRIDIUM_RECEIVED_COMMAND)  # Transmit error
            self.sfr.IRIDIUM_RECEIVED_COMMAND = []  # Clear buffer
        # APRS
        if self.sfr.devices["APRS"] is not None:  # if APRS is on
            if self.sfr.APRS_RECEIVED_COMMAND != "":  # If message was received
                raw_command = self.sfr.APRS_RECEIVED_COMMAND
                if raw_command.find(self.TJ_PREFIX) != -1:  # If message is from us
                    command = raw_command[raw_command.find(self.TJ_PREFIX) +  # Extract command
                                            len(self.TJ_PREFIX):
                                            raw_command.find(self.TJ_PREFIX) +
                                            len(self.TJ_PREFIX) + 3]
                    if command in self.aprs_primary_registry.keys:  # If command is real
                        self.aprs_primary_registry[command]()  # Execute command
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
    
    def error(self, radio, command):
        """
        Transmit an error message over radio that received command
        :param radio: (str) radio which received erraneous command, "Iridium" or "APRS"
        :param command: (str) command which failed
        """
        if radio == "Iridium":
            self.sfr.devices["Iridium"].transmit("ERR:" + command)
        elif radio == "APRS":
            self.sfr.devices["APRS"].transmit("ERR:" + command)

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

    def U(self, a, b):  #TODO: Implement
        self.sfr.UPPER_THRESHOLD = int(a) + float(b) / 10

    def L(self, a, b):  #TODO: Implement
        self.sfr.LOWER_THRESHOLD = int(a) + float(b) / 10

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
        Transmit IMU tumble
        """
    
    def MLK(self):
        """
        Enable Mode Lock
        """
    
    def D(self, a, b):
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