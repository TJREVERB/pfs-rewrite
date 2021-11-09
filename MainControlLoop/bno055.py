# SPDX-FileCopyrightText: 2017 Radomir Dopieralski for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
This is a CircuitPython driver for the Bosch BNO055 nine degree of freedom
inertial measurement unit module with sensor fusion.

* Author(s): Radomir Dopieralski
* Modified by TJREVERB team

**Hardware:**

* Adafruit `9-DOF Absolute Orientation IMU Fusion Breakout - BNO055
  <https://www.adafruit.com/product/4646>`_ (Product ID: 4646)
"""
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from smbus2 import SMBus
import time
import numpy as np
from math import atan
from math import degrees
try:
    import struct
except ImportError:
    import ustruct as struct

class Struct:
    """
    Arbitrary structure register that is readable and writeable.
    Values are tuples that map to the values in the defined struct.  See struct
    module documentation for struct format string and its possible value types.
    :param int register_address: The register address to read the bit from
    :param type struct_format: The struct format string for this register.
    """

    def __init__(self, register_address, struct_format):
        self.format = struct_format
        self.buffer = bytearray(1 + struct.calcsize(self.format))
        self.buffer[0] = register_address

    def __get__(self, obj, objtype=None):
        obj.bus.write_byte(obj.address, self.buffer[0])
        time.sleep(.1)
        self.buffer[1:] = obj.bus.read_i2c_block_data(obj.address, 0, len(self.buffer)-1)
        return struct.unpack_from(self.format, memoryview(self.buffer)[1:])

        #with obj.i2c_device as i2c:
        #    i2c.write_then_readinto(self.buffer, self.buffer, out_end=1, in_start=1)
        #return struct.unpack_from(self.format, memoryview(self.buffer)[1:])

    def __set__(self, obj, value):
        struct.pack_into(self.format, self.buffer, 1, *value)
        obj.bus.write_i2c_block_data(obj.address, self.buffer[0], self.buffer[1:])

        #with obj.i2c_device as i2c:
        #    i2c.write(self.buffer)


class UnaryStruct:
    """
    Arbitrary single value structure register that is readable and writeable.
    Values map to the first value in the defined struct.  See struct
    module documentation for struct format string and its possible value types.
    :param int register_address: The register address to read the bit from
    :param type struct_format: The struct format string for this register.
    """

    def __init__(self, register_address, struct_format):
        self.format = struct_format
        self.address = register_address

    def __get__(self, obj, objtype=None):
        buf = bytearray(1 + struct.calcsize(self.format))
        buf[0] = self.address
        obj.bus.write_byte(obj.address, buf[0])
        time.sleep(.1)
        buf[1:] = obj.bus.read_i2c_block_data(obj.address, 0, len(buf)-1)
        return struct.unpack_from(self.format, buf, 1)[0]

    def __set__(self, obj, value):
        buf = bytearray(1 + struct.calcsize(self.format))
        buf[0] = self.address
        struct.pack_into(self.format, buf, 1, value)
        obj.bus.write_i2c_block_data(obj.address, buf[0], buf[1:])


class _ScaledReadOnlyStruct(Struct):  # pylint: disable=too-few-public-methods
    def __init__(self, register_address, struct_format, scale):
        super().__init__(register_address, struct_format)
        self.scale = scale

    def __get__(self, obj, objtype=None):
        result = super().__get__(obj, objtype)
        return tuple(self.scale * v for v in result)

    def __set__(self, obj, value):
        raise NotImplementedError()

class _ReadOnlyUnaryStruct(UnaryStruct):  # pylint: disable=too-few-public-methods
    def __set__(self, obj, value):
        raise NotImplementedError()


class _ModeStruct(Struct):  # pylint: disable=too-few-public-methods
    def __init__(self, register_address, struct_format, mode):
        super().__init__(register_address, struct_format)
        self.mode = mode

    def __get__(self, obj, objtype=None):
        last_mode = obj.mode
        obj.mode = self.mode
        result = super().__get__(obj, objtype)
        obj.mode = last_mode
        # single value comes back as a one-element tuple
        return result[0] if isinstance(result, tuple) and len(result) == 1 else result

    def __set__(self, obj, value):
        last_mode = obj.mode
        obj.mode = self.mode
        # underlying __set__() expects a tuple
        set_val = value if isinstance(value, tuple) else (value,)
        super().__set__(obj, set_val)
        obj.mode = last_mode

class IMU:
    """
    Base class for the BNO055 9DOF IMU sensor.
    """

    #Constants:
    _CHIP_ID = 0xA0

    CONFIG_MODE = 0x00
    ACCONLY_MODE = 0x01
    MAGONLY_MODE = 0x02
    GYRONLY_MODE = 0x03
    ACCMAG_MODE = 0x04
    ACCGYRO_MODE = 0x05
    MAGGYRO_MODE = 0x06
    AMG_MODE = 0x07
    IMUPLUS_MODE = 0x08
    COMPASS_MODE = 0x09
    M4G_MODE = 0x0A
    NDOF_FMC_OFF_MODE = 0x0B
    NDOF_MODE = 0x0C

    ACCEL_2G = 0x00  # For accel_range property
    ACCEL_4G = 0x01  # Default
    ACCEL_8G = 0x02
    ACCEL_16G = 0x03
    ACCEL_7_81HZ = 0x00  # For accel_bandwidth property
    ACCEL_15_63HZ = 0x04
    ACCEL_31_25HZ = 0x08
    ACCEL_62_5HZ = 0x0C  # Default
    ACCEL_125HZ = 0x10
    ACCEL_250HZ = 0x14
    ACCEL_500HZ = 0x18
    ACCEL_1000HZ = 0x1C
    ACCEL_NORMAL_MODE = 0x00  # Default. For accel_mode property
    ACCEL_SUSPEND_MODE = 0x20
    ACCEL_LOWPOWER1_MODE = 0x40
    ACCEL_STANDBY_MODE = 0x60
    ACCEL_LOWPOWER2_MODE = 0x80
    ACCEL_DEEPSUSPEND_MODE = 0xA0

    GYRO_2000_DPS = 0x00  # Default. For gyro_range property
    GYRO_1000_DPS = 0x01
    GYRO_500_DPS = 0x02
    GYRO_250_DPS = 0x03
    GYRO_125_DPS = 0x04
    GYRO_523HZ = 0x00  # For gyro_bandwidth property
    GYRO_230HZ = 0x08
    GYRO_116HZ = 0x10
    GYRO_47HZ = 0x18
    GYRO_23HZ = 0x20
    GYRO_12HZ = 0x28
    GYRO_64HZ = 0x30
    GYRO_32HZ = 0x38  # Default
    GYRO_NORMAL_MODE = 0x00  # Default. For gyro_mode property
    GYRO_FASTPOWERUP_MODE = 0x01
    GYRO_DEEPSUSPEND_MODE = 0x02
    GYRO_SUSPEND_MODE = 0x03
    GYRO_ADVANCEDPOWERSAVE_MODE = 0x04

    MAGNET_2HZ = 0x00  # For magnet_rate property
    MAGNET_6HZ = 0x01
    MAGNET_8HZ = 0x02
    MAGNET_10HZ = 0x03
    MAGNET_15HZ = 0x04
    MAGNET_20HZ = 0x05  # Default
    MAGNET_25HZ = 0x06
    MAGNET_30HZ = 0x07
    MAGNET_LOWPOWER_MODE = 0x00  # For magnet_operation_mode property
    MAGNET_REGULAR_MODE = 0x08  # Default
    MAGNET_ENHANCEDREGULAR_MODE = 0x10
    MAGNET_ACCURACY_MODE = 0x18
    MAGNET_NORMAL_MODE = 0x00  # for magnet_power_mode property
    MAGNET_SLEEP_MODE = 0x20
    MAGNET_SUSPEND_MODE = 0x40
    MAGNET_FORCEMODE_MODE = 0x60  # Default

    _POWER_NORMAL = 0x00
    _POWER_LOW = 0x01
    _POWER_SUSPEND = 0x02

    _MODE_REGISTER = 0x3D
    _PAGE_REGISTER = 0x07
    _ACCEL_CONFIG_REGISTER = 0x08
    _MAGNET_CONFIG_REGISTER = 0x09
    _GYRO_CONFIG_0_REGISTER = 0x0A
    _GYRO_CONFIG_1_REGISTER = 0x0B
    _CALIBRATION_REGISTER = 0x35
    _OFFSET_ACCEL_REGISTER = 0x55
    _OFFSET_MAGNET_REGISTER = 0x5B
    _OFFSET_GYRO_REGISTER = 0x61
    _RADIUS_ACCEL_REGISTER = 0x67
    _RADIUS_MAGNET_REGISTER = 0x69
    _TRIGGER_REGISTER = 0x3F
    _POWER_REGISTER = 0x3E
    _ID_REGISTER = 0x00
    # Axis remap registers and values
    _AXIS_MAP_CONFIG_REGISTER = 0x41
    _AXIS_MAP_SIGN_REGISTER = 0x42
    AXIS_REMAP_X = 0x00
    AXIS_REMAP_Y = 0x01
    AXIS_REMAP_Z = 0x02
    AXIS_REMAP_POSITIVE = 0x00
    AXIS_REMAP_NEGATIVE = 0x01

    def __init__(self, state_field_registry):
        self.sfr = state_field_registry
        chip_id = self._read_register(IMU._ID_REGISTER)
        if chip_id != IMU._CHIP_ID:
            raise RuntimeError("bad chip id (%x != %x)" % (chip_id, IMU._CHIP_ID))
        self._reset()
        self._write_register(IMU._POWER_REGISTER, IMU._POWER_NORMAL)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        self._write_register(IMU._TRIGGER_REGISTER, 0x00)
        self.accel_range = IMU.ACCEL_4G
        self.gyro_range = IMU.GYRO_2000_DPS
        self.magnet_rate = IMU.MAGNET_20HZ
        time.sleep(0.01)
        self.mode = IMU.NDOF_MODE
        time.sleep(0.01)

    def _reset(self):
        """Resets the sensor to default settings."""
        self.mode = IMU.CONFIG_MODE
        try:
            self._write_register(IMU._TRIGGER_REGISTER, 0x20)
        except OSError:  # error due to the chip resetting
            pass
        # wait for the chip to reset (650 ms typ.)
        time.sleep(0.7)

    @property
    def mode(self):
        """
        legend: x=on, -=off (see Table 3-3 in datasheet)

        +------------------+-------+---------+------+----------+----------+
        | Mode             | Accel | Compass | Gyro | Fusion   | Fusion   |
        |                  |       | (Mag)   |      | Absolute | Relative |
        +==================+=======+=========+======+==========+==========+
        | CONFIG_MODE      |   -   |   -     |  -   |     -    |     -    |
        +------------------+-------+---------+------+----------+----------+
        | ACCONLY_MODE     |   X   |   -     |  -   |     -    |     -    |
        +------------------+-------+---------+------+----------+----------+
        | MAGONLY_MODE     |   -   |   X     |  -   |     -    |     -    |
        +------------------+-------+---------+------+----------+----------+
        | GYRONLY_MODE     |   -   |   -     |  X   |     -    |     -    |
        +------------------+-------+---------+------+----------+----------+
        | ACCMAG_MODE      |   X   |   X     |  -   |     -    |     -    |
        +------------------+-------+---------+------+----------+----------+
        | ACCGYRO_MODE     |   X   |   -     |  X   |     -    |     -    |
        +------------------+-------+---------+------+----------+----------+
        | MAGGYRO_MODE     |   -   |   X     |  X   |     -    |     -    |
        +------------------+-------+---------+------+----------+----------+
        | AMG_MODE         |   X   |   X     |  X   |     -    |     -    |
        +------------------+-------+---------+------+----------+----------+
        | IMUPLUS_MODE     |   X   |   -     |  X   |     -    |     X    |
        +------------------+-------+---------+------+----------+----------+
        | COMPASS_MODE     |   X   |   X     |  -   |     X    |     -    |
        +------------------+-------+---------+------+----------+----------+
        | M4G_MODE         |   X   |   X     |  -   |     -    |     X    |
        +------------------+-------+---------+------+----------+----------+
        | NDOF_FMC_OFF_MODE|   X   |   X     |  X   |     X    |     -    |
        +------------------+-------+---------+------+----------+----------+
        | NDOF_MODE        |   X   |   X     |  X   |     X    |     -    |
        +------------------+-------+---------+------+----------+----------+

        The default mode is :const:`NDOF_MODE`.

        | You can set the mode using the line below:
        | ``sensor.mode = adafruit_bno055.ACCONLY_MODE``
        | replacing :const:`ACCONLY_MODE` with the mode you want to use

        .. data:: CONFIG_MODE

           This mode is used to configure BNO, wherein all output data is reset to zero and sensor
           fusion is halted.

        .. data:: ACCONLY_MODE

           In this mode, the BNO055 behaves like a stand-alone acceleration sensor. In this mode the
           other sensors (magnetometer, gyro) are suspended to lower the power consumption.

        .. data:: MAGONLY_MODE

           In MAGONLY mode, the BNO055 behaves like a stand-alone magnetometer, with acceleration
           sensor and gyroscope being suspended.

        .. data:: GYRONLY_MODE

           In GYROONLY mode, the BNO055 behaves like a stand-alone gyroscope, with acceleration
           sensor and magnetometer being suspended.

        .. data:: ACCMAG_MODE

           Both accelerometer and magnetometer are switched on, the user can read the data from
           these two sensors.

        .. data:: ACCGYRO_MODE

           Both accelerometer and gyroscope are switched on; the user can read the data from these
           two sensors.

        .. data:: MAGGYRO_MODE

           Both magnetometer and gyroscope are switched on, the user can read the data from these
           two sensors.

        .. data:: AMG_MODE

           All three sensors accelerometer, magnetometer and gyroscope are switched on.

        .. data:: IMUPLUS_MODE

           In the IMU mode the relative orientation of the BNO055 in space is calculated from the
           accelerometer and gyroscope data. The calculation is fast (i.e. high output data rate).

        .. data:: COMPASS_MODE

           The COMPASS mode is intended to measure the magnetic earth field and calculate the
           geographic direction.

        .. data:: M4G_MODE

           The M4G mode is similar to the IMU mode, but instead of using the gyroscope signal to
           detect rotation, the changing orientation of the magnetometer in the magnetic field is
           used.

        .. data:: NDOF_FMC_OFF_MODE

           This fusion mode is same as NDOF mode, but with the Fast Magnetometer Calibration turned
           ‘OFF’.

        .. data:: NDOF_MODE

           This is a fusion mode with 9 degrees of freedom where the fused absolute orientation data
           is calculated from accelerometer, gyroscope and the magnetometer.

        """
        return self._read_register(IMU._MODE_REGISTER) & 0b00001111  # Datasheet Table 4-2

    @mode.setter
    def mode(self, new_mode):
        self._write_register(IMU._MODE_REGISTER, IMU.CONFIG_MODE)  # Empirically necessary
        time.sleep(0.02)  # Datasheet table 3.6
        if new_mode != IMU.CONFIG_MODE:
            self._write_register(IMU._MODE_REGISTER, new_mode)
            time.sleep(0.01)  # Table 3.6

    @property
    def calibration_status(self):
        """Tuple containing sys, gyro, accel, and mag calibration data."""
        calibration_data = self._read_register(IMU._CALIBRATION_REGISTER)
        sys = (calibration_data >> 6) & 0x03
        gyro = (calibration_data >> 4) & 0x03
        accel = (calibration_data >> 2) & 0x03
        mag = calibration_data & 0x03
        return sys, gyro, accel, mag

    @property
    def calibrated(self):
        """Boolean indicating calibration status."""
        sys, gyro, accel, mag = self.calibration_status
        return sys == gyro == accel == mag == 0x03

    @property
    def external_crystal(self):
        """Switches the use of external crystal on or off."""
        last_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        value = self._read_register(IMU._TRIGGER_REGISTER)
        self.mode = last_mode
        return value == 0x80

    @external_crystal.setter
    def use_external_crystal(self, value):
        last_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        self._write_register(IMU._TRIGGER_REGISTER, 0x80 if value else 0x00)
        self.mode = last_mode
        time.sleep(0.01)

    @property
    def temperature(self):
        """Measures the temperature of the chip in degrees Celsius."""
        return self._temperature

    @property
    def _temperature(self):
        raise NotImplementedError("Must be implemented.")

    @property
    def acceleration(self):
        """Gives the raw accelerometer readings, in m/s.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode not in [0x00, 0x02, 0x03, 0x06]:
            return self._acceleration
        return (None, None, None)

    @property
    def _acceleration(self):
        raise NotImplementedError("Must be implemented.")

    @property
    def magnetic(self):
        """Gives the raw magnetometer readings in microteslas.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode not in [0x00, 0x01, 0x03, 0x05, 0x08]:
            return self._magnetic
        return (None, None, None)

    @property
    def _magnetic(self):
        raise NotImplementedError("Must be implemented.")

    @property
    def gyro(self):
        """Gives the raw gyroscope reading in radians per second.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode not in [0x00, 0x01, 0x02, 0x04, 0x09, 0x0A]:
            return self._gyro
        return (None, None, None)

    @property
    def _gyro(self):
        raise NotImplementedError("Must be implemented.")

    @property
    def euler(self):
        """Gives the calculated orientation angles, in degrees.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            return self._euler
        return (None, None, None)

    @property
    def _euler(self):
        raise NotImplementedError("Must be implemented.")

    @property
    def quaternion(self):
        """Gives the calculated orientation as a quaternion.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            return self._quaternion
        return (None, None, None, None)

    @property
    def _quaternion(self):
        raise NotImplementedError("Must be implemented.")

    @property
    def linear_acceleration(self):
        """Returns the linear acceleration, without gravity, in m/s.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            return self._linear_acceleration
        return (None, None, None)

    @property
    def _linear_acceleration(self):
        raise NotImplementedError("Must be implemented.")

    @property
    def gravity(self):
        """Returns the gravity vector, without acceleration in m/s.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            return self._gravity
        return (None, None, None)

    @property
    def _gravity(self):
        raise NotImplementedError("Must be implemented.")

    @property
    def accel_range(self):
        """Switch the accelerometer range and return the new range. Default value: +/- 4g
        See table 3-8 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00000011 & value

    @accel_range.setter
    def accel_range(self, rng=ACCEL_4G):
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        masked_value = 0b11111100 & value
        self._write_register(IMU._ACCEL_CONFIG_REGISTER, masked_value | rng)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    def accel_bandwidth(self):
        """Switch the accelerometer bandwidth and return the new bandwidth. Default value: 62.5 Hz
        See table 3-8 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00011100 & value

    @accel_bandwidth.setter
    def accel_bandwidth(self, bandwidth=ACCEL_62_5HZ):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        masked_value = 0b11100011 & value
        self._write_register(IMU._ACCEL_CONFIG_REGISTER, masked_value | bandwidth)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    def accel_mode(self):
        """Switch the accelerometer mode and return the new mode. Default value: Normal
        See table 3-8 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b11100000 & value

    @accel_mode.setter
    def accel_mode(self, mode=ACCEL_NORMAL_MODE):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        masked_value = 0b00011111 & value
        self._write_register(IMU._ACCEL_CONFIG_REGISTER, masked_value | mode)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    def gyro_range(self):
        """Switch the gyroscope range and return the new range. Default value: 2000 dps
        See table 3-9 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_0_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00000111 & value

    @gyro_range.setter
    def gyro_range(self, rng=GYRO_2000_DPS):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_0_REGISTER)
        masked_value = 0b00111000 & value
        self._write_register(IMU._GYRO_CONFIG_0_REGISTER, masked_value | rng)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    def gyro_bandwidth(self):
        """Switch the gyroscope bandwidth and return the new bandwidth. Default value: 32 Hz
        See table 3-9 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_0_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00111000 & value

    @gyro_bandwidth.setter
    def gyro_bandwidth(self, bandwidth=GYRO_32HZ):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_0_REGISTER)
        masked_value = 0b00000111 & value
        self._write_register(IMU._GYRO_CONFIG_0_REGISTER, masked_value | bandwidth)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    def gyro_mode(self):
        """Switch the gyroscope mode and return the new mode. Default value: Normal
        See table 3-9 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_1_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00000111 & value

    @gyro_mode.setter
    def gyro_mode(self, mode=GYRO_NORMAL_MODE):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_1_REGISTER)
        masked_value = 0b00000000 & value
        self._write_register(IMU._GYRO_CONFIG_1_REGISTER, masked_value | mode)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    def magnet_rate(self):
        """Switch the magnetometer data output rate and return the new rate. Default value: 20Hz
        See table 3-10 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00000111 & value

    @magnet_rate.setter
    def magnet_rate(self, rate=MAGNET_20HZ):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        masked_value = 0b01111000 & value
        self._write_register(IMU._MAGNET_CONFIG_REGISTER, masked_value | rate)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    def magnet_operation_mode(self):
        """Switch the magnetometer operation mode and return the new mode. Default value: Regular
        See table 3-10 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00011000 & value

    @magnet_operation_mode.setter
    def magnet_operation_mode(self, mode=MAGNET_REGULAR_MODE):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        masked_value = 0b01100111 & value
        self._write_register(IMU._MAGNET_CONFIG_REGISTER, masked_value | mode)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    def magnet_mode(self):
        """Switch the magnetometer power mode and return the new mode. Default value: Forced
        See table 3-10 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b01100000 & value

    @magnet_mode.setter
    def magnet_mode(self, mode=MAGNET_FORCEMODE_MODE):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        masked_value = 0b00011111 & value
        self._write_register(IMU._MAGNET_CONFIG_REGISTER, masked_value | mode)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    def _write_register(self, register, value):
        raise NotImplementedError("Must be implemented.")

    def _read_register(self, register):
        raise NotImplementedError("Must be implemented.")

    @property
    def axis_remap(self):
        """Return a tuple with the axis remap register values.

        This will return 6 values with the following meaning:
          - X axis remap (a value of AXIS_REMAP_X, AXIS_REMAP_Y, or AXIS_REMAP_Z.
                          which indicates that the physical X axis of the chip
                          is remapped to a different axis)
          - Y axis remap (see above)
          - Z axis remap (see above)
          - X axis sign (a value of AXIS_REMAP_POSITIVE or AXIS_REMAP_NEGATIVE
                         which indicates if the X axis values should be positive/
                         normal or negative/inverted.  The default is positive.)
          - Y axis sign (see above)
          - Z axis sign (see above)

        Note that the default value, per the datasheet, is NOT P0,
        but rather P1 ()
        """
        # Get the axis remap register value.
        map_config = self._read_register(IMU._AXIS_MAP_CONFIG_REGISTER)
        z = (map_config >> 4) & 0x03
        y = (map_config >> 2) & 0x03
        x = map_config & 0x03
        # Get the axis remap sign register value.
        sign_config = self._read_register(IMU._AXIS_MAP_SIGN_REGISTER)
        x_sign = (sign_config >> 2) & 0x01
        y_sign = (sign_config >> 1) & 0x01
        z_sign = sign_config & 0x01
        # Return the results as a tuple of all 3 values.
        return (x, y, z, x_sign, y_sign, z_sign)

    @axis_remap.setter
    def axis_remap(self, remap):
        """Pass a tuple consisting of x, y, z, x_sign, y-sign, and z_sign.

        Set axis remap for each axis.  The x, y, z parameter values should
        be set to one of AXIS_REMAP_X (0x00), AXIS_REMAP_Y (0x01), or
        AXIS_REMAP_Z (0x02) and will change the BNO's axis to represent another
        axis.  Note that two axises cannot be mapped to the same axis, so the
        x, y, z params should be a unique combination of AXIS_REMAP_X,
        AXIS_REMAP_Y, AXIS_REMAP_Z values.
        The x_sign, y_sign, z_sign values represent if the axis should be
        positive or negative (inverted). See section 3.4 of the datasheet for
        information on the proper settings for each possible orientation of
        the chip.
        """
        x, y, z, x_sign, y_sign, z_sign = remap
        # Switch to configuration mode. Necessary to remap axes
        current_mode = self._read_register(IMU._MODE_REGISTER)
        self.mode = IMU.CONFIG_MODE
        # Set the axis remap register value.
        map_config = 0x00
        map_config |= (z & 0x03) << 4
        map_config |= (y & 0x03) << 2
        map_config |= x & 0x03
        self._write_register(IMU._AXIS_MAP_CONFIG_REGISTER, map_config)
        # Set the axis remap sign register value.
        sign_config = 0x00
        sign_config |= (x_sign & 0x01) << 2
        sign_config |= (y_sign & 0x01) << 1
        sign_config |= z_sign & 0x01
        self._write_register(IMU._AXIS_MAP_SIGN_REGISTER, sign_config)
        # Go back to normal operation mode.
        self._write_register(IMU._MODE_REGISTER, current_mode)

    def getTumble(self):
        """
        Returns tumble taken from gyro and magnetometer, in degrees/s
        :return: (tuple) nested tuple, x,y,z values for gyro and yz rot, xz rot, and xy rot for magnetometer
        """
        interval = .5 #Time interval for magnetometer readings

        gyroValues = self.gyro #read the gyroscope

        magValues = []
        magValues.append(np.array(self.magnetic)) #read the magnetometer
        time.sleep(interval)
        magValues.append(np.array(self.magnetic))

        magV = (magValues[1]-magValues[0])/interval #mag values velocity

        magRot = (degrees(atan(magV[2]/magV[1])), degrees(magV[0]/magV[2]), degrees(atan(magV[1]/magV[0]))) #yz, xz, xy
        #from https://forum.sparkfun.com/viewtopic.php?t=22252

        return (gyroValues, magRot)


class IMU_I2C(IMU):
    """
    Driver for the BNO055 9DOF IMU sensor via I2C.
    """

    _temperature = _ReadOnlyUnaryStruct(0x34, "b")
    _acceleration = _ScaledReadOnlyStruct(0x08, "<hhh", 1 / 100)
    _magnetic = _ScaledReadOnlyStruct(0x0E, "<hhh", 1 / 16)
    _gyro = _ScaledReadOnlyStruct(0x14, "<hhh", 0.001090830782496456)
    _euler = _ScaledReadOnlyStruct(0x1A, "<hhh", 1 / 16)
    _quaternion = _ScaledReadOnlyStruct(0x20, "<hhhh", 1 / (1 << 14))
    _linear_acceleration = _ScaledReadOnlyStruct(0x28, "<hhh", 1 / 100)
    _gravity = _ScaledReadOnlyStruct(0x2E, "<hhh", 1 / 100)

    offsets_accelerometer = _ModeStruct(IMU._OFFSET_ACCEL_REGISTER, "<hhh", IMU.CONFIG_MODE)
    """Calibration offsets for the accelerometer"""
    offsets_magnetometer = _ModeStruct(IMU._OFFSET_MAGNET_REGISTER, "<hhh", IMU.CONFIG_MODE)
    """Calibration offsets for the magnetometer"""
    offsets_gyroscope = _ModeStruct(IMU._OFFSET_GYRO_REGISTER, "<hhh", IMU.CONFIG_MODE)
    """Calibration offsets for the gyroscope"""

    radius_accelerometer = _ModeStruct(IMU._RADIUS_ACCEL_REGISTER, "<h", IMU.CONFIG_MODE)
    """Radius for accelerometer (cm?)"""
    radius_magnetometer = _ModeStruct(IMU._RADIUS_MAGNET_REGISTER, "<h", IMU.CONFIG_MODE)
    """Radius for magnetometer (cm?)"""

    def __init__(self, state_field_registry):
        self.buffer = bytearray(2)
        self.address = 0x28
        self.bus = SMBus(1)
        super().__init__(state_field_registry)

    def _write_register(self, register, value):
        self.buffer[0] = register
        self.buffer[1] = value
        #try:
        result = self.bus.write_i2c_block_data(self.address, self.buffer[0], self.buffer[1:])
        #except:
            #return False
        time.sleep(.1)
        return result

    def _read_register(self, register):
        self.buffer[0] = register
        #try:
        self.bus.write_byte(self.address, self.buffer[0])
        time.sleep(.1)
        self.buffer[1:] = self.bus.read_i2c_block_data(self.address, 0, len(self.buffer)-1)
        #except:
            #return False
        time.sleep(.1)
        return self.buffer[1]
