import time
from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.iridium import Iridium
from MainControlLoop.Drivers.bno055 import IMU
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer
from MainControlLoop.lib.exceptions import decorate_all_callables, wrap_errors, SystemError


class Mode:
    # initialization: does not turn on devices, initializes instance variables
    @wrap_errors(SystemError)
    def __init__(self, sfr, wait = 40, thresh = 2):
        self.LOWER_THRESHOLD = 6  # Lower battery voltage threshold for switching to CHARGING mode
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode
        self.previous_time = 0
        self.sfr = sfr
        self.last_iridium_poll_time = 0
        self.PRIMARY_IRIDIUM_WAIT_TIME = wait # wait time for iridium polling if iridium is main radio (default to 40 seconds)
                                            # Actual time between read/write will depend on signal availability
        self.SIGNAL_THRESHOLD = thresh # Lower threshold to read or transmit
        self.instruct = {
            "Pin On": self.__turn_on_component,
            "Pin Off": self.__turn_off_component,
            "All On": self.__turn_all_on,
            "All Off": self.__turn_all_off
        }

        self.component_to_class = {  # returns class from component name
            "Iridium": Iridium,
            "APRS": APRS,
            "IMU": IMU,
            "Antenna Deployer": AntennaDeployer
        }
        decorate_all_callables(self, SystemError)

    def __str__(self):  # returns mode name as string
        pass

    def start(self) -> None:
        """
        Runs initial setup for a mode. Turns on and off devices for a specific mode.
        """
        pass

    def check_conditions(self) -> bool:
        """
        Checks whether conditions for mode to continue running are still true.
        NOTE: THIS METHOD DOES NOT SWITCH MODES OR MODIFY THE STATE FIELD REGISTRY. THAT IS DONE IN THE MCL
        :return: (bool) true to stay in mode, false to exit
        """
        return True

    def update_conditions(self) -> None:
        """
        Updates conditions dict in each mode
        """
        pass

    def switch_mode(self):
        """
        Returns which mode to switch to
        """
        pass

    def execute_cycle(self) -> None:
        """
        Executes one iteration of mode
        For example: measure signal strength as the orbit location changes.
        NOTE: This method should not execute radio commands, that is done by command_executor class.
        """
        pass

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
        # If primary radio is iridium and enough time has passed
        if self.sfr.vars.PRIMARY_RADIO == "Iridium" and \
                time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME \
                    and self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
            # get all messages from iridium, store them in sfr
            try:
                self.sfr.devices["Iridium"].next_msg()
            except RuntimeError as e:
                print(e)  # TODO: IMPLEMENT CONTINGENCIES
            self.last_iridium_poll_time = time.time()
        # If APRS is on for whatever reason
        if self.sfr.devices["APRS"] is not None:
            # add aprs messages to sfr
            self.sfr.devices["APRS"].next_msg()
        # commands will be executed in the mode.py's super method for execute_cycle using a command executor
        
        #TODO: Update Iridium time

    def transmit_radio(self) -> None:
        """
        Transmit any messages in the transmit queue
        :return: (bool) whether all transmit queue messages were sent
        """
        # If primary radio is iridium and enough time has passed
        if self.sfr.vars.PRIMARY_RADIO == "Iridium" and \
                time.time() - self.last_iridium_poll_time > self.PRIMARY_IRIDIUM_WAIT_TIME \
                    and self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
            while len(self.sfr.vars.transmit_buffer) > 0: # attempt to transmit transmit buffer
                packet = self.vars.transmit_buffer.pop(0)
                if not self.sfr.command_executor.transmit(packet):
                    return False
        # If primary radio is APRS
        if self.sfr.vars.PRIMARY_RADIO == "APRS":
            while len(self.sfr.vars.transmit_buffer) > 0: # attempt to transmit transmit buffer
                packet = self.vars.transmit_buffer.pop(0)
                if not self.sfr.command_executor.transmit(packet):
                    return False
        return True

    def check_time(self) -> None:
        """
        Checks rtc time against iridium time, should be called AFTER all tx/rx functions
        """

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
            if self.sfr.devices[device] is not None and not self.sfr.devices[device].functional():
                result.append(device)
        return result

    def __turn_on_component(self, component: str) -> None:
        """
        Turns on component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.
        :param component: (str) component to turn on
        """
        if self.sfr.devices[component] is not None:  # if component is already on, stop method from running further
            return None
        if self.sfr.vars.LOCKED_DEVICES[component] is True:  # if component is locked, stop method from running further
            return None

        self.sfr.eps.commands["Pin On"](component)  # turns on component
        self.sfr.devices[component] = self.component_to_class[component](self.sfr)  # registers component as on by setting component status in sfr to object instead of None
        if component in self.sfr.component_to_serial:  # see if component has a serial converter to open
            serial_converter = self.sfr.component_to_serial[component]  # gets serial converter name of component
            self.sfr.eps.commands["Pin On"](serial_converter)  # turns on serial converter
            self.sfr.serial_converters[serial_converter] = True  # sets serial converter status to True (on)

        if component == "APRS":
            self.sfr.devices[component].disable_digi()
        if component == "IMU":
            self.sfr.devices[component].start()

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    def __turn_off_component(self, component: str) -> None:
        """
        Turns off component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.
        :param component: (str) component to turn off
        """
        if self.sfr.devices[component] is None:  # if component is off, stop method from running further.
            return None
        if self.sfr.vars.LOCKED_DEVICES[component] is True:  # if component is locked, stop method from running further
            return None

        if component == "Iridium" and self.sfr.devices["Iridium"] is not None: # Read in MT buffer to avoid wiping commands when mode switching
            try:
                self.sfr.devices[component].next_msg()
            except Exception as e:
                print(e)

        self.sfr.devices[component] = None  # sets device object in sfr to None instead of object
        self.sfr.eps.commands["Pin Off"](component)  # turns component off
        if component in self.sfr.component_to_serial:  # see if component has a serial converter to close
            # Same suggestion as for __turn_on_component
            serial_converter = self.sfr.component_to_serial[component]  # get serial converter name for component
            self.sfr.eps.commands["Pin Off"](serial_converter)  # turn off serial converter
            self.sfr.serial_converters[serial_converter] = False  # sets serial converter status to False (off)

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    def __turn_all_on(self, exceptions=None, override_default_exceptions=False) -> None:
        """
        Turns all components on automatically, except for Antenna Deployer.
        Calls __turn_on_component for every key in self.devices except for those in exceptions parameter
        :param exceptions: (list) components to not turn on, default is ["Antenna Deployer, IMU"]
        :param override_default_exceptions: (bool) whether or not to use default exceptions
        :return: None
        """

        if override_default_exceptions:  # if True no default exceptions
            default_exceptions = []
        else:  # normally exceptions
            default_exceptions = ["Antenna Deployer", "IMU"]
        if exceptions is not None:
            for exception in exceptions:  # loops through custom device exceptions and adds to exceptions list
                default_exceptions.append(exception)

        exceptions = default_exceptions  # sets to exceptions list

        for key in self.sfr.devices:
            if not self.sfr.devices[key] and key not in exceptions:  # if device is off and not in exceptions
                self.__turn_on_component(key)  # turn on device and serial converter if applicable

    def __turn_all_off(self, exceptions=None, override_default_exceptions=False) -> None:
        """
        Turns all components off automatically, except for Antenna Deployer.
        Calls __turn_off_component for every key in self.devices. Except for those in exceptions parameter
        :param exceptions: (list) components to not turn off, default is ["Antenna Deployer, IMU"]
        :param override_default_exceptions: (bool) whether or not to use default exceptions
        :return: None
        """
        if override_default_exceptions:
            default_exceptions = []
        else:
            default_exceptions = ["Antenna Deployer", "IMU"]
        if exceptions is not None:
            for exception in exceptions:
                default_exceptions.append(exception)

        exceptions = default_exceptions

        for key in self.sfr.devices:
            if self.sfr.devices[key] and key not in exceptions:  # if device  is on and not in exceptions
                self.__turn_off_component(key)  # turn off device and serial converter if applicable
