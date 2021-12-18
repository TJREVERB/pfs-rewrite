import time
import os
import pandas as pd
import pickle
import json
from MainControlLoop.Drivers.eps import EPS
from MainControlLoop.Drivers.battery import Battery
from MainControlLoop.Drivers.bno055 import IMU_I2C
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
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket


class StateFieldRegistry:
    @wrap_errors(LogicalError)
    def __init__(self):
        """
        Variables common across our pfs
        Vars in the "vars" object get logged
        """
        self.logs = {
            "sfr": self.Log("./MainControlLoop/lib/data/state_field_log.pkl", None),
            "sfr_readable": self.Log("./MainControlLoop/lib/data/state_field_log.json", None),
            "power": self.Log("./MainControlLoop/lib/data/pwr_draw_log.csv",
                              ["ts0", "ts1", "buspower", "0x01", "0x02", "0x03", "0x04", "0x05",
                               "0x06", "0x07", "0x08", "0x09", "0x0A"]),
            "solar": self.Log("./MainControlLoop/lib/data/solar_generation_log.csv",
                              ["ts0", "ts1", "bcr1", "bcr2", "bcr3"]),
            "voltage_energy": self.Log("./MainControlLoop/lib/data/volt-energy-map.csv",
                                       ["voltage", "energy"]),
            "orbits": self.Log("./MainControlLoop/lib/data/orbit_log.csv",
                               ["ts0", "ts1", "phase"]),
            "iridium": self.Log("./MainControlLoop/lib/data/iridium_data.csv",
                                ["ts0", "ts1", "latitude", "longitude", "altitude", "signal"]),
            "imu": self.Log("./MainControlLoop/lib/data/imu_data.csv",
                            ["ts0", "ts1", "xgyro", "ygyro", "zgyro"]),
            "command": self.Log("./MainControlLoop/lib/data/command_log.csv",
                                ["ts0", "ts1", "radio", "command", "arg", "registry", "msn", "result"]),
            "transmission": self.Log("./MainControlLoop/lib/data/transmission_log.csv",
                                     ["ts0", "ts1", "radio", "size"]),
        }

        self.eps = EPS(self)  # EPS never turns off
        self.battery = Battery()
        self.imu = IMU_I2C(self)
        self.analytics = Analytics(self)
        self.command_executor = CommandExecutor(self)
        self.logger = Logger(self)

        self.devices = {
            "Iridium": None,
            "APRS": None,
            "Antenna Deployer": None,
            "IMU": None
        }
        self.serial_converters = {  # False if off, True if on
            "UART-RS232": False,  # Iridium Serial Converter
            "SPI-UART": False,  # APRS Serial Converter
            "USB-UART": False  # Alternate APRS Serial Converter
        }
        self.modes_list = {
            "Startup": Startup,
            "Charging": Charging,
            "Science": Science,
            "Outreach": Outreach,
            "Repeater": Repeater,
        }
        self.component_to_serial = {  # in sfr so command_executor can switch serial_converter of APRS if needed.
            "Iridium": "UART-RS232",
            "APRS": "SPI-UART"
        }
        self.components = [
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

        self.component_to_class = {  # returns class from component name
            "Iridium": Iridium,
            "APRS": APRS,
            "IMU": IMU_I2C,
            "Antenna Deployer": AntennaDeployer
        }
        self.instruct = {
            "Pin On": self.__turn_on_component,
            "Pin Off": self.__turn_off_component,
            "All On": self.__turn_all_on,
            "All Off": self.__turn_all_off
        }
        # self.MODE = Startup(self)  # Stores mode object, we don't want to log it
        self.MODE = Science(self)  # DEBUG!!!
        self.vars = self.load()
        self.vars.LAST_STARTUP = time.time()

    @wrap_errors(LogicalError)
    def load(self):
        """
        Load sfr fields from log
        :return: (Registry) loaded registry
        """
        defaults = self.Registry(self)
        return defaults  # DEBUG
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
    def log_iridium(self, location: tuple, signal):
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
        return df[[i for i in self.logs["power"].headers if i.endswith("_pwr")]].iloc[-1].tolist()

    @wrap_errors(LogicalError)
    def recent_gen(self) -> list:
        """
        Returns list of input power from all bcrs
        :return: (list) [bcr1, bcr2, bcr3]
        """
        if len(df := self.logs["solar"].read()) == 0:
            return self.eps.raw_solar_gen()
        # Get last row, exclude timestamp columns
        return df[[i for i in self.logs["solar"].headers if i.find("ts") == -1]].iloc[-1].tolist()

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
            self.logs[i].clear()
        print("Logs cleared")

    @wrap_errors(LogicalError)
    def reset(self):
        """
        Resets state field registry log
        """
        self.logs["sfr"].write(self.Registry())  # Write default log

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
        self.devices[component] = self.component_to_class[component](self)  # registers component as on by setting
        # component status in sfr to object instead of None
        if component in self.component_to_serial:  # see if component has a serial converter to open
            serial_converter = self.component_to_serial[component]  # gets serial converter name of component
            self.eps.commands["Pin On"](serial_converter)  # turns on serial converter
            self.serial_converters[serial_converter] = True  # sets serial converter status to True (on)

        if component == "APRS":
            self.devices[component].disable_digi()
        if component == "IMU":
            time.sleep(.5)
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

        if component == "Iridium" and self.devices["Iridium"] is not None:  # Read in MT buffer to avoid wiping
            # commands when mode switching
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
    def __turn_all_on(self, exceptions=None) -> None:
        """
        Turns all components on automatically, except for Antenna Deployer.
        Calls __turn_on_component for every key in self.devices except for those in exceptions parameter
        :param exceptions: (list) components to not turn on, default is ["Antenna Deployer, IMU"]
        :return: None
        """
        if exceptions is None:  # If no argument provided
            exceptions = ["Antenna Deployer", "IMU"]  # Set to default list

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

    @wrap_errors(LogicalError)
    def set_primary_radio(self, new_radio: str, turn_off_old=False):
        """
        Takes care of switching sfr PRIMARY_RADIO field:
        instantiates primary radio if necessary, kills the previous radio if requested
        """
        # TODO: send notification to groundstation over new radio
        previous_radio = self.vars.PRIMARY_RADIO
        if new_radio != previous_radio:  # if it's a new radio
            if turn_off_old:
                self.instruct["Pin Off"](previous_radio)
            self.vars.PRIMARY_RADIO = new_radio
            if self.devices[new_radio] is None:  # initialize it
                self.instruct["Pin On"](new_radio)
            # transmit update to groundstation
            self.vars.LAST_IRIDIUM_RECEIVED = time.time()
            unsolicited_packet = TransmissionPacket("GPR", [], 0)
            self.command_executor.GPR(unsolicited_packet)

    class Log:
        @wrap_errors(LogicalError)
        def __init__(self, path, headers):
            self.path = path
            self.headers = headers
            self.ext = path.split(".")[-1]
            if not os.path.exists(self.path):  # If log doesn't exist on filesystem, create it
                self.clear()
            elif self.ext == "csv":  # For csv files
                if pd.read_csv(self.path).columns.tolist() != self.headers:
                    self.clear()  # Clear log if columns don't match up (out of date log)

        @wrap_errors(LogicalError)
        def clear(self):
            """
            Reset log
            """
            if self.ext == "csv" and self.path.find("volt-energy-map") == -1:  # For csv files
                with open(self.path, "w") as f:  # Open file
                    f.write(",".join(self.headers) + "\n")  # Write headers + newline
            elif self.ext == "pkl" and os.path.exists(self.path):  # For pkl files which exist
                os.remove(self.path)  # Delete
            elif self.ext == "json":  # For json files
                if os.path.exists(self.path):  # IF file exists
                    os.remove(self.path)  # Delete
                open(self.path, "x").close()  # Create empty file

        @wrap_errors(LogicalError)
        def write(self, data):
            """
            Append one line of data to a csv log or dump to a pickle or json log
            :param data: dictionary of the form {"column_name": value} if csv log
                object if pkl log
                dictionary of the form {"field": float_val} if json log
            """
            if self.ext == "csv":
                if list(data.keys()) != self.headers:  # Raise error if keys are wrong
                    raise LogicalError(details="Incorrect keys for logging")
                # Append to log
                pd.DataFrame.from_dict({k: [v] for (k, v) in data.items()}).to_csv(
                    self.path, mode="a", header=False, index=False)
            elif self.ext == "pkl":  # If log is pkl
                with open(self.path, "wb") as f:
                    for i in data.__dict__.keys():
                        print(i + ": " + str(getattr(data, i)))
                        pickle.dumps(getattr(data, i))
                    pickle.dump(data, f)  # Dump to file
            elif self.ext == "json":  # If log is json
                with open(self.path, "w") as f:
                    json.dump(data, f)  # Dump to file

        @wrap_errors(LogicalError)
        def truncate(self, n):
            """
            Remove n rows from log file
            """
            if self.ext != "csv":
                raise LogicalError(details="Attempted to truncate non-csv log!")
            elif len(df := self.read()) <= n:
                self.clear()
            else:
                df.iloc[:-n].to_csv(self.path, mode="w", header=True, index=False)

        @wrap_errors(LogicalError)
        def read(self):
            """
            Read and return entire log
            :return: dataframe if csv, object if pickle, dictionary if json
            """
            if self.ext == "csv":  # Return dataframe if csv
                return pd.read_csv(self.path, header=0)
            if self.ext == "pkl":  # Return object if pickle
                with open(self.path, "rb") as f:
                    return pickle.load(f)
            with open(self.path, "r") as f:
                return json.load(f)  # Return dict if json

    class Registry:
        @wrap_errors(LogicalError)
        def __init__(self, sfr):
            self.ANTENNA_DEPLOYED = False
            # Integral estimate of remaining battery capacity
            self.BATTERY_CAPACITY_INT = sfr.analytics.volt_to_charge(sfr.battery.telemetry["VBAT"]())
            self.FAILURES = []
            self.LAST_DAYLIGHT_ENTRY = time.time() - 45 * 60 if (sun := sfr.sun_detected()) else time.time()
            self.LAST_ECLIPSE_ENTRY = time.time() if sun else time.time() - 45 * 60
            self.ORBITAL_PERIOD = sfr.analytics.calc_orbital_period()
            # Switch to charging mode if battery capacity (J) dips below threshold. 30% of max capacity
            self.LOWER_THRESHOLD = 133732.8 * 0.3
            self.UPPER_THRESHOLD = 999999  # TODO: USE REAL VALUE
            self.UNSUCCESSFUL_SEND_TIME_CUTOFF = 60*60*24  # if it has been unsuccessfully trying to send messages
            # via iridium for this amount of time, switch primary to APRS
            self.UNSUCCESSFUL_RECEIVE_TIME_CUTOFF = 60*60*24*7  # if no message is received on iridium for this
            # amount of time, it will switch primary radio to APRS
            self.DETUMBLE_THRESHOLD = 5  # angle for acceptable x and y rotation for detumble
            self.PACKET_AGE_LIMIT = 60*6  # age limit before switching primary radio (seconds)
            # self.MODE = Startup(sfr)  # Stores mode class, mode is instantiated in mcl
            self.MODE = Science(sfr)  # DEBUG!!!
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
            self.LAST_STARTUP = time.time()
            self.LAST_IRIDIUM_RECEIVED = time.time()

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
                list(StateFieldRegistry.modes_list.keys()).index(type(self.MODE).__name__),
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

