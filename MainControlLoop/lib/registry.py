import time
import os
import pandas as pd
import numpy as np
import pickle, json
from MainControlLoop.Drivers.eps import EPS
from MainControlLoop.Drivers.battery import Battery
from MainControlLoop.Drivers.bno055 import IMU_I2C, IMU
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.outreach import Outreach
from MainControlLoop.Mode.repeater import Repeater
from MainControlLoop.lib.analytics import Analytics
from MainControlLoop.lib.command_executor import CommandExecutor
from MainControlLoop.lib.log import Logger
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError
from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.iridium import Iridium
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer


class StateFieldRegistry:
    modes_list = {
        "Startup": Startup,
        "Charging": Charging,
        "Science": Science,
        "Outreach": Outreach,
        "Repeater": Repeater,
    }
    component_to_serial = {  # in sfr so command_executor can switch serial_converter of APRS if needed.
        "Iridium": "UART-RS232",
        "APRS": "SPI-UART"
    }
    components = [
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

    component_to_class = {  # returns class from component name
        "Iridium": Iridium,
        "APRS": APRS,
        "IMU": IMU,
        "Antenna Deployer": AntennaDeployer
    }

    @wrap_errors(LogicalError)
    def __init__(self):
        """
        Variables common across our pfs
        Vars in the "vars" object get logged
        """
        self.log_path = "./MainControlLoop/lib/data/state_field_log.pkl"
        self.readable_log_path = "./MainControlLoop/lib/data/state_field_log.json"
        self.pwr_log_path = "./MainControlLoop/lib/data/pwr_draw_log.csv"
        self.solar_log_path = "./MainControlLoop/lib/data/solar_generation_log.csv"
        self.volt_energy_map_path = "./MainControlLoop/lib/data/volt-energy-map.csv"
        self.orbit_log_path = "./MainControlLoop/lib/data/orbit_log.csv"
        self.iridium_data_path = "./MainControlLoop/lib/data/iridium_data.csv"
        self.imu_log_path = "./MainControlLoop/lib/data/imu_data.csv"  # Scuffed implementation
        self.command_log_path = "./MainControlLoop/lib/data/command_log.csv"
        self.transmission_log_path = "./MainControlLoop/lib/data/transmission_log.csv"

        self.eps = EPS(self)  # EPS never turns off
        self.battery = Battery()
        self.imu = IMU_I2C(self)
        self.analytics = Analytics(self)
        self.command_executor = CommandExecutor(self)
        self.logger = Logger(self)

        # Data for power draw and solar generation logs
        self.pwr_draw_log_headers = pd.read_csv(self.pwr_log_path, header=0).columns
        self.solar_generation_log_headers = pd.read_csv(self.solar_log_path, header=0).columns
        self.voltage_energy_map = pd.read_csv(self.volt_energy_map_path)

        self.devices = {
            "Iridium": None,
            "APRS": None,
            "Antenna Deployer": None,
        }
        self.serial_converters = {  # False if off, True if on
            "UART-RS232": False,  # Iridium Serial Converter
            "SPI-UART": False,  # APRS Serial Converter
            "USB-UART": False  # Alternate APRS Serial Converter
        }
        self.vars = self.load()
        self.vars.LAST_STARTUP = time.time()

    class Registry:
        @wrap_errors(LogicalError)
        def __init__(self, battery, analytics):
            self.ANTENNA_DEPLOYED = False
            # Integral estimate of remaining battery capacity
            self.BATTERY_CAPACITY_INT = analytics.volt_to_charge(battery.telemetry["VBAT"]())
            self.FAILURES = []
            self.LAST_DAYLIGHT_ENTRY = time.time() - 45 * 60 if (sun := self.sun_detected()) else time.time()
            self.LAST_ECLIPSE_ENTRY = time.time() if sun else time.time() - 45 * 60
            self.ORBITAL_PERIOD = 90 * 60
            # Switch to charging mode if battery capacity (J) dips below threshold. 30% of max capacity
            self.LOWER_THRESHOLD = 133732.8 * 0.3
            self.UPPER_THRESHOLD = 999999  # TODO: USE REAL VALUE
            # self.MODE = Startup  # Stores mode class, mode is instantiated in mcl
            self.MODE = Science  # DEBUG!!!
            self.PRIMARY_RADIO = "Iridium"  # Primary radio to use for communications
            self.SIGNAL_STRENGTH_VARIABILITY = -1.0  # Science mode result
            self.MODE_LOCK = False  # Whether to lock mode switches
            self.LOCKED_DEVICES = {"Iridium": False, "APRS": False, "IMU": False, "Antenna Deployer": None}
            self.CONTACT_ESTABLISHED = False
            self.ENABLE_SAFE_MODE = False
            self.transmit_buffer = []
            self.command_buffer = []
            self.outreach_buffer = []
            self.START_TIME = time.time()
            self.LAST_COMMAND_RUN = time.time()
            self.LAST_MODE_SWITCH = time.time()
            self.LAST_STARTUP = 0

        @wrap_errors(LogicalError)
        def encode(self):
            return [
                int(self.ANTENNA_DEPLOYED),
                self.BATTERY_CAPACITY_INT,
                sum([1 << StateFieldRegistry.components.index(i) for i in self.FAILURES]),
                int(self.LAST_DAYLIGHT_ENTRY / 100000) * 100000,
                int(self.LAST_DAYLIGHT_ENTRY % 100000),
                int(self.LAST_ECLIPSE_ENTRY / 100000) * 100000,
                int(self.LAST_ECLIPSE_ENTRY % 100000),
                self.ORBITAL_PERIOD,
                self.LOWER_THRESHOLD,
                self.UPPER_THRESHOLD,
                list(StateFieldRegistry.modes_list.keys()).index(self.MODE.__name__),
                StateFieldRegistry.components.index(self.PRIMARY_RADIO),
                self.SIGNAL_STRENGTH_VARIABILITY,
                int(self.MODE_LOCK),
                sum([1 << StateFieldRegistry.components.index(i) for i in list(self.LOCKED_DEVICES.keys())
                     if self.LOCKED_DEVICES[i]]),
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

    @wrap_errors(LogicalError)
    def load(self) -> Registry:
        """
        Load sfr fields from log
        :return: (Registry) loaded registry
        """
        defaults = self.Registry(self.battery, self.analytics)
        return defaults  # DEBUG
        try:
            with open(self.log_path, "rb") as f:
                fields = pickle.load(f)
            if list(fields.to_dict().keys()) == list(defaults.to_dict().keys()):
                print("Loading sfr from log...")
                return fields
            print("Invalid log, loading default sfr...")
            return defaults
        except Exception as e:
            print("Unknown error, loading default sfr...")
            print(e)
            return defaults

    @wrap_errors(LogicalError)
    def dump(self) -> None:
        """
        Dump values of all state fields into state_field_log and readable log
        """
        with open(self.log_path, "wb") as f:
            pickle.dump(self.vars, f)
        with open(self.readable_log_path, "w") as f:
            json.dump(self.vars.to_dict(), f)

    @wrap_errors(LogicalError)
    def enter_sunlight(self) -> None:
        """
        Update LAST_DAYLIGHT_ENTRY and log new data
        """
        self.vars.LAST_DAYLIGHT_ENTRY = time.time()
        # Add data to dataframe
        df = pd.DataFrame(data={"daylight": self.vars.LAST_DAYLIGHT_ENTRY}, columns=["timestamp", "phase"])
        df.to_csv(self.orbit_log_path, mode="a", header=False)  # Append data to log

    @wrap_errors(LogicalError)
    def enter_eclipse(self) -> None:
        """
        Update LAST_ECLIPSE_ENTRY and log new data
        """
        self.vars.LAST_ECLIPSE_ENTRY = time.time()
        # Add data to dataframe
        df = pd.DataFrame(data={"eclipse": self.vars.LAST_ECLIPSE_ENTRY}, columns=["timestamp", "phase"])
        df.to_csv(self.orbit_log_path, mode="a", header=False)  # Append data to log

    @wrap_errors(LogicalError)
    def log_iridium(self, location, signal):
        """
        Logs iridium data
        :param location: current geolocation
        :param signal: iridium signal strength
        :param t: time to log, defaults to time method is called
        """
        with open(self.iridium_data_path, "a") as f:
            f.write(f"""{int(time.time()/100000)*100000},{int(time.time()%100000)},{",".join(map(str, location))},{str(signal)}\n""")

    @wrap_errors(LogicalError)
    def recent_power(self) -> list:
        """
        Returns list of buspower and power draws for all pdms
        :return: (list) [buspower, 0x01, 0x02... 0x0A]
        """
        if len(df := pd.read_csv(self.pwr_log_path, header=0)) == 0:
            return [self.eps.bus_power()] + self.eps.raw_pdm_draw()[1]
        cols = ["buspower"] + [f"0x0{str(hex(i))[2:].upper()}_pwr" for i in range(1, 11)]
        return df[cols].iloc[-1].tolist()

    @wrap_errors(LogicalError)
    def recent_gen(self) -> list:
        """
        Returns list of input power from all bcrs
        :return: (list) [bcr1, bcr2, bcr3]
        """
        if len(df := pd.read_csv(self.solar_log_path, header=0)) == 0:
            return self.eps.raw_solar_gen()
        cols = ["bcr1", "bcr2", "bcr3"]
        return df[cols].iloc[-1].tolist()

    @wrap_errors(LogicalError)
    def sun_detected(self) -> bool:
        """
        Checks if sun is detected
        :return: (bool)
        """
        solar = sum(self.eps.raw_solar_gen())
        if solar > self.eps.SUN_DETECTION_THRESHOLD: # Threshold of 1W
            return True
        if self.battery.telemetry["VBAT"]() > self.eps.V_EOC: # If EPS is at end of charge mode, MPPT will be disabled, making solar power an inaccurate representation of actual sunlight
            pcharge = self.battery.charging_power()
            if pcharge > (-1*self.eps.total_power(2)[0] + self.eps.SUN_DETECTION_THRESHOLD): # If the battery is charging, or is discharging at a rate below an acceptable threshold (i.e., the satellite is in a power hungry mode)
                return True
        return False

    @wrap_errors(LogicalError)
    def clear_logs(self):
        """
        WARNING: CLEARS ALL LOGGED DATA, ONLY USE FOR TESTING/DEBUG
        """
        for f in [self.pwr_log_path, self.solar_log_path, self.orbit_log_path, self.iridium_data_path]:
            headers = pd.read_csv(f, header=0).columns
            os.remove(f)
            with open(f, "w") as new:
                new.write(",".join(list(headers)) + "\n")
        if os.path.exists(self.log_path):
            os.remove(self.log_path)
        print("Logs cleared")

    @wrap_errors(LogicalError)
    def reset(self):
        """
        Resets state field registry log
        """
        with open(self.log_path, "w") as f:
            f.write("")

    @wrap_errors(LogicalError)
    def __turn_on_component(self, component: str) -> None:
        """
        Turns on component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.
        :param component: (str) component to turn on
        """
        if self.devices[component] is not None:  # if component is already on, stop method from running further
            return
        if self.vars.LOCKED_DEVICES[component] is True:  # if component is locked, stop method from running further
            return

        self.eps.commands["Pin On"](component)  # turns on component
        self.devices[component] = self.component_to_class[component](self)   # registers component as on by setting component status in sfr to object instead of None
        if component in self.component_to_serial:  # see if component has a serial converter to open
            serial_converter = self.component_to_serial[component]  # gets serial converter name of component
            self.eps.commands["Pin On"](serial_converter)  # turns on serial converter
            self.serial_converters[serial_converter] = True  # sets serial converter status to True (on)

        if component == "APRS":
            self.devices[component].disable_digi()
        if component == "IMU":
            self.devices[component].start()

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    @wrap_errors(LogicalError)
    def __turn_off_component(self, component: str) -> None:
        """
        Turns off component, updates sfr.devices, and updates sfr.serial_converters if applicable to component.
        :param component: (str) component to turn off
        """
        if self.devices[component] is None:  # if component is off, stop method from running further.
            return None
        if self.vars.LOCKED_DEVICES[component] is True:  # if component is locked, stop method from running further
            return None

        if component == "Iridium" and self.devices[
            "Iridium"] is not None:  # Read in MT buffer to avoid wiping commands when mode switching
            try:
                self.devices[component].next_msg()
            except Exception as e:
                print(e)

        self.devices[component] = None  # sets device object in sfr to None instead of object
        self.eps.commands["Pin Off"](component)  # turns component off
        if component in self.component_to_serial:  # see if component has a serial converter to close
            # Same suggestion as for __turn_on_component
            serial_converter = self.component_to_serial[component]  # get serial converter name for component
            self.eps.commands["Pin Off"](serial_converter)  # turn off serial converter
            self.serial_converters[serial_converter] = False  # sets serial converter status to False (off)

        # if component does not have serial converter (IMU, Antenna Deployer), do nothing

    @wrap_errors(LogicalError)
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

        for key in self.devices:
            if not self.devices[key] and key not in exceptions:  # if device is off and not in exceptions
                self.__turn_on_component(key)  # turn on device and serial converter if applicable

    @wrap_errors(LogicalError)
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

        for key in self.devices:
            if self.devices[key] and key not in exceptions:  # if device  is on and not in exceptions
                self.__turn_off_component(key)  # turn off device and serial converter if applicable