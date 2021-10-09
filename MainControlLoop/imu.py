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
