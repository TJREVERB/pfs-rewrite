import time
import gc
from MainControlLoop.Drivers.eps import EPS
from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.iridium import Iridium
from MainControlLoop.Drivers.imu import IMU
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer


class Mode:

    # initialization: turn on any necessary devices using EPS, initialize any instance variables, etc.
    def __init__(self, sfr):
        self.LOWER_THRESHOLD = 6  # Lower battery voltage threshold for switching to CHARGING mode
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode
        self.previous_time = 0
        self.sfr = sfr

        self.instruct = {
            "Pin On": self.turn_on_component,
            "Pin Off": self.turn_off_component,
            "All On": self.turn_all_on,
            "All Off": self.turn_all_off,
        }
        self.component_to_serial = {
            "Iridium": "UART-RS232",
            "APRS": "SPI-UART"
        }

        self.component_to_object = {  # returns object from component name
            "Iridium": Iridium,
            "APRS": APRS,
            "IMU": IMU,
            "Antenna Deployer": AntennaDeployer
        }
    def __str__(self):  # returns mode name as string
        pass
    # turns on and off devices for specific mode
    def start(self):
        pass


    # checks the conditions this mode requires, for example a minimum battery voltage store any mode conditions as
    # instance variables so that you only have to retrieve them once, and can then use them in switch_modes right
    # after if necessary RETURN: True if conditions are met, False otherwise DO NOT SWITCH MODES IF FALSE - this is
    # up to the main control loop to decide implemented for the seach specific mode
    def check_conditions(self):
        pass

    # execute one iteration of this mode, for example: read from the radio and retrieve EPS telemtry one time this
    # method should take care of reading from the radio and executing commands (which is happening in basically all
    # of the modes) NOTE: receiving and executing commmands is not up to the main control loop because different
    # modes might do this in different manners save any values to instance varaibles if they may be necessary in
    # future execute_cycle calls this method is called in each specific mode before specific execute_cycle for that
    # code
    def execute_cycle(self):
        self.integrate_charge()

    # If conditions (from the check_conditions method) for a running mode are not met, it will choose which new mode
    # to switch to. THIS SHOULD ONLY BE CALLED FROM MAIN CONTROL LOOP This is a mode specific switch, meaning the
    # current mode chooses which new mode to switch to based only on the current mode's conditions. This method does
    # not handle manual override commands from the groundstation to switch to specific modes, that's handled by the
    # Main Control Loop. implemented for the specific modes
    # returns Mode object to switch to, but does not init it
    def switch_modes(self) -> object:
        pass

    # Safely terminates the current mode: Turns off any non-essential devices that were turned on (non-essential
    # meaning devices that other modes might not need, so don't turn off the flight pi...) delete (using del) any
    # memory-expensive instance variables so that we don't have to wait for python garbage collector to clear them
    # NOTE: This should be standalone, so it can be called by itself on a mode
    # object, but it should also be used in switch_modes
    def terminate_mode(self):
        #store iridium buffer and other important data to sfr
        pass



    def integrate_charge(self):
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
        :return: list of component failures
        """
        result = []
        for device in self.sfr.devices:
            # TODO: Implement functional for all devices
            # if the device is on and not functional
            if self.sfr.devices[device] is not None and not self.sfr.devices[device].functional:
                result.append(device)
        return result

    def turn_on_component(self, component: str):
        self.sfr.devices[component] = self.component_to_object[component](self.sfr)  # registers component as on by setting component status in sfr to object instead of None
        self.sfr.eps.commands["Pin On"](component)  # turns on component
        if component in self.component_to_serial:  # see if component has a serial converter to open
            serial_converter = self.component_to_serial[component]  # gets serial converter name of component
            self.sfr.eps.commands["Pin On"](serial_converter)  # turns on serial converter
            self.sfr.serial_converters[serial_converter] = True  # sets serial converter status to True (on)

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    def turn_off_component(self, component: str):
        #TODO: Make sure to copy iridium command buffer to sfr to avoid wiping commands when switching modes
        self.sfr.devices[component] = None  # sets device object in sfr to None instead of object
        self.sfr.eps.commands["Pin Off"](component)  # turns component off
        if component in self.component_to_serial:  # see if component has a serial converter to close
            serial_converter = self.component_to_serial[component]  # get serial converter name for component
            self.sfr.eps.commands["Pin Off"](serial_converter)  # turn off serial converter
            self.sfr.serial_converters[serial_converter] = False  # sets serial converter status to False (off)

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    def turn_all_on(self):
        for key in self.sfr.devices:
            if not self.sfr.devices[key]:  # if device in sfr.devices returns false (device is off)
                self.turn_on_component(key)  # turn device and serial converter on if applicable

    def turn_all_off(self):
        # TODO: Store iridium buffer into sfr
        for device in self.sfr.devices:  # device is key (str) of each component
            if self.sfr.devices[device]:  # if device in sfr.devices returns true (device is on)
                self.turn_off_component(device)  # turn off device and serial converter if applicable
