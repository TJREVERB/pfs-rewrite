import time
import gc
from MainControlLoop.Drivers.eps import EPS
from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.iridium import Iridium
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer


class Mode:

    # initialization: turn on any necessary devices using EPS, initialize any instance variables, etc.
    def __init__(self, sfr):
        self.LOWER_THRESHOLD = 6  # Lower battery voltage threshold for switching to CHARGING mode
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode
        self.previous_time = 0
        self.sfr = sfr

        self.instruct = {
            "Pin On": self.__turn_on_component,
            "Pin Off": self.__turn_off_component,
            "All On": self.__turn_all_on,
            "All Off": self.__turn_all_off,
        }

        # Could replace the functionality of this dictionary pretty easily with exec, would shrink the code
        self.component_to_object = {  # returns object from component name
                                    # FALSE! This code returns component class, not an object
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

        :return: None
        """
        pass

    # Why don't we call these methods from the subclass?
    # We'd be able to conserve common code like integrate_charge in every run of execute_cycle
    def check_conditions(self) -> bool:
        """
        Checks whether conditions for mode to continue running are still true

        Checks the conditions this mode requires, for example a minimum battery voltage.
        Returns True if conditions are met (to keep executing the mode) or False if mode is no longer applicable.
        Does NOT switch modes, switching modes is only called in main control loop.

        :return:
            boolean: Whether conditions for specific mode is still true or not.
        """
        pass

    def execute_cycle(self) -> None:
        """
        Executes one iteration of mode

        Execute one iteration of this mode. For example: measure signal strength as the orbit location changes.
        NOTE: This method should not execute radio commands, that is done by command_executor class.

        :return: None
        """
        self.integrate_charge()

    def switch_modes(self) -> type:
        """
        Decides which new mode to switch to based on conditions.

        This method is only called from main control loop if conditions for running previous mode are not met.
        Then it decides which new mode to switch to. This mode does not write to sfr or handle manual mode overrides.
        Returns the CLASS NAME of the desired new mode (not initialized, this is done in MCL).

        :returns:
            type: Class name of new mode to switch to.
        """
        pass

    def terminate_mode(self) -> None:
        """
        Safely terminates current mode. Turns off any devices turned on by mode.

        Terminates mode so that new mode knows state of satellite.
        This DOES NOT turn off all devices, simply the ones turned on specifically for this mode.
        This is to prevent modes from turning on manually turned on or off devices.
        Also writes any relevant temporary memory stored in modules to sfr (i.e. iridium buffer).
        Does not handle memory, memory handler is responsible for insufficient memory errors.
        TODO: write memory handler in case of insufficient memory error.

        :returns: None
        """
        # TODO: store iridium buffer and other important data to sfr.
        pass

    def integrate_charge(self):
        """
        Integrate charge in Joules

        :return: None
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
        :return:
            list: list of component failures
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

        Private method, cannot be called outside of class. Must be called using self.instruct dictionary.
        Checks whether component is already on. If already on stop method.
        Gets component object corresponding to component name from self.component_to_object.
        Initializes component object passing in self.sfr.
        Updates sfr.devices to show component name corresponding to initialized component object (shows component is on).
        Turns component on via eps.
        Turns on serial converter if applicable to component.
        If previous step: Sets serial converter status to True in sfr.serial_converters to show serial converter is on.

        :returns: None
        """
        if self.sfr.devices[component] is not None:  # if component is already on, stop method from running further
            return None

        self.sfr.devices[component] = self.component_to_object[component](self.sfr)  # registers component as on by setting component status in sfr to object instead of None
        self.sfr.eps.commands["Pin On"](component)  # turns on component
        if component in self.sfr.component_to_serial:  # see if component has a serial converter to open
            # SUGGESTION: Collapse the following two lines into one line
            # Remove third line and serial_converters dictionary
            serial_converter = self.sfr.component_to_serial[component]  # gets serial converter name of component
            self.sfr.eps.commands["Pin On"](serial_converter)  # turns on serial converter
            self.sfr.serial_converters[serial_converter] = True  # sets serial converter status to True (on)

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    def __turn_off_component(self, component: str):
        """
        Turns off component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.

        Private method, cannot be called outside of class. Must be called using self.instruct dictionary.
        Checks whether component is already off. If already off stop method.
        Sets component in sfr.devices to None (to show component is off).
        Turns component off via eps.
        Turns off serial converter if applicable to component.
        If previous step: Sets serial status to False in sfr.serial_converters to show serial converter is off.

        :returns: None
        """
        # TODO: if component iridium: copy iridium command buffer to sfr to avoid wiping commands when switching modes
        if self.sfr.devices[component] is None:  # if component is off, stop method from running further.
            return None
        self.sfr.devices[component] = None  # sets device object in sfr to None instead of object
        self.sfr.eps.commands["Pin Off"](component)  # turns component off
        if component in self.sfr.component_to_serial:  # see if component has a serial converter to close
            # Same suggestion as for __turn_on_component
            serial_converter = self.sfr.component_to_serial[component]  # get serial converter name for component
            self.sfr.eps.commands["Pin Off"](serial_converter)  # turn off serial converter
            self.sfr.serial_converters[serial_converter] = False  # sets serial converter status to False (off)

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    def __turn_all_on(self, exceptions=None):
        """
        Turns all components on automatically, except for Antenna Deployer.

        Calls __turn_on_component for every key in self.devices. Except for those in exceptions list parameter.
        Only calls __turn_on_components if device is off.

        Parameters:
            optional, list: components to not turn on, default is ["Antenna Deployer"]

        :return: None
        """
        # Why not put exceptions=["Antenna Deployer"] in the method header?
        if exceptions is None:
            exceptions = ["Antenna Deployer"]
        for key in self.sfr.devices:
            if not self.sfr.devices[key] and key not in exceptions:  # if device is off and not in exceptions
                self.__turn_on_component(key)  # turn on device and serial converter if applicable

    def __turn_all_off(self, exceptions=None):
        """
        Turns all components off automatically, except for Antenna Deployer.

        Calls __turn_off_component for every key in self.devices. Except for those in exceptions list parameter.
        Only calls __turn_off_components if device is on.

        Parameters:
            optional, list: components to not turn off, default is ["Antenna Deployer"]

        :return: None
        """
        if exceptions is None:
            exceptions = ["Antenna Deployer"]
        for key in self.sfr.devices:
            if self.sfr.devices[key] and key not in exceptions:  # if device  is on and not in exceptions
                self.__turn_off_component(key)  # turn off device and serial converter if applicable
