import time
from Drivers.eps import EPS
from Drivers.battery import Battery
from Drivers.bno055 import IMU_I2C
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.outreach.outreach import Outreach
from MainControlLoop.Mode.repeater import Repeater
from MainControlLoop.Mode.recovery import Recovery
from lib.analytics import Analytics
from lib.command_executor import CommandExecutor
from lib.log import CSVLog, JSONLog, PKLLog, NonWritableCSV
from lib.log import Logger
from lib.exceptions import wrap_errors, LogicalError
from Drivers.aprs import APRS
from Drivers.iridium import Iridium
from Drivers.antenna_deployer import AntennaDeployer
from Drivers.transmission_packet import UnsolicitedString


class Vars:
    """
    Loggable fields of sfr
    """
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        All variables which are logged and loaded
        NOTE: PLEASE UPDATE TO_DICT IF YOU ADD AN SFR VARS FIELD
        :param sfr: sfr object
        :type sfr: :class: 'MainControlLoop.lib.registry.StateFieldRegistry'
        """
        self.ANTENNA_DEPLOYED = False
        # Integral estimate of remaining battery capacity
        self.BATTERY_CAPACITY_INT = sfr.analytics.volt_to_charge(sfr.battery.telemetry["VBAT"]())
        self.FAILURES = []
        self.LAST_DAYLIGHT_ENTRY = time.time() - 45 * 60 if (sun := sfr.sun_detected()) else time.time()
        self.LAST_ECLIPSE_ENTRY = time.time() if sun else time.time() - 45 * 60
        self.ORBITAL_PERIOD = sfr.analytics.calc_orbital_period()
        # Switch to charging mode if battery capacity (J) dips below threshold. 30% of max capacity
        self.LOWER_THRESHOLD = 133732.8 * .3
        self.UPPER_THRESHOLD = 133732.8 * .8
        self.PRIMARY_RADIO = "Iridium"  # Primary radio to use for communications
        self.SIGNAL_STRENGTH_MEAN = -1.0  # Science mode result
        self.SIGNAL_STRENGTH_VARIABILITY = -1.0  # Science mode result
        self.OUTREACH_MAX_CALCULATION_TIME = 0.1  # max calculation time for minimax calculations in outreach (seconds)
        self.MODE_LOCK = False  # Whether to lock mode switches
        self.LOCKED_ON_DEVICES = set()  # set of string names of devices locked in the on state
        self.LOCKED_OFF_DEVICES = set()  # set of string names of devices locked in the off state
        self.CONTACT_ESTABLISHED = False
        self.ENABLE_SAFE_MODE = False
        self.transmit_buffer = []
        self.command_buffer = []
        self.outreach_buffer = []
        self.START_TIME = time.time()
        self.LAST_COMMAND_RUN = time.time()
        self.LAST_MODE_SWITCH = time.time()
        self.LAST_STARTUP = time.time()
        self.LAST_IRIDIUM_RECEIVED = time.time()
        self.PACKET_AGE_LIMIT = 3600*24*7  # One week
        self.DETUMBLE_THRESHOLD = 10

    @wrap_errors(LogicalError)
    def to_dict(self) -> dict:
        """
        Converts vars to dictionary with encoded values
        Encoded values must be integers or floats!!!
        :return: dictionary with encoded values
        :rtype: dict
        """
        return {
            "ANTENNA_DEPLOYED": int(self.ANTENNA_DEPLOYED),
            "BATTERY_CAPACITY_INT": self.BATTERY_CAPACITY_INT,
            "FAILURES": sum([1 << StateFieldRegistry.COMPONENTS.index(i) for i in self.FAILURES]),
            "LAST_DAYLIGHT_ENTRY_0": int(self.LAST_DAYLIGHT_ENTRY / 100000) * 100000,
            "LAST_DAYLIGHT_ENTRY_1": int(self.LAST_DAYLIGHT_ENTRY % 100000),
            "LAST_ECLIPSE_ENTRY_0": int(self.LAST_ECLIPSE_ENTRY / 100000) * 100000,
            "LAST_ECLIPSE_ENTRY_1": int(self.LAST_ECLIPSE_ENTRY % 100000),
            "ORBITAL_PERIOD": self.ORBITAL_PERIOD,
            "LOWER_THRESHOLD": self.LOWER_THRESHOLD,
            "UPPER_THRESHOLD": self.UPPER_THRESHOLD,
            "PRIMARY_RADIO": StateFieldRegistry.COMPONENTS.index(self.PRIMARY_RADIO),
            "SIGNAL_STRENGTH_MEAN": self.SIGNAL_STRENGTH_MEAN,
            "SIGNAL_STRENGTH_VARIABILITY": self.SIGNAL_STRENGTH_VARIABILITY,
            "OUTREACH_MAX_CALCULATION_TIME": self.OUTREACH_MAX_CALCULATION_TIME,
            "MODE_LOCK": int(self.MODE_LOCK),
            "LOCKED_ON_DEVICES": sum([1 << index for index in range(len(StateFieldRegistry.COMPONENTS))
                                      if StateFieldRegistry.COMPONENTS[index] in self.LOCKED_ON_DEVICES]),
            # binary sequence where each bit corresponds to a device (1 = locked on, 0 = not locked on)
            "LOCKED_OFF_DEVICES": sum([1 << index for index in range(len(StateFieldRegistry.COMPONENTS))
                                       if StateFieldRegistry.COMPONENTS[index] in self.LOCKED_OFF_DEVICES]),
            "CONTACT_ESTABLISHED": int(self.CONTACT_ESTABLISHED),
            "ENABLE_SAFE_MODE": int(self.ENABLE_SAFE_MODE),
            "START_TIME_0": int(self.START_TIME / 100000) * 100000,
            "START_TIME_1": int(self.START_TIME % 100000),
            "LAST_COMMAND_RUN_0": int(self.LAST_COMMAND_RUN / 100000) * 100000,
            "LAST_COMMAND_RUN_1": int(self.LAST_COMMAND_RUN % 100000),
            "LAST_MODE_SWITCH_0": int(self.LAST_MODE_SWITCH / 100000) * 100000,
            "LAST_MODE_SWITCH_1": int(self.LAST_MODE_SWITCH % 100000),
            "LAST_IRIDIUM_RECEIVED_0": int(self.LAST_IRIDIUM_RECEIVED / 100000) * 100000,
            "LAST_IRIDIUM_RECEIVED_1": int(self.LAST_IRIDIUM_RECEIVED % 100000),
            "PACKET_AGE_LIMIT": int(self.PACKET_AGE_LIMIT),
            "DETUMBLE_THRESHOLD": self.DETUMBLE_THRESHOLD,
        }

    @wrap_errors(LogicalError)
    def encode(self) -> list:
        """
        Specifically for transmission of all sfr fields
        :return: encoded values of vars
        :rtype: list
        """
        return list(self.to_dict().values())


class StateFieldRegistry:
    """
    Collection of loggable fields, constants, functions, and devices
    Accessible to every element of pfs
    """
    # Constants
    PDMS = ["0x01", "0x02", "0x03", "0x04", "0x05", "0x06", "0x07", "0x08", "0x09", "0x0A"]
    PANELS = ["bcr1", "bcr2", "bcr3"]
    COMPONENTS = [
        "APRS",
        "Iridium",
        "IMU",
        "Antenna Deployer",
        "EPS",
        "RTC",
        "UART-RS232",  # Iridium Serial Converter
        "USB-UART"  # APRS Serial Converter
    ]
    UNSUCCESSFUL_SEND_TIME_CUTOFF = 60 * 60 * 24  # if it has been unsuccessfully trying to send messages
    # via iridium for this amount of time, switch primary to APRS
    UNSUCCESSFUL_RECEIVE_TIME_CUTOFF = 60 * 60 * 24 * 7  # if no message is received on iridium for this
    # amount of time, it will switch primary radio to APRS
    # Volt backup thresholds, further on than the capacity thresholds
    VOLT_UPPER_THRESHOLD = 8.0
    VOLT_LOWER_THRESHOLD = 7.3

    @wrap_errors(LogicalError)
    def __init__(self):
        """
        Variables common across our pfs
        Vars in the "vars" object get logged
        """
        self.logs = {
            "sfr": PKLLog("./lib/data/state_field_log.pkl"),
            "sfr_readable": JSONLog("./lib/data/state_field_log.json"),
            "power": CSVLog("./lib/data/pwr_draw_log.csv", ["ts0", "ts1", "buspower"] + self.PDMS),
            "solar": CSVLog("./lib/data/solar_generation_log.csv", ["ts0", "ts1"] + self.PANELS),
            "voltage_energy": NonWritableCSV("./lib/data/volt-energy-map.csv", ["voltage", "energy"]),
            "orbits": CSVLog("./lib/data/orbit_log.csv", ["ts0", "ts1", "phase"]),
            "iridium": CSVLog("./lib/data/iridium_data.csv",
                              ["ts0", "ts1", "latitude", "longitude", "altitude", "signal"]),
            "imu": CSVLog("./lib/data/imu_data.csv", ["ts0", "ts1", "xgyro", "ygyro", "zgyro"]),
            "command": CSVLog("./lib/data/command_log.csv",
                              ["ts0", "ts1", "radio", "command", "arg", "registry", "msn", "result"]),
            "transmission": CSVLog("./lib/data/transmission_log.csv", ["ts0", "ts1", "radio", "size"]),
        }

        self.eps = EPS(self)  # EPS never turns off
        self.battery = Battery(self)
        self.analytics = Analytics(self)
        self.command_executor = CommandExecutor(self)
        self.logger = Logger(self)
        self.MODE = None

        self.devices = {
            "Iridium": None,
            "APRS": None,
            "Antenna Deployer": None,
            "IMU": None
        }
        self.serial_converters = {  # False if off, True if on
            "UART-RS232": False,  # Iridium Serial Converter
            "USB-UART": False  # Alternate APRS Serial Converter
        }
        self.modes_list = {
            "Startup": Startup,
            "Charging": Charging,
            "Science": Science,
            "Outreach": Outreach,
            "Repeater": Repeater,
            "Recovery": Recovery
        }

        self.component_to_class = {  # returns class from component name
            "Iridium": Iridium,
            "APRS": APRS,
            "IMU": IMU_I2C,
            "Antenna Deployer": AntennaDeployer
        }
        self.vars = self.load()

    @wrap_errors(LogicalError)
    def sleep(self, t: int) -> None:
        """
        Use this when you need to time.sleep for longer than 4 minutes, to prevent EPS reset
        Runs in increments of 60 seconds
        :param t: number of seconds to sleep
        :type t: int
        """
        begin = time.perf_counter()
        while time.perf_counter() - begin < t:
            self.eps.commands["Reset Watchdog"]()
            time.sleep(60)

    @wrap_errors(LogicalError)
    def check_upper_threshold(self) -> bool:
        """
        Checks upper battery threshold for switching modes
        Syncs voltage to integrated charge if necessary
        :return: whether switch is required
        :rtype: bool
        """
        if self.battery.telemetry["VBAT"]() > self.VOLT_UPPER_THRESHOLD:
            self.vars.BATTERY_CAPACITY_INT = self.analytics.volt_to_charge(self.battery.telemetry["VBAT"]())
            # Sync up the battery charge integration to voltage
            return True
        if self.vars.BATTERY_CAPACITY_INT > self.vars.UPPER_THRESHOLD:
            return True
        return False

    @wrap_errors(LogicalError)
    def check_lower_threshold(self) -> bool:
        """
        Checks upper battery threshold for switching modes
        Syncs voltage to integrated charge if necessary
        :return: whether switch is required
        :rtype: bool
        """
        if self.battery.telemetry["VBAT"]() < self.VOLT_LOWER_THRESHOLD:
            self.vars.BATTERY_CAPACITY_INT = self.analytics.volt_to_charge(self.battery.telemetry["VBAT"]())
            # Sync up the battery charge integration to voltage
            return True
        if self.vars.BATTERY_CAPACITY_INT < self.vars.LOWER_THRESHOLD:
            return True
        return False

    @wrap_errors(LogicalError)
    def load(self) -> Vars:
        """
        Load sfr fields from log
        :return: loaded fields
        :rtype: :class: 'lib.registry.Vars'
        """
        defaults = Vars(self)  # Generate default sfr vars
        fields = self.logs["sfr"].read()  # Load fields
        if not fields:  # If log doesn't exist
            return defaults  # Return defaults
        if fields.to_dict().keys() != defaults.to_dict().keys():  # If the log is the wrong version
            return defaults  # Return defaults
        return fields  # Otherwise return loaded vars

    @wrap_errors(LogicalError)
    def dump(self) -> None:
        """
        Dump values of all state fields into state_field_log and readable log
        """
        self.logs["sfr"].write(self.vars)
        self.logs["sfr_readable"].write(self.vars.to_dict())

    @wrap_errors(LogicalError)
    def enter_sunlight(self) -> None:
        """
        Update LAST_DAYLIGHT_ENTRY and log new data
        """
        self.vars.LAST_DAYLIGHT_ENTRY = time.time()
        self.logs["orbits"].write({  # Append data to log
            "ts0": self.vars.LAST_DAYLIGHT_ENTRY // 100000 * 100000,
            "ts1": int(self.vars.LAST_DAYLIGHT_ENTRY % 100000),
            "phase": "daylight",
        })

    @wrap_errors(LogicalError)
    def enter_eclipse(self) -> None:
        """
        Update LAST_ECLIPSE_ENTRY and log new data
        """
        self.vars.LAST_ECLIPSE_ENTRY = time.time()
        self.logs["orbits"].write({  # Append data to log
            "ts0": self.vars.LAST_ECLIPSE_ENTRY // 100000 * 100000,
            "ts1": int(self.vars.LAST_ECLIPSE_ENTRY % 100000),
            "phase": "eclipse",
        })

    @wrap_errors(LogicalError)
    def log_iridium(self, location: tuple, signal: int) -> None:
        """
        Logs iridium data
        :param location: current geolocation
        :type location: tuple
        :param signal: iridium signal strength
        :type signal: int
        """
        self.logs["iridium"].write({
            "ts0": (t := time.time()) // 100000 * 100000,
            "ts1": int(t % 100000),
            "latitude": location[0],
            "longitude": location[1],
            "altitude": location[2],
            "signal": signal,
        })

    @wrap_errors(LogicalError)
    def recent_power(self) -> list:
        """
        Returns list of buspower and power draws for all pdms
        :return: [buspower, 0x01, 0x02... 0x0A]
        :rtype: list
        """
        if (df := self.logs["power"].read()).shape[0] == 0:
            return [self.eps.bus_power()] + self.eps.raw_pdm_draw()[1]
        # Get last row, only include columns which store information about power
        return df[["buspower"] + self.PDMS].iloc[-1].tolist()

    @wrap_errors(LogicalError)
    def recent_gen(self) -> list:
        """
        Returns list of input power from all bcrs
        :return: [bcr1, bcr2, bcr3]
        :rtype: list
        """
        if (df := self.logs["solar"].read()).shape[0] == 0:
            return self.eps.raw_solar_gen()
        # Get last row, exclude timestamp columns
        return df[self.PANELS].iloc[-1].tolist()

    @wrap_errors(LogicalError)
    def sun_detected(self) -> bool:
        """
        Checks if sun is detected (JANK IMPLEMENTATION BECAUSE WE DON'T HAVE SUN SENSORS, VERY UNRELIABLE)
        :return: whether sun is detected
        :rtype: bool
        """
        solar = sum(self.eps.raw_solar_gen())
        if solar > self.eps.SUN_DETECTION_THRESHOLD:  # Threshold of 1W
            return True
        # If EPS is at end of charge mode, MPPT will be disabled, making solar power an inaccurate representation of
        # actual sunlight
        if self.battery.telemetry["VBAT"]() > self.eps.V_EOC:
            pcharge = self.battery.charging_power()
            # If the battery is charging, or is discharging at a rate below an acceptable threshold (i.e.,
            # the satellite is in a power hungry mode)
            if pcharge > (-1 * self.eps.total_power(2)[0]):
                return True
        return False

    @wrap_errors(LogicalError)
    def clear_logs(self) -> None:
        """
        WARNING: CLEARS ALL LOGGED DATA, ONLY USE FOR TESTING/DEBUG
        """
        for i in self.logs.keys():
            self.logs[i].clear()

    @wrap_errors(LogicalError)
    def reset(self) -> None:
        """
        Resets state field registry vars log
        """
        self.logs["sfr"].write(Vars())  # Write default log

    @wrap_errors(LogicalError)
    def switch_mode(self, mode: Mode) -> bool:
        """
        Switches current mode if new mode is possible based on locked devices, returns whether mode was switched
        :param mode: mode object to switch to
        :type mode: Mode
        :return: whether the mode switch was executed
        :rtype: bool
        """
        if not mode.start():
            return False
        self.MODE.terminate_mode()
        self.MODE = mode
        return True

    @wrap_errors(LogicalError)
    def power_on(self, component: str) -> None:
        """
        Turns on component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.
        :param component: component to turn on
        :type component: str
        """
        if self.devices[component] is not None:
            return  # if component is already on, stop method from running further
        if component in self.vars.LOCKED_OFF_DEVICES:
            return  # if component is locked off, stop method from running further

        self.eps.commands["Pin On"](component)  # turns on component
        for i in self.component_to_class[component].SERIAL_CONVERTERS:
            self.eps.commands["Pin On"](i)  # Turns on all serial converters for this component
        time.sleep(.5)  # Wait for device to boot
        # registers component as on by setting devices value to instantiated object
        self.devices[component] = self.component_to_class[component](self)

    @wrap_errors(LogicalError)
    def power_off(self, component: str) -> None:
        """
        Turns off component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.
        :param component: component to turn off
        :type component: str
        """
        if self.devices[component] is None:  # if component is off, stop method from running further.
            return
        if component in self.vars.LOCKED_ON_DEVICES:  # if component is locked on, stop method from running further
            return

        self.devices[component].terminate()
        self.devices[component] = None  # removes from dict
        self.eps.commands["Pin Off"](component)  # turns off component
        for i in self.component_to_class[component].SERIAL_CONVERTERS:
            self.eps.commands["Pin Off"](i)  # Switch off serial converters for this component

    @wrap_errors(LogicalError)
    def reboot(self, component: str) -> None:
        """
        Powers a given component on and off again
        :param component: component to reboot
        :type component: str
        """
        self.power_off(component)
        time.sleep(5)
        self.power_on(component)
        time.sleep(10)

    @wrap_errors(LogicalError)
    def all_on(self, exceptions=None) -> None:
        """
        Turns all components on automatically, except for Antenna Deployer.
        Calls power_on for every key in self.devices except for those in exceptions parameter
        :param exceptions: components to not turn on, default is ["Antenna Deployer, IMU"]
        :type exceptions: list
        """
        exceptions = (exceptions or []) + ["Antenna Deployer", "IMU"]  # Set to default list

        for key in self.devices:
            if not self.devices[key] and key not in exceptions:  # if device is off and not in exceptions
                self.power_on(key)  # turn on device and serial converter if applicable

    @wrap_errors(LogicalError)
    def all_off(self, exceptions=None, override_default_exceptions=False) -> None:
        """
        Turns all components off automatically, except for Antenna Deployer.
        Calls power_off for every key in self.devices. Except for those in exceptions parameter
        :param exceptions: (list) components to not turn off, default is ["Antenna Deployer, IMU"]
        :param override_default_exceptions: (bool) whether or not to use default exceptions
        :return: None
        """
        exceptions = (exceptions or []) + (["Antenna Deployer", "IMU"] if not override_default_exceptions else [])

        for key in self.devices:
            if self.devices[key] and key not in exceptions:  # if device  is on and not in exceptions
                self.power_off(key)  # turn off device and serial converter if applicable

    @wrap_errors(LogicalError)
    def set_primary_radio(self, new_radio: str, turn_off_old=False) -> bool:
        """
        Takes care of switching sfr PRIMARY_RADIO field:
        instantiates primary radio if necessary, kills the previous radio if requested
        :param new_radio: string name of new radio (i.e. "APRS" or "Iridium")
        :type new_radio: str
        :param turn_off_old: whether or not to turn off the old radio if it is being switched
        :type turn_off_old: bool
        :return: Whether primary radio was switched
            True if the primary radio could be set as specified (or it already was that one).
            False only if it is locked off, or it's APRS and antenna not deployed
        :rtype: bool
        """
        # If this is not a different radio or the new radio is locked off, don't run further
        if new_radio == self.vars.PRIMARY_RADIO or new_radio in self.vars.LOCKED_OFF_DEVICES:
            return False
        # don't switch to APRS as primary if the antenna hasn't deployed
        if new_radio == "APRS" and not self.vars.ANTENNA_DEPLOYED:
            return False
        if turn_off_old:
            self.power_off(self.vars.PRIMARY_RADIO)
        # Switch radio
        self.vars.PRIMARY_RADIO = new_radio
        self.power_on(new_radio)
        # transmit update to groundstation
        self.command_executor.transmit(UnsolicitedString(return_data=f"Switched to {self.vars.PRIMARY_RADIO}"))
        return True

    @wrap_errors(LogicalError)
    def lock_device_on(self, component: str, force=False) -> bool:
        """
        Takes care of logic for locking on devices
        :param component: name of device to lock on
        :type component: str
        :param force: if true, this will overwrite any previous locks on this device
        :type force: bool
        :return: whether the device was able to be locked on
            (only false if force == False and it was previously in LOCKED_OFF_DEVICES)
        :rtype: bool
        """
        if component in self.vars.LOCKED_ON_DEVICES:
            return True  # if it's already locked on
        if component in self.vars.LOCKED_OFF_DEVICES:
            if not force:  # If we're not allowed to overwrite, return
                return False
            self.vars.LOCKED_OFF_DEVICES.remove(component)  # Unlock device off
        # Lock device
        self.vars.LOCKED_ON_DEVICES.add(component)
        self.power_on(component)  # Power on device
        return True

    @wrap_errors(LogicalError)
    def lock_device_off(self, component: str, force=False) -> bool:
        """
        Takes care of logic for locking off devices
        :param component: name of device to lock off
        :type component: str
        :param force: if true, this will overwrite any previous locks on this device
        :type force: bool
        :return: whether the device was able to be locked off
            (example: false if force == False and it was previously in LOCKED_ON_DEVICES)
        :rtype: bool
        """
        # won't allow both radios to be locked off
        if "Iridium" in (l := list(self.vars.LOCKED_OFF_DEVICES) + [component]) and "APRS" in l:
            return False
        if component in self.vars.LOCKED_OFF_DEVICES:
            return True  # if it's already locked off
        if component in self.vars.LOCKED_ON_DEVICES:  # if it was locked on before
            if not force:  # If we're not allowed to overwrite, return
                return False
            self.vars.LOCKED_ON_DEVICES.remove(component)  # Otherwise remove from LOCKED_ON_DEVICES
        # at this point, we know this is a legal action
        self.vars.LOCKED_OFF_DEVICES.add(component)  # Add device to locked devices
        self.power_off(component)  # Power off device
        return True

    def unlock_device(self, device: str) -> bool:
        """
        Unlocks device
        :param device: name of device to unlock
        :type device: str
        :return: True if something had to be changed, False if it was not previously locked
        :rtype: bool
        """
        if device in self.vars.LOCKED_ON_DEVICES:  # if it was locked on
            self.vars.LOCKED_ON_DEVICES.remove(device)
            return True
        if device in self.vars.LOCKED_OFF_DEVICES:  # if it was locked off
            self.vars.LOCKED_OFF_DEVICES.remove(device)
            return True
        return False
