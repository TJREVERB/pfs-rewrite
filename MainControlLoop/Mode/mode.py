import time
from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.iridium import Iridium
from MainControlLoop.Drivers.bno055 import IMU
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer


class Mode:
    # initialization: turn on any necessary devices using EPS, initialize any instance variables, etc.
    def __init__(self, sfr):
        self.LOWER_THRESHOLD = 6  # Lower battery voltage threshold for switching to CHARGING mode
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode
        self.previous_time = 0
        self.sfr = sfr
        self.command_executor = self.CommandExecutor(sfr, self)

        self.instruct = {
            "Pin On": self.__turn_on_component,
            "Pin Off": self.__turn_off_component,
            "All On": self.__turn_all_on,
            "All Off": self.__turn_all_off,
        }

        self.component_to_class = {  # returns class from component name
            "Iridium": Iridium,
            "APRS": APRS,
            "IMU": IMU,
            "Antenna Deployer": AntennaDeployer
        }

    def __str__(self):  # returns mode name as string
        pass

    def start(self) -> None:
        """
        Runs initial setup for a mode. Turns on devices for a specific mode.
        """
        pass

    def check_conditions(self) -> bool:
        """
        Checks whether conditions for mode to continue running are still true
        Updates state field registry with mode to switch to if necessary
        Does not mode.terminate_mode(), mode.__init__(), or mode.start(), mcl handles this
        :return: (bool) true to stay in mode, false to exit
        """
        pass

    def update_conditions(self) -> None:
        """
        Updates conditions dict in each mode
        """
        pass

    def execute_cycle(self) -> None:
        """
        Executes one iteration of mode
        For example: measure signal strength as the orbit location changes.
        NOTE: This method should not execute radio commands, that is done by command_executor class.
        """
        self.integrate_charge()
        self.command_executor.execute()

    def terminate_mode(self) -> None:
        """
        Safely terminates current mode.
        This DOES NOT turn off all devices, simply the ones turned on specifically for this mode.
        This is to prevent modes from turning on manually turned on or off devices.
        Also writes any relevant temporary memory stored in modules to sfr (i.e. iridium buffer).
        Does not handle memory, memory handler is responsible for insufficient memory errors.
        TODO: write memory handler in case of insufficient memory error.
        """
        self.sfr.dump()
        pass

    def read_radio(self) -> None:
        """
        Function for each mode to implement to determine how it will use the specific radios
        """
        pass

    def integrate_charge(self) -> None:
        """
        Integrate charge in Joules
        """
        draw = self.sfr.eps.total_power(4)[0]
        gain = self.sfr.eps.solar_power()
        self.sfr.BATTERY_CAPACITY_INT -= (draw - gain) * (time.perf_counter() - self.previous_time)
        self.previous_time = time.perf_counter()

    def systems_check(self) -> list:
        """
        Performs a systems check of components that are on and returns a list of component failures
        TODO: implement system check of antenna deployer
        TODO: account for different exceptions in .functional() and attempt to troubleshoot
        :return: (list) component failures
        """
        result = []
        for device in self.sfr.devices:
            # TODO: Implement functional for all devices
            # if the device is on and not functional
            if self.sfr.devices[device] is not None and not self.sfr.devices[device].functional:
                result.append(device)
        return result

    def __turn_on_component(self, component: str) -> None:
        """
        Turns on component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.
        :param component: (str) component to turn on
        """
        if self.sfr.devices[component] is not None:  # if component is already on, stop method from running further
            return None
        if self.sfr.locked_devices[component]:  # if component is locked, stop method from running further
            return None
        self.sfr.devices[component] = self.component_to_class[component](self.sfr)  # registers component as on by setting component status in sfr to object instead of None
        self.sfr.eps.commands["Pin On"](component)  # turns on component
        if component in self.sfr.component_to_serial:  # see if component has a serial converter to open
            # SUGGESTION: Collapse the following two lines into one line
            # Remove third line and serial_converters dictionary
            serial_converter = self.sfr.component_to_serial[component]  # gets serial converter name of component
            self.sfr.eps.commands["Pin On"](serial_converter)  # turns on serial converter
            self.sfr.serial_converters[serial_converter] = True  # sets serial converter status to True (on)

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    def __turn_off_component(self, component: str) -> None:
        """
        Turns off component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.
        :param component: (str) component to turn off
        """
        # TODO: if component iridium: copy iridium command buffer to sfr to avoid wiping commands when switching modes
        if self.sfr.devices[component] is None:  # if component is off, stop method from running further.
            return None
        if self.sfr.locked_devices[component]:  # if component is locked, stop method from running further
            return None
        if component == "Iridium" and self.sfr.devices["Iridium"] is not None:  # if iridium is already on
            self.sfr.devices["Iridium"].SHUTDOWN()  # runs proprietary off function for iridium before pdm off
        self.sfr.devices[component] = None  # sets device object in sfr to None instead of object
        self.sfr.eps.commands["Pin Off"](component)  # turns component off
        if component in self.sfr.component_to_serial:  # see if component has a serial converter to close
            # Same suggestion as for __turn_on_component
            serial_converter = self.sfr.component_to_serial[component]  # get serial converter name for component
            self.sfr.eps.commands["Pin Off"](serial_converter)  # turn off serial converter
            self.sfr.serial_converters[serial_converter] = False  # sets serial converter status to False (off)

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    def __turn_all_on(self, exceptions=None) -> None:
        """
        Turns all components on automatically, except for Antenna Deployer.
        Calls __turn_on_component for every key in self.devices except for those in exceptions parameter
        :param exceptions: (list) components to not turn on, default is ["Antenna Deployer"]
        """

        if exceptions is None:
            exceptions = ["Antenna Deployer", "IMU"]
        else:
            default_exceptions = ["Antenna Deployer", "IMU"]
            for exception in exceptions:
                default_exceptions.append(exception)
            exceptions = default_exceptions
        for key in self.sfr.devices:
            if not self.sfr.devices[key] and key not in exceptions:  # if device is off and not in exceptions
                self.__turn_on_component(key)  # turn on device and serial converter if applicable

    def __turn_all_off(self, exceptions=None) -> None:
        """
        Turns all components off automatically, except for Antenna Deployer.
        Calls __turn_off_component for every key in self.devices. Except for those in exceptions parameter
        :param exceptions: (list) components to not turn off, default is ["Antenna Deployer"]
        """
        if exceptions is None:
            exceptions = ["Antenna Deployer", "IMU"]
        else:
            default_exceptions = ["Antenna Deployer", "IMU"]
            for exception in exceptions:
                default_exceptions.append(exception)
            exceptions = default_exceptions
        for key in self.sfr.devices:
            if self.sfr.devices[key] and key not in exceptions:  # if device  is on and not in exceptions
                self.__turn_off_component(key)  # turn off device and serial converter if applicable

    class CommandExecutor:
        def __init__(self, sfr, mode):
            self.sfr = sfr
            self.mode = mode
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
                "Arguments": {
                    "U": self.U,  # Set upper threshold
                    "L": self.L,  # Set lower threshold
                    "D": self.D
                }
            }
            # IMPLEMENT FULLY
            self.aprs_secondary_registry = {
                # Reads and transmits battery voltage
                "BVT": lambda: self.iridium.transmit(str(self.eps.telemetry["VBCROUT"]())),
                "Arguments": {

                }
            }
            self.iridium_registry = {
                # Reads and transmits battery voltage
                "0": lambda: self.transmit("Hello"),
                "1": self.BVT,
                "2": self.CHG,
                "3": self.SCI,
                "4": self.OUT,
                "5": self.RST,
                "6": self.WVE,
                "7": self.PWR,
                "8": self.SSV,
                "9": self.SOL,
                "10": self.TBL,
                "11": self.MLK,
                "Arguments": {
                    "U": self.U,
                    "L": self.L,
                    "D": self.D
                }
            }
        
        def execute(self) -> None:
            """
            Execute all commands in buffers
            """
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
            if self.sfr.APRS_RECEIVED_COMMAND is not "":  # If message was received
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
            if radio is "Iridium":
                self.sfr.devices["Iridium"].transmit("ERR:" + command)
            elif radio is "APRS":
                self.sfr.devices["APRS"].transmit("ERR:" + command)

        def transmit(self, message: str):
            """
            Transmits time + message string from primary radio to ground station
            """
            if self.sfr.PRIMARY_RADIO is "Iridium":
                self.sfr.devices["Iridium"].transmit(message)
            elif self.sfr.PRIMARY_RADIO is "APRS":
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
            if str(self.mode) == "Charging":
                self.transmit("NO SWITCH")
            else:
                self.sfr.MODE = self.sfr.modes_list["Charging"]
                self.transmit("SWITCH CHARGING")

        def SCI(self):
            """
            Switches current mode to science mode
            """
            if str(self.mode) == "Science":
                self.transmit("Already in science mode, no mode switch executed")
            else:
                self.sfr.MODE = self.sfr.modes_list["Science"]
                self.transmit("SWITCH SCIENCE")

        def OUT(self):
            """
            Switches current mode to outreach mode
            """
            if str(self.mode) == "Outreach":
                self.transmit("NO SWITCH")
            else:
                self.sfr.MODE = self.sfr.modes_list["Outreach"]
                self.transmit("SWITCH OUTREACH")

        def U(self, a, b):  #TODO: Implement
            self.sfr.UPPER_THRESHOLD = int(a) + float(b) / 10

        def L(self, a, b):  #TODO: Implement
            self.sfr.LOWER_THRESHOLD = int(a) + float(b) / 10

        def RST(self):  #TODO: Implement, how to power cycle satelitte without touching CPU power
            self.mode.instruct["All Off"](exceptions=[])
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
            self.transmit(str(self.eps.total_power(3)[0]))
        
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
