from smbus2 import SMBus
import time
from lib.exceptions import wrap_errors, BatteryError
from Drivers.device import Device


# Datasheet https://drive.google.com/file/d/13GKtzXyufFxrbeQ7wEGgo796i91W1dQt/view

class Battery(Device):
    """
    Class to interface with Clydespace battery TTC node
    """

    @wrap_errors(BatteryError)
    def __init__(self, sfr):
        super().__init__(sfr)
        self.addr = 0x2a
        self.bus = SMBus(1)

        # Refer to datasheet section 12.3 for a list of commands
        self.commands = {
            # Board info commands: Basic board info
            "Board Status": lambda: self.request(0x01, [0x00], 2),
            # Reads and returns board status
            "Last Error": lambda: self.request(0x03, [0x00], 2),  # Reads and returns last error
            "Firmware Version": lambda: self.request(0x04, [0x00], 2),
            # Reads and returns firmware version
            "Checksum": lambda: self.request(0x05, [0x00], 2),
            # Reads and returns generated checksum of ROM contents

            "Brownout Resets": lambda: self.request(0x31, [0x00], 2),
            # Number of Brown-out resets
            "Software Resets": lambda: self.request(0x32, [0x00], 2),
            # Number of automatic software resets
            "Manual Resets": lambda: self.request(0x33, [0x00], 2),
            # Number of manual resets

            "Manual Reset": lambda: self.request(0x80, [0x00], 2),
            # Manually reset to initial state

            "Get Heater Controller Status": lambda: self.request(0x90, [0x00], 2),
            # Heater Controller status, 0 = disabled, 1 = enabled (automatic)
            "Set Heater Controller Status": lambda mode: self.request(0x91, [mode], 2),
            # Set Heater Controller Status
        }
        self.telemetry = {
            "VBAT": lambda: self.telemetry_request([0xE2, 0x80], 0.008993),
            "IBAT": lambda: self.telemetry_request([0xE2, 0x84], 14.662757),  # RETURNS IN MILLIAMPS
            # 1 = discharging, 0 = charging
            "IDIRBAT": lambda: wrap_errors(BatteryError)(int)(self.telemetry_request([0xE2, 0x8E], 1 / 512)),
            "TBRD": lambda: self.telemetry_request([0xE3, 0x08], 0.372434),  # temperature in K
            "IPCM5V": lambda: self.telemetry_request([0xE2, 0x14], 1.327547),  # 5V current consumption in mA
            "VPCM5V": lambda: self.telemetry_request([0xE2, 0x10], 0.005865),  # 5V voltage
            "IPCM3V3": lambda: self.telemetry_request([0xE2, 0x04], 1.327547),  # 3V3 current consumption in mA
            "VPCM3V3": lambda: self.telemetry_request([0xE2, 0x00], 0.004311),  # 3V3 voltage
            "TBAT1": lambda: self.telemetry_request([0xE3, 0x98], 0.397600),  # Batt1 temperature in K
            # 1 = heater on, 0 = heater off
            "HBAT1": lambda: wrap_errors(BatteryError)(int)(self.telemetry_request([0xE3, 0x9F], 1 / 512)),
            "TBAT2": lambda: self.telemetry_request([0xE3, 0xA8], 0.397600),  # Batt2 temperature in K
            # 1 = heater on, 0 = heater off
            "HBAT2": lambda: wrap_errors(BatteryError)(int)(self.telemetry_request([0xE3, 0xAF], 1 / 512)),
            "TBAT3": lambda: self.telemetry_request([0xE3, 0xB8], 0.397600),  # Batt3 temperature in K
            # 1 = heater on, 0 = heater off
            "HBAT3": lambda: wrap_errors(BatteryError)(int)(self.telemetry_request([0xE3, 0xBF], 1 / 512)),
            "TBAT4": lambda: self.telemetry_request([0xE3, 0xC8], 0.397600),  # Batt4 temperature in K
            # 1 = heater on, 0 = heater off
            "HBAT4": lambda: wrap_errors(BatteryError)(int)(self.telemetry_request([0xE3, 0xCF], 1 / 512))
        }

    @wrap_errors(BatteryError)
    def request(self, register, data, length) -> bytes:
        """
        Requests and returns uninterpreted bytes object
        :param register: register
        :param data: data
        :param length: number of bytes to read
        :return: (byte) response from EPS
        """
        self.bus.write_i2c_block_data(self.addr, register, data)
        time.sleep(.05)
        result = self.bus.read_i2c_block_data(self.addr, 0, length)
        time.sleep(.2)
        return result

    @wrap_errors(BatteryError)
    def command(self, register, data) -> bool:
        """
        Sends command to EPS
        :param register: register
        :param data: data
        :return: (bool) whether command was successful
        """
        result = self.bus.write_i2c_block_data(self.addr, register, data)
        time.sleep(.2)
        return True

    @wrap_errors(BatteryError)
    def telemetry_request(self, tle, multiplier) -> float:
        """
        Requests and returns interpreted telemetry data
        :param tle: TLE code
        :parm multiplier: = multiplier
        :return: (float) telemetry value
        """
        result = []
        for i in range(3): #avg filter
            raw = self.request(0x10, tle, 2)
            result.append((raw[0] << 8 | raw[1]) * multiplier)
        return sum(result)/len(result)

    @wrap_errors(BatteryError)
    def charging_power(self) -> float:
        """
        Returns total power going into the battery or out of
        :return: (float) power in watts, if positive, battery is charging, if negative, battery is discharging
        """
        pwr = self.telemetry["VBAT"]() * self.telemetry["IBAT"]() / 1000
        if self.telemetry["IDIRBAT"]() != 0:
            pwr *= -1
        print(f"Charging Power: {pwr}")
        return pwr
