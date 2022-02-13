import time
from lib.exceptions import wrap_errors, BatteryError
from Drivers.device import Device

class Battery(Device):
    """
    Emulates Battery charge cycling without having to charge cycle the battery.
    """

    def __init__(self, sfr):
        super().__init__(sfr)
    
        self.commands = {
            # Board info commands: Basic board info
            "Board Status": 0,
            # Reads and returns board status
            "Last Error": 0,  # Reads and returns last error
            "Firmware Version": 0,
            # Reads and returns firmware version
            "Checksum": 0,
            # Reads and returns generated checksum of ROM contents

            "Brownout Resets": 0,
            # Number of Brown-out resets
            "Software Resets": 0,
            # Number of automatic software resets
            "Manual Resets": 0,
            # Number of manual resets

            "Manual Reset": 0,
            # Manually reset to initial state

            "Get Heater Controller Status": 0,
            # Heater Controller status, 0 = disabled, 1 = enabled (automatic)
            "Set Heater Controller Status": 0,
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