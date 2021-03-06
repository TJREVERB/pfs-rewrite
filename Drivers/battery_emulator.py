import time
from lib.exceptions import wrap_errors, BatteryError
from Drivers.device import Device


class Battery(Device):
    """
    Emulates Battery charge cycling without having to charge cycle the battery.
    Designed to be a drop-in replacement of the regular battery driver
    """

    def __init__(self, sfr):
        super().__init__(sfr)
        self.vbat = 8.25
        self.ibat = 5333
    
        self.commands = {
            # Board info commands: Basic board info
            "Board Status": lambda: 0,
            # Reads and returns board status
            "Last Error": lambda: 0,  # Reads and returns last error
            "Firmware Version": lambda: 0,
            # Reads and returns firmware version
            "Checksum": lambda: 0,
            # Reads and returns generated checksum of ROM contents

            "Brownout Resets": lambda: 0,
            # Number of Brown-out resets
            "Software Resets": lambda: 0,
            # Number of automatic software resets
            "Manual Resets": lambda: 0,
            # Number of manual resets

            "Manual Reset": lambda: 0,
            # Manually reset to initial state

            "Get Heater Controller Status": lambda: 0,
            # Heater Controller status, 0 = disabled, 1 = enabled (automatic)
            "Set Heater Controller Status": lambda: 0,
            # Set Heater Controller Status
        }
        self.telemetry = {
            "VBAT": self.volt_time_charge,
            "IBAT": lambda: abs(self.ibat),  # RETURNS IN MILLIAMPS
            # 1 = discharging, 0 = charging
            "IDIRBAT": lambda: int(self.ibat < 0),
            "TBRD": lambda: 295,  # temperature in K
            "IPCM5V": lambda: 0,  # 5V current consumption in mA
            "VPCM5V": lambda: 5,  # 5V voltage
            "IPCM3V3": lambda: 0,  # 3V3 current consumption in mA
            "VPCM3V3": lambda: 3.3,  # 3V3 voltage
            "TBAT1": lambda: 295,  # Batt1 temperature in K
            # 1 = heater on, 0 = heater off
            "HBAT1": lambda: 0,
            "TBAT2": lambda: 295,  # Batt2 temperature in K
            # 1 = heater on, 0 = heater off
            "HBAT2": lambda: 0,
            "TBAT3": lambda: 295,  # Batt3 temperature in K
            # 1 = heater on, 0 = heater off
            "HBAT3": lambda: 0,
            "TBAT4": lambda: 295,  # Batt4 temperature in K
            # 1 = heater on, 0 = heater off
            "HBAT4": lambda: 0
        }
    
    def volt_time_charge(self):
        hours = (time.perf_counter())/3600
        
        hours = hours % (148/74)
        if hours >= 0 and hours < 70.09/74:
            self.ibat = 5333
            return (6.2 + (74*hours/4.5)**.2)
        if hours >= 70.09/74 and hours < 74/74:
            self.ibat = 5333
            return (1/6)*((74*hours/4.5) - 15)**3 + 7.9
        if hours >= 74/74 and hours < 77.91/74:
            self.ibat = -5333
            return (1/6)*((-1*74*hours/4.5) + 161/9 )**3 + 7.9
        if hours >= 77.91/74 and hours < 148/74:
            self.ibat = -5333
            return 6.2 + (-1*74*hours/4.5 + 148/4.5 )**.2

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
