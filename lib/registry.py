import time
from Drivers.eps import EPS
from Drivers.battery import Battery
from Drivers.bno055 import IMU_I2C
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.outreach.outreach import Outreach
from MainControlLoop.Mode.repeater import Repeater
from MainControlLoop.Mode.recovery import Recovery
from lib.analytics import Analytics
from lib.command_executor import CommandExecutor
from lib.log import CSVLog, JSONLog, PKLLog
from lib.log import Logger
from lib.exceptions import wrap_errors, LogicalError
from Drivers.aprs import APRS
from Drivers.iridium import Iridium
from Drivers.antenna_deployer import AntennaDeployer
from Drivers.transmission_packet import UnsolicitedString


class Vars:
    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        self.ANTENNA_DEPLOYED = False
        # Integral estimate of remaining battery capacity
        self.BATTERY_CAPACITY_INT = sfr.analytics.volt_to_charge(sfr.battery.telemetry["VBAT"]())
        self.FAILURES = []
        self.LAST_DAYLIGHT_ENTRY = time.time() - 45 * 60 if (sun := sfr.sun_detected()) else time.time()
        self.LAST_ECLIPSE_ENTRY = time.time() if sun else time.time() - 45 * 60
        self.ORBITAL_PERIOD = sfr.analytics.calc_orbital_period()  # TODO: Don't be an idiot, this won't work
        # Switch to charging mode if battery capacity (J) dips below threshold. 30% of max capacity
        self.LOWER_THRESHOLD = 133732.8 * 0.3
        self.UPPER_THRESHOLD = 133732.8 * 50  # TODO: USE REAL VALUE
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
        self.PACKET_AGE_LIMIT = 999999 # TODO: USE REAL VALUE

    @wrap_errors(LogicalError)
    def encode(self):
        """
        :return: Dictionary containing the values of the SFR and vars
        """
        return [
            int(self.ANTENNA_DEPLOYED),
            self.BATTERY_CAPACITY_INT,
            sum([1 << StateFieldRegistry.COMPONENTS.index(i) for i in self.FAILURES]),
            int(self.LAST_DAYLIGHT_ENTRY / 100000) * 100000,
            int(self.LAST_DAYLIGHT_ENTRY % 100000),
            int(self.LAST_ECLIPSE_ENTRY / 100000) * 100000,
            int(self.LAST_ECLIPSE_ENTRY % 100000),
            self.ORBITAL_PERIOD,
            self.LOWER_THRESHOLD,
            self.UPPER_THRESHOLD,
            StateFieldRegistry.COMPONENTS.index(self.PRIMARY_RADIO),
            self.SIGNAL_STRENGTH_VARIABILITY,
            int(self.MODE_LOCK),
            # sum([1 << StateFieldRegistry.COMPONENTS.index(i) for i in list(self.LOCKED_DEVICES.keys())
            #      if self.LOCKED_DEVICES[i]]),  # TODO: change encoding for locking on/off
            sum([1 << index for index in range(len(StateFieldRegistry.COMPONENTS))
                 if StateFieldRegistry.COMPONENTS[index] in self.LOCKED_ON_DEVICES]),
            # binary sequence where each bit corresponds to a device (1 = locked on, 0 = not locked on)
            sum([1 << index for index in range(len(StateFieldRegistry.COMPONENTS))
                 if StateFieldRegistry.COMPONENTS[index] in self.LOCKED_OFF_DEVICES]),
            # binary sequence where each bit corresponds to a device (1 = locked off, 0 = not locked off)
            int(self.CONTACT_ESTABLISHED),
            int(self.START_TIME / 100000) * 100000,
            int(self.START_TIME % 100000),
            int(self.LAST_COMMAND_RUN / 100000) * 100000,
            int(self.LAST_COMMAND_RUN % 100000),
            int(self.LAST_MODE_SWITCH / 100000) * 100000,
            int(self.LAST_MODE_SWITCH % 100000)
        ]

    @wrap_errors(LogicalError)
    def to_dict(self):
        """
        Converts vars to dictionary with encoded values
        """
        encoded = self.encode()
        result = {}
        for i in vars(self):
            if not i.startswith("__") and i.isupper():
                result[i] = encoded[0]  # encoded.pop(0)
        return result


class StateFieldRegistry:
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
        "SPI-UART",  # APRS Serial Converter
        "USB-UART"
    ]
    UNSUCCESSFUL_SEND_TIME_CUTOFF = 60 * 60 * 24  # if it has been unsuccessfully trying to send messages
    # via iridium for this amount of time, switch primary to APRS
    UNSUCCESSFUL_RECEIVE_TIME_CUTOFF = 60 * 60 * 24 * 7  # if no message is received on iridium for this
    # amount of time, it will switch primary radio to APRS
    # Volt backup thresholds, further on than the capacity thresholds
    VOLT_UPPER_THRESHOLD = 9.0  # TODO: update this value to something
    VOLT_LOWER_THRESHOLD = 7.3  # TODO: update this value to something

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
            "voltage_energy": CSVLog("./lib/data/volt-energy-map.csv", ["voltage", "energy"]),
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
    def sleep(self, t):
        """
        Use this when you need to time.sleep for longer than 4 minutes, to prevent EPS reset
        Runs in increments of 60 seconds
        :param t: (int) number of seconds to sleep
        """
        begin = time.perf_counter()
        while time.perf_counter() - begin < t:
            self.eps.commands["Reset Watchdog"]()
            time.sleep(60)
    
    @wrap_errors(LogicalError)
    def check_upper_threshold(self):
        """
        Checks upper battery threshold for switching modes
        Syncs voltage to integrated charge if necessary
        :return: (bool) whether switch is required
        """
        if self.battery.telemetry["VBAT"]() > self.VOLT_UPPER_THRESHOLD:
            self.vars.BATTERY_CAPACITY_INT = self.analytics.volt_to_charge(self.battery.telemetry["VBAT"]()) 
            # Sync up the battery charge integration to voltage
            return True
        if self.vars.BATTERY_CAPACITY_INT > self.vars.UPPER_THRESHOLD:
            print("Exiting charging, BATTERY_CAPACITY_INT", self.vars.BATTERY_CAPACITY_INT)
            return True
        return False

    @wrap_errors(LogicalError)
    def check_lower_threshold(self):
        """
        Checks upper battery threshold for switching modes
        Syncs voltage to integrated charge if necessary
        :return: (bool) whether switch is required
        """
        print(f"Checking lower threshold, vbat {self.battery.telemetry['VBAT']()} capacity {self.vars.BATTERY_CAPACITY_INT}")
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
        :return: (Registry) loaded registry
        """
        defaults = Vars(self)
        return defaults  # TODO: DEBUG
        try:
            fields = self.logs["sfr"].read()
            if list(fields.to_dict().keys()) == list(defaults.to_dict().keys()):
                print("Loading sfr from log...")
                return fields
            print("Invalid log, loading default sfr...")
            return defaults
        except LogicalError as e:
            if type(e.exception) == FileNotFoundError:
                print("Log missing, loading default sfr...")
                return defaults
            raise

    @wrap_errors(LogicalError)
    def dump(self) -> None:
        """
        Dump values of all state fields into state_field_log and readable log
        """
        self.logs["sfr"].write(self.vars)
        # self.logs["sfr_readable"].write(self.vars.to_dict())

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
    def log_iridium(self, location: tuple, signal) -> None:
        """
        Logs iridium data
        :param location: current geolocation
        :param signal: iridium signal strength
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
        :return: (list) [buspower, 0x01, 0x02... 0x0A]
        """
        if len(df := self.logs["power"].read()) == 0:
            return [self.eps.bus_power()] + self.eps.raw_pdm_draw()[1]
        # Get last row, only include columns which store information about power
        return df[["buspower"] + self.PDMS].iloc[-1].tolist()

    @wrap_errors(LogicalError)
    def recent_gen(self) -> list:
        """
        Returns list of input power from all bcrs
        :return: (list) [bcr1, bcr2, bcr3]
        """
        if len(df := self.logs["solar"].read()) == 0:
            return self.eps.raw_solar_gen()
        # Get last row, exclude timestamp columns
        return df[self.PANELS].iloc[-1].tolist()

    @wrap_errors(LogicalError)
    def sun_detected(self) -> bool:
        """
        Checks if sun is detected
        :return: (bool)
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
    def clear_logs(self):
        """
        WARNING: CLEARS ALL LOGGED DATA, ONLY USE FOR TESTING/DEBUG
        """
        for i in self.logs.keys():
            if i != "voltage_energy":
                self.logs[i].clear()
        print("Logs cleared")

    @wrap_errors(LogicalError)
    def reset(self):
        """
        Resets state field registry log
        """
        self.logs["sfr"].write(Vars())  # Write default log

    @wrap_errors(LogicalError)
    def power_on(self, component: str) -> None:
        """
        Turns on component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.
        :param component: (str) component to turn on
        """
        if self.devices[component] is not None:
            return  # if component is already on, stop method from running further
        if component in self.vars.LOCKED_OFF_DEVICES:
            return  # if component is locked off, stop method from running further

        self.eps.commands["Pin On"](component)  # turns on component
        for current_converter in self.component_to_class[component].SERIAL_CONVERTERS:
            self.eps.commands["Pin On"](current_converter)
        time.sleep(.5)
        self.devices[component] = self.component_to_class[component](self)  # registers component as on by setting
        self.devices[component] = self.component_to_class[component](self)  # registers component as on by setting

    @wrap_errors(LogicalError)
    def power_off(self, component: str) -> None:
        """
        Turns off component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.
        :param component: (str) component to turn off
        """
        if self.devices[component] is None:  # if component is off, stop method from running further.
            return None
        if component in self.vars.LOCKED_ON_DEVICES:  # if component is locked on, stop method from running further
            return None

        self.devices[component].terminate()
        self.devices[component] = None  # removes from dict
        self.eps.commands["Pin Off"](component)  # turns off component
        for current_converter in self.component_to_class[component].SERIAL_CONVERTERS:
            self.eps.commands["Pin Off"](current_converter)

    @wrap_errors(LogicalError)
    def reboot(self, component: str) -> None:
        """
        Powers a given component on and off again
        :param component: (str) component to rebood
        :return: None
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
        :param exceptions: (list) components to not turn on, default is ["Antenna Deployer, IMU"]
        :return: None
        """
        if exceptions is None:  # If no argument provided
            exceptions = ["Antenna Deployer", "IMU"]  # Set to default list

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
        exceptions = exceptions or []
        if not override_default_exceptions:
            exceptions += ["Antenna Deployer", "IMU"]

        for key in self.devices:
            if self.devices[key] and key not in exceptions:  # if device  is on and not in exceptions
                self.power_off(key)  # turn off device and serial converter if applicable

    @wrap_errors(LogicalError)
    def set_primary_radio(self, new_radio: str, turn_off_old=False):
        """
        Takes care of switching sfr PRIMARY_RADIO field:
        instantiates primary radio if necessary, kills the previous radio if requested
        :param new_radio: (str) string name of new radio (i.e. "APRS" or "Iridium")
        :param turn_off_old: (bool) whether or not to turn off the old radio if it is being switched
        :return: True if the primary radio could be set as specified (or it already was that one).
            False only if it is locked off, or it's APRS and antenna not deployed
        """
        previous_radio = self.vars.PRIMARY_RADIO
        if new_radio != previous_radio:  # if it's a new radio
            if new_radio in self.vars.LOCKED_OFF_DEVICES:  # if it's locked off
                return False
            if new_radio == "APRS" and not self.vars.ANTENNA_DEPLOYED:  # don't switch to APRS as primary if the antenna haven't deployed
                return False
            if turn_off_old:
                self.power_off(previous_radio)
            self.vars.PRIMARY_RADIO = new_radio
            if self.devices[new_radio] is None:  # initialize it
                self.power_on(new_radio)
            # transmit update to groundstation
            self.vars.LAST_IRIDIUM_RECEIVED = time.time()
            unsolicited_packet = UnsolicitedString(return_data=f"Switched to {self.vars.PRIMARY_RADIO}")
            self.command_executor.transmit(unsolicited_packet)
        return True

    @wrap_errors(LogicalError)
    def lock_device_on(self, component: str, force=False):
        """
        Takes care of logic for locking on devices
        :param component: (str) name of device to lock on
        :param force: (bool) if true, this will overwrite any previous locks on this device
        :return: whether the device was able to be locked on (only false if force == False and it was previously in LOCKED_OFF_DEVICES)
        """
        if component in self.vars.LOCKED_ON_DEVICES:
            return True  # if it's already locked on
        if component in self.vars.LOCKED_OFF_DEVICES:  # if it was locked off before
            if not force:
                return False  # the device was locked off before, and this is not allowed to overwrite
            # else:
            self.vars.LOCKED_OFF_DEVICES.remove(component)
        # at this point, we know this is a legal action:
        self.vars.LOCKED_ON_DEVICES.add(component)
        if self.devices[component] is None:
            self.power_on(component)  # needs to be powered on
        return True

    @wrap_errors(LogicalError)
    def lock_device_off(self, component: str, force=False):
        """
        Takes care of logic for locking off devices
        :param component: (str) name of device to lock off
        :param force: (bool) if true, this will overwrite any previous locks on this device
        :return: whether the device was able to be locked off (example: false if force == False and it was previously in LOCKED_ON_DEVICES)
        """
        if component == "APRS" and "Iridium" in self.vars.LOCKED_OFF_DEVICES:  # won't allow both radios to be locked off
            return False
        if component == "Iridium" and "APRS" in self.vars.LOCKED_OFF_DEVICES:  # won't allow both radios to be locked off
            return False
        if component in self.vars.LOCKED_OFF_DEVICES:
            return True  # if it's already locked off
        if component in self.vars.LOCKED_ON_DEVICES:  # if it was locked on before
            if not force:
                return False  # the device was locked on before, and this is not allowed to overwrite
            # else:
            self.vars.LOCKED_ON_DEVICES.remove(component)
        # at this point, we know this is a legal action
        self.vars.LOCKED_OFF_DEVICES.add(component)
        if not (self.devices[component] is None):  # needs to be powered off
            self.power_off(component)
        self.devices[component] = None  # this is already handled in power_off, but this is making it explicit
        return True

    def unlock_device(self, device: str):
        """
        Unlocks device
        :param device: (str) name of device to unlock
        :return: (bool) True if something had to be changed, False if it was not previously locked
        """
        if device in self.vars.LOCKED_ON_DEVICES:  # if it was locked on
            self.vars.LOCKED_ON_DEVICES.remove(device)
            return True
        elif device in self.vars.LOCKED_OFF_DEVICES:  # if it was locked off
            self.vars.LOCKED_OFF_DEVICES.remove(device)
            return True
        else:
            return False
