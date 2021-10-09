from functools import partial
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from smbus2 import SMBusWrapper
from smbus2 import SMBus
import time
from math import radians

try:
    import struct
except ImportError:
    import ustruct as struct

class IMU:
    """
    Class for LSM9DS1 IMU Breakout Board
    Referenced from https://github.com/adafruit/Adafruit_CircuitPython_LSM9DS1/blob/main/adafruit_lsm9ds1.py
    """
    def __init__(self, state_field_registry):
        self.sfr = state_field_registry

        #INTERNAL CONSTANTS
        self.ADDRESS_ACCELGYRO: hex = 0x6B
        self.ADDRESS_MAG: hex = 0x1E
        self.XG_ID: bin = 0b01101000
        self.MAG_ID: bin = 0b00111101
        self.ACCEL_MG_LSB_2G = 0.061
        self.ACCEL_MG_LSB_4G = 0.122
        self.ACCEL_MG_LSB_8G = 0.244
        self.ACCEL_MG_LSB_16G = 0.732
        self.MAG_MGAUSS_4GAUSS = 0.14
        self.MAG_MGAUSS_8GAUSS = 0.29
        self.MAG_MGAUSS_12GAUSS = 0.43
        self.MAG_MGAUSS_16GAUSS = 0.58
        self.GYRO_DPS_DIGIT_245DPS = 0.00875
        self.GYRO_DPS_DIGIT_500DPS = 0.01750
        self.GYRO_DPS_DIGIT_2000DPS = 0.07000
        self.TEMP_LSB_CELSIUS = 8 #1C = 8, 25C = 200, etc.
        self.REGISTER_WHOAMI_XG: hex = 0x0F
        self.REGISTER_CTRL_REG1_G: hex = 0x10
        self.REGISTER_CTRL_REG2_G: hex = 0x11
        self.REGISTER_CTRL_REG3_G: hex = 0x12
        self.REGISTER_TEMP_OUT_L: hex = 0x15
        self.REGISTER_TEMP_OUT_H: hex = 0x16
        self.REGISTER_STATUS_REG: hex = 0x17
        self.REGISTER_OUT_XLG: hex = 0x18
        self.REGISTER_OUT_XHG: hex = 0x19
        self.REGISTER_OUT_YLG: hex = 0x1A
        self.REGISTER_OUT_YHG: hex = 0x1B
        self.REGISTER_OUT_ZLG: hex = 0x1C
        self.REGISTER_OUT_ZHG: hex = 0x1D
        self.REGISTER_CTRL_REG4: hex = 0x1E
        self.REGISTER_CTRL_REG5_XL: hex = 0x1F
        self.REGISTER_CTRL_REG6_XL: hex = 0x20
        self.REGISTER_CTRL_REG7_XL: hex = 0x21
        self.REGISTER_CTRL_REG8: hex = 0x22
        self.REGISTER_CTRL_REG9: hex = 0x23
        self.REGISTER_CTRL_REG10: hex = 0x24
        self.REGISTER_OUT_XLXL: hex = 0x28
        self.REGISTER_OUT_XHXL: hex = 0x29
        self.REGISTER_OUT_YLXL: hex = 0x2A
        self.REGISTER_OUT_YHXL: hex = 0x2B
        self.REGISTER_OUT_ZLXL: hex = 0x2C
        self.REGISTER_OUT_ZHXL: hex = 0x2D
        self.REGISTER_WHOAMI_M: hex = 0x0F
        self.REGISTER_CTRL_REG1_M: hex = 0x20
        self.REGISTER_CTRL_REG2_M: hex = 0x21
        self.REGISTER_CTRL_REG3_M: hex = 0x22
        self.REGISTER_CTRL_REG4_M: hex = 0x23
        self.REGISTER_CTRL_REG5_M: hex = 0x24
        self.REGISTER_STATUS_REG_M: hex = 0x27
        self.REGISTER_OUT_XLM: hex = 0x28
        self.REGISTER_OUT_XHM: hex = 0x29
        self.REGISTER_OUT_YLM: hex = 0x2A
        self.REGISTER_OUT_YHM: hex = 0x2B
        self.REGISTER_OUT_ZLM: hex = 0x2C
        self.REGISTER_OUT_ZHM: hex = 0x2D
        self.REGISTER_CFG_M: hex = 0x30
        self.REGISTER_INT_SRC_M: hex = 0x31
        self.MAGTYPE = True
        self.XGTYPE = False
        self.SENSORS_GRAVITY_STANDARD = 9.80665
        self.SPI_AUTO_INCR: hex = 0x40


        #USER FACING CONSTANTS
        self.ACCELRANGE_2G: bin = 0b00 << 3
        self.ACCELRANGE_16G: bin = 0b01 << 3
        self.ACCELRANGE_4G: bin = 0b10 << 3
        self.ACCELRANGE_8G: bin = 0b11 << 3
        self.MAGGAIN_4GAUSS: bin = 0b00 << 5 #+/- 4 gauss
        self.MAGGAIN_8GAUSS: bin = 0b01 << 5 #+/- 8 gauss
        self.MAGGAIN_12GAUSS: bin = 0b10 << 5 #+/- 12 gauss
        self.MAGGAIN_16GAUSS: bin = 0b11 << 5 #+/- 16 gauss
        self.GYROSCALE_245DPS: bin = 0b00 << 3 #+/- 245 degrees/s rotation
        self.GYROSCALE_500DPS: bin = 0b01 << 3 #+/- 500 degrees/s rotation
        self.GYROSCALE_2000DPS: bin = 0b11 << 3 #+/- 2000 degrees/s rotation
