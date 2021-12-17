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
# from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from micropython import const
from smbus2 import SMBus
import time
import numpy as np
from math import atan2
from math import degrees
from MainControlLoop.lib.exceptions import wrap_errors, IMUError


@wrap_errors(IMUError)
def _twos_comp_to_signed(val, bits):
    # Convert an unsigned integer in 2's compliment form of the specified bit
    # length to its signed integer value and return it.
    if val & (1 << (bits - 1)) != 0:
        return val - (1 << bits)
    return val


@wrap_errors(IMUError)
def _signed_to_twos_comp(val, bits):
    # Convert a signed integer to unsigned int in 2's complement form
    # bits is number of bits, with sign bit
    if val < 0:
        val += (1 << bits)
    return val


class IMU:
    """
    Base class for the BNO055 9DOF IMU sensor.
    """

    # Constants:
    _CHIP_ID = const(0xA0)

    CONFIG_MODE = const(0x00)
    ACCONLY_MODE = const(0x01)
    MAGONLY_MODE = const(0x02)
    GYRONLY_MODE = const(0x03)
    ACCMAG_MODE = const(0x04)
    ACCGYRO_MODE = const(0x05)
    MAGGYRO_MODE = const(0x06)
    AMG_MODE = const(0x07)
    IMUPLUS_MODE = const(0x08)
    COMPASS_MODE = const(0x09)
    M4G_MODE = const(0x0A)
    NDOF_FMC_OFF_MODE = const(0x0B)
    NDOF_MODE = const(0x0C)

    ACCEL_2G = const(0x00)  # For accel_range property
    ACCEL_4G = const(0x01)  # Default
    ACCEL_8G = const(0x02)
    ACCEL_16G = const(0x03)
    ACCEL_7_81HZ = const(0x00)  # For accel_bandwidth property
    ACCEL_15_63HZ = const(0x04)
    ACCEL_31_25HZ = const(0x08)
    ACCEL_62_5HZ = const(0x0C)  # Default
    ACCEL_125HZ = const(0x10)
    ACCEL_250HZ = const(0x14)
    ACCEL_500HZ = const(0x18)
    ACCEL_1000HZ = const(0x1C)
    ACCEL_NORMAL_MODE = const(0x00)  # Default. For accel_mode property
    ACCEL_SUSPEND_MODE = const(0x20)
    ACCEL_LOWPOWER1_MODE = const(0x40)
    ACCEL_STANDBY_MODE = const(0x60)
    ACCEL_LOWPOWER2_MODE = const(0x80)
    ACCEL_DEEPSUSPEND_MODE = const(0xA0)

    GYRO_2000_DPS = const(0x00)  # Default. For gyro_range property
    GYRO_1000_DPS = const(0x01)
    GYRO_500_DPS = const(0x02)
    GYRO_250_DPS = const(0x03)
    GYRO_125_DPS = const(0x04)
    GYRO_523HZ = const(0x00)  # For gyro_bandwidth property
    GYRO_230HZ = const(0x08)
    GYRO_116HZ = const(0x10)
    GYRO_47HZ = const(0x18)
    GYRO_23HZ = const(0x20)
    GYRO_12HZ = const(0x28)
    GYRO_64HZ = const(0x30)
    GYRO_32HZ = const(0x38)  # Default
    GYRO_NORMAL_MODE = const(0x00)  # Default. For gyro_mode property
    GYRO_FASTPOWERUP_MODE = const(0x01)
    GYRO_DEEPSUSPEND_MODE = const(0x02)
    GYRO_SUSPEND_MODE = const(0x03)
    GYRO_ADVANCEDPOWERSAVE_MODE = const(0x04)

    MAGNET_2HZ = const(0x00)  # For magnet_rate property
    MAGNET_6HZ = const(0x01)
    MAGNET_8HZ = const(0x02)
    MAGNET_10HZ = const(0x03)
    MAGNET_15HZ = const(0x04)
    MAGNET_20HZ = const(0x05)  # Default
    MAGNET_25HZ = const(0x06)
    MAGNET_30HZ = const(0x07)
    MAGNET_LOWPOWER_MODE = const(0x00)  # For magnet_operation_mode property
    MAGNET_REGULAR_MODE = const(0x08)  # Default
    MAGNET_ENHANCEDREGULAR_MODE = const(0x10)
    MAGNET_ACCURACY_MODE = const(0x18)
    MAGNET_NORMAL_MODE = const(0x00)  # for magnet_power_mode property
    MAGNET_SLEEP_MODE = const(0x20)
    MAGNET_SUSPEND_MODE = const(0x40)
    MAGNET_FORCEMODE_MODE = const(0x60)  # Default

    _POWER_NORMAL = const(0x00)
    _POWER_LOW = const(0x01)
    _POWER_SUSPEND = const(0x02)

    _MODE_REGISTER = const(0x3D)
    _PAGE_REGISTER = const(0x07)
    _ACCEL_CONFIG_REGISTER = const(0x08)
    _MAGNET_CONFIG_REGISTER = const(0x09)
    _GYRO_CONFIG_0_REGISTER = const(0x0A)
    _GYRO_CONFIG_1_REGISTER = const(0x0B)
    _CALIBRATION_REGISTER = const(0x35)
    _TRIGGER_REGISTER = const(0x3F)
    _POWER_REGISTER = const(0x3E)
    _ID_REGISTER = const(0x00)
    # Axis remap registers and values
    _AXIS_MAP_CONFIG_REGISTER = const(0x41)
    _AXIS_MAP_SIGN_REGISTER = const(0x42)
    AXIS_REMAP_X = const(0x00)
    AXIS_REMAP_Y = const(0x01)
    AXIS_REMAP_Z = const(0x02)
    AXIS_REMAP_POSITIVE = const(0x00)
    AXIS_REMAP_NEGATIVE = const(0x01)

    # Data registers (start, end)
    # X_LSB, X_MSB, Y_LSB, Y_MSB, Z_LSB, Z_MSB

    ACCEL_REGISTER = (0x08, 0x0D)
    MAG_REGISTER = (0x0E, 0x13)
    GYRO_REGISTER = (0x14, 0x19)
    EULER_REGISTER = (0x1A, 0x1F)
    QUATERNION_REGISTER = (0x20, 0x27)
    LIA_REGISTER = (0x28, 0x2D)
    GRAV_REGISTER = (0x2E, 0x33)
    TEMP_REGISTER = 0x34

    # Scales
    ACCEL_SCALE = 1 / 100
    MAG_SCALE = 1 / 16
    GYRO_SCALE = 0.001090830782496456
    EULER_SCALE = 1 / 16
    QUATERNION_SCALE = 1 / (1 << 14)
    LIA_SCALE = 1 / 100
    GRAV_SCALE = 1 / 100

    # Offset registers

    # X_LSB, X_MSB, Y_LSB, Y_MSB, Z_LSB, Z_MSB
    _OFFSET_ACCEL_REGISTER = (0x55, 0x5A)
    _OFFSET_MAGNET_REGISTER = (0x5B, 0x60)
    _OFFSET_GYRO_REGISTER = (0x61, 0x66)

    # LSB, MSB
    _RADIUS_ACCEL_REGISTER = (0x67, 0x68)
    _RADIUS_MAGNET_REGISTER = (0x69, 0x6A)

    @wrap_errors(IMUError)
    def __init__(self, state_field_registry):
        self.sfr = state_field_registry

    @wrap_errors(IMUError)
    def start(self):
        # Start the IMU; MUST BE RUN BEFORE TRYING TO READ ANYTHING
        chip_id = self._read_register(IMU._ID_REGISTER)
        if chip_id != IMU._CHIP_ID:
            raise IMUError(details="bad chip id (%x != %x)" % (chip_id, IMU._CHIP_ID))
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

    @wrap_errors(IMUError)
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
    @wrap_errors(IMUError)
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
    @wrap_errors(IMUError)
    def mode(self, new_mode):
        self._write_register(IMU._MODE_REGISTER, IMU.CONFIG_MODE)  # Empirically necessary
        time.sleep(0.02)  # Datasheet table 3.6
        if new_mode != IMU.CONFIG_MODE:
            self._write_register(IMU._MODE_REGISTER, new_mode)
            time.sleep(0.01)  # Table 3.6

    @wrap_errors(IMUError)
    def get_tup_data(self, registers, scale):
        """gets and returns xyz tuple data from corresponding register range, with scale multiplied"""
        raw = []
        for addr in range(*registers, 2):
            lsb = self._read_register(addr)
            msb = self._read_register(addr + 1)
            raw.append(_twos_comp_to_signed(lsb + (msb << 8), 16))
        return tuple(np.array(raw) * scale)

    @wrap_errors(IMUError)
    def write_tup_data(self, tup, registers, scale):
        """sets xyz tuple data from register range, dividing by scale"""
        i = 0
        for addr in range(*registers, 2):
            raw = _signed_to_twos_comp(int(tup[i] / scale), 16)
            msb = (raw >> 8) & 0xff
            lsb = raw & 0xff
            self._write_register(addr, lsb)
            self._write_register(addr + 1, msb)

    @property
    @wrap_errors(IMUError)
    def calibration_status(self):
        """Tuple containing sys, gyro, accel, and mag calibration data."""
        calibration_data = self._read_register(IMU._CALIBRATION_REGISTER)
        sys = (calibration_data >> 6) & 0x03
        gyro = (calibration_data >> 4) & 0x03
        accel = (calibration_data >> 2) & 0x03
        mag = calibration_data & 0x03
        return sys, gyro, accel, mag

    @property
    @wrap_errors(IMUError)
    def calibrated(self):
        """Boolean indicating calibration status."""
        sys, gyro, accel, mag = self.calibration_status
        return sys == gyro == accel == mag == 0x03

    # Calibration offsets for accelerometer
    @property
    @wrap_errors(IMUError)
    def offsets_accelerometer(self):
        old_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        result = self.get_tup_data(IMU._OFFSET_ACCEL_REGISTER, IMU.ACCEL_SCALE)
        self.mode = old_mode
        return result

    @offsets_accelerometer.setter
    @wrap_errors(IMUError)
    def offsets_accelerometer(self, new_offsets):
        old_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        self.write_tup_data(new_offsets, IMU._OFFSET_ACCEL_REGISTER, IMU.ACCEL_SCALE)
        self.mode = old_mode

    # Calibration offsets for the magnetometer
    @property
    @wrap_errors(IMUError)
    def offsets_magnetometer(self):
        old_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        result = self.get_tup_data(IMU._OFFSET_MAGNET_REGISTER, 1)
        self.mode = old_mode
        return result

    @offsets_magnetometer.setter
    @wrap_errors(IMUError)
    def offsets_magnetometer(self, new_offsets):
        old_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        self.write_tup_data(new_offsets, IMU._OFFSET_MAGNET_REGISTER, IMU.MAG_SCALE)
        self.mode = old_mode

    # Calibration offsets for the gyroscope
    @property
    @wrap_errors(IMUError)
    def offsets_gyroscope(self):
        old_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        result = self.get_tup_data(IMU._OFFSET_GYRO_REGISTER, 1)
        self.mode = old_mode
        return result

    @offsets_gyroscope.setter
    @wrap_errors(IMUError)
    def offsets_gyroscope(self, new_offsets):
        old_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        self.write_tup_data(new_offsets, IMU._OFFSET_GYRO_REGISTER, IMU.GYRO_SCALE)
        self.mode = old_mode

    # Radius for accelerometer (cm?)
    @property
    @wrap_errors(IMUError)
    def radius_accelerometer(self):
        old_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        lsb = self._read_register(IMU._RADIUS_ACCEL_REGISTER[0])
        msb = self._read_register(IMU._RADIUS_ACCEL_REGISTER[1])
        self.mode = old_mode
        data = _twos_comp_to_signed(lsb + (msb << 8), 16)
        return data

    @radius_accelerometer.setter
    @wrap_errors(IMUError)
    def radius_accelerometer(self, new_rad):
        old_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        raw = _signed_to_twos_comp(new_rad, 16)
        msb = (raw >> 8) & 0xff
        lsb = raw & 0xff
        self._write_register(IMU._RADIUS_ACCEL_REGISTER[0], lsb)
        self._write_register(IMU._RADIUS_ACCEL_REGISTER[1], msb)
        self.mode = old_mode

    # Radius for magnetometer (cm?)
    @property
    @wrap_errors(IMUError)
    def radius_magnetometer(self):
        old_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        lsb = self._read_register(IMU._RADIUS_MAGNET_REGISTER[0])
        msb = self._read_register(IMU._RADIUS_MAGNET_REGISTER[1])
        self.mode = old_mode
        data = _twos_comp_to_signed(lsb + (msb << 8), 16)
        return data

    @radius_magnetometer.setter
    @wrap_errors(IMUError)
    def radius_magnetometer(self, new_rad):
        old_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        raw = _signed_to_twos_comp(new_rad, 16)
        msb = (raw >> 8) & 0xff
        lsb = raw & 0xff
        self._write_register(IMU._RADIUS_MAGNET_REGISTER[0], lsb)
        self._write_register(IMU._RADIUS_MAGNET_REGISTER[1], msb)
        self.mode = old_mode

    @property
    @wrap_errors(IMUError)
    def external_crystal(self):
        """Switches the use of external crystal on or off."""
        last_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        value = self._read_register(IMU._TRIGGER_REGISTER)
        self.mode = last_mode
        return value == 0x80

    @external_crystal.setter
    @wrap_errors(IMUError)
    def use_external_crystal(self, value):
        last_mode = self.mode
        self.mode = IMU.CONFIG_MODE
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        self._write_register(IMU._TRIGGER_REGISTER, 0x80 if value else 0x00)
        self.mode = last_mode
        time.sleep(0.01)

    @property
    @wrap_errors(IMUError)
    def temperature(self):
        """Measures the temperature of the chip in degrees Celsius."""
        return self._temperature

    @property
    @wrap_errors(IMUError)
    def _temperature(self):
        # return _twos_comp_to_signed(self._read_register(IMU.TEMP_REGISTER), 8)
        return self._read_register(IMU.TEMP_REGISTER)

    @property
    @wrap_errors(IMUError)
    def acceleration(self):
        """Gives the raw accelerometer readings, in m/s.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode not in [0x00, 0x02, 0x03, 0x06]:
            return self._acceleration
        return (None, None, None)

    @property
    @wrap_errors(IMUError)
    def _acceleration(self):
        return self.get_tup_data(IMU.ACCEL_REGISTER, IMU.ACCEL_SCALE)

    @property
    @wrap_errors(IMUError)
    def magnetic(self):
        """Gives the raw magnetometer readings in microteslas.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode not in [0x00, 0x01, 0x03, 0x05, 0x08]:
            return self._magnetic
        return (None, None, None)

    @property
    @wrap_errors(IMUError)
    def _magnetic(self):
        return self.get_tup_data(IMU.MAG_REGISTER, IMU.MAG_SCALE)

    @property
    @wrap_errors(IMUError)
    def gyro(self):
        """Gives the raw gyroscope reading in radians per second.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode not in [0x00, 0x01, 0x02, 0x04, 0x09, 0x0A]:
            return self._gyro
        return (None, None, None)

    @property
    @wrap_errors(IMUError)
    def _gyro(self):
        return self.get_tup_data(IMU.GYRO_REGISTER, IMU.GYRO_SCALE)

    @property
    @wrap_errors(IMUError)
    def euler(self):
        """Gives the calculated orientation angles, in degrees.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            return self._euler
        return (None, None, None)

    @property
    @wrap_errors(IMUError)
    def _euler(self):
        return self.get_tup_data(IMU.EULER_REGISTER, IMU.EULER_SCALE)

    @property
    @wrap_errors(IMUError)
    def quaternion(self):
        """Gives the calculated orientation as a quaternion.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            return self._quaternion
        return (None, None, None, None)

    @property
    @wrap_errors(IMUError)
    def _quaternion(self):
        return self.get_tup_data(IMU.QUATERNION_REGISTER, IMU.QUATERNION_SCALE)

    @property
    @wrap_errors(IMUError)
    def linear_acceleration(self):
        """Returns the linear acceleration, without gravity, in m/s.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            return self._linear_acceleration
        return (None, None, None)

    @property
    @wrap_errors(IMUError)
    def _linear_acceleration(self):
        return self.get_tup_data(IMU.LIA_REGISTER, IMU.LIA_SCALE)

    @property
    @wrap_errors(IMUError)
    def gravity(self):
        """Returns the gravity vector, without acceleration in m/s.
        Returns an empty tuple of length 3 when this property has been disabled by the current mode.
        """
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            return self._gravity
        return (None, None, None)

    @property
    @wrap_errors(IMUError)
    def _gravity(self):
        return self.get_tup_data(IMU.GRAV_REGISTER, IMU.GRAV_SCALE)

    @property
    @wrap_errors(IMUError)
    def accel_range(self):
        """Switch the accelerometer range and return the new range. Default value: +/- 4g
        See table 3-8 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00000011 & value

    @accel_range.setter
    @wrap_errors(IMUError)
    def accel_range(self, rng=ACCEL_4G):
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        masked_value = 0b11111100 & value
        self._write_register(IMU._ACCEL_CONFIG_REGISTER, masked_value | rng)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    @wrap_errors(IMUError)
    def accel_bandwidth(self):
        """Switch the accelerometer bandwidth and return the new bandwidth. Default value: 62.5 Hz
        See table 3-8 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00011100 & value

    @accel_bandwidth.setter
    @wrap_errors(IMUError)
    def accel_bandwidth(self, bandwidth=ACCEL_62_5HZ):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        masked_value = 0b11100011 & value
        self._write_register(IMU._ACCEL_CONFIG_REGISTER, masked_value | bandwidth)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    @wrap_errors(IMUError)
    def accel_mode(self):
        """Switch the accelerometer mode and return the new mode. Default value: Normal
        See table 3-8 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b11100000 & value

    @accel_mode.setter
    @wrap_errors(IMUError)
    def accel_mode(self, mode=ACCEL_NORMAL_MODE):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._ACCEL_CONFIG_REGISTER)
        masked_value = 0b00011111 & value
        self._write_register(IMU._ACCEL_CONFIG_REGISTER, masked_value | mode)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    @wrap_errors(IMUError)
    def gyro_range(self):
        """Switch the gyroscope range and return the new range. Default value: 2000 dps
        See table 3-9 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_0_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00000111 & value

    @gyro_range.setter
    @wrap_errors(IMUError)
    def gyro_range(self, rng=GYRO_2000_DPS):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_0_REGISTER)
        masked_value = 0b00111000 & value
        self._write_register(IMU._GYRO_CONFIG_0_REGISTER, masked_value | rng)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    @wrap_errors(IMUError)
    def gyro_bandwidth(self):
        """Switch the gyroscope bandwidth and return the new bandwidth. Default value: 32 Hz
        See table 3-9 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_0_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00111000 & value

    @gyro_bandwidth.setter
    @wrap_errors(IMUError)
    def gyro_bandwidth(self, bandwidth=GYRO_32HZ):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_0_REGISTER)
        masked_value = 0b00000111 & value
        self._write_register(IMU._GYRO_CONFIG_0_REGISTER, masked_value | bandwidth)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    @wrap_errors(IMUError)
    def gyro_mode(self):
        """Switch the gyroscope mode and return the new mode. Default value: Normal
        See table 3-9 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_1_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00000111 & value

    @gyro_mode.setter
    @wrap_errors(IMUError)
    def gyro_mode(self, mode=GYRO_NORMAL_MODE):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._GYRO_CONFIG_1_REGISTER)
        masked_value = 0b00000000 & value
        self._write_register(IMU._GYRO_CONFIG_1_REGISTER, masked_value | mode)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    @wrap_errors(IMUError)
    def magnet_rate(self):
        """Switch the magnetometer data output rate and return the new rate. Default value: 20Hz
        See table 3-10 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00000111 & value

    @magnet_rate.setter
    @wrap_errors(IMUError)
    def magnet_rate(self, rate=MAGNET_20HZ):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        masked_value = 0b01111000 & value
        self._write_register(IMU._MAGNET_CONFIG_REGISTER, masked_value | rate)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    @wrap_errors(IMUError)
    def magnet_operation_mode(self):
        """Switch the magnetometer operation mode and return the new mode. Default value: Regular
        See table 3-10 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b00011000 & value

    @magnet_operation_mode.setter
    @wrap_errors(IMUError)
    def magnet_operation_mode(self, mode=MAGNET_REGULAR_MODE):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        masked_value = 0b01100111 & value
        self._write_register(IMU._MAGNET_CONFIG_REGISTER, masked_value | mode)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @property
    @wrap_errors(IMUError)
    def magnet_mode(self):
        """Switch the magnetometer power mode and return the new mode. Default value: Forced
        See table 3-10 in the datasheet.
        """
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        self._write_register(IMU._PAGE_REGISTER, 0x00)
        return 0b01100000 & value

    @magnet_mode.setter
    @wrap_errors(IMUError)
    def magnet_mode(self, mode=MAGNET_FORCEMODE_MODE):
        if self.mode in [0x08, 0x09, 0x0A, 0x0B, 0x0C]:
            raise RuntimeError("Mode must not be a fusion mode")
        self._write_register(IMU._PAGE_REGISTER, 0x01)
        value = self._read_register(IMU._MAGNET_CONFIG_REGISTER)
        masked_value = 0b00011111 & value
        self._write_register(IMU._MAGNET_CONFIG_REGISTER, masked_value | mode)
        self._write_register(IMU._PAGE_REGISTER, 0x00)

    @wrap_errors(IMUError)
    def _write_register(self, register, value):
        raise NotImplementedError("Must be implemented.")

    @wrap_errors(IMUError)
    def _read_register(self, register):
        raise NotImplementedError("Must be implemented.")

    @property
    @wrap_errors(IMUError)
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
    @wrap_errors(IMUError)
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

    @wrap_errors(IMUError)
    def get_tumble(self):
        """
        Returns tumble taken from gyro and magnetometer, in degrees/s
        :return: (tuple) nested tuple, x,y,z values for gyro and yz rot, xz rot, and xy rot for magnetometer
        """
        interval = .5  # Time interval for magnetometer readings

        temp = np.array(self.gyro)
        time.sleep(.05)
        gyroValues = tuple((np.array(self.gyro) - temp) / 2)  # read the gyroscope, two readings

        magValues = []
        magValues.append(np.array(self.magnetic))  # read the magnetometer
        time.sleep(interval)
        magValues.append(np.array(self.magnetic))

        magV = (magValues[1] - magValues[0]) / interval  # mag values velocity

        magRot = (degrees(atan2(magV[2] , magV[1])), degrees(atan2(magV[0] , magV[2])), degrees(atan2(magV[1] , magV[0])))  # yz, xz, xy
        # from https://forum.sparkfun.com/viewtopic.php?t=22252

        return (gyroValues, magRot)

    @wrap_errors(IMUError)
    def is_tumbling(self) -> bool:
        """Checks if sat is tumbling. If is tumbling returns True, else returns False"""
        df = self.sfr.logs["imu"].read().tail(5)
        x_tumble_values = df["xgyro"].values.tolist()
        y_tumble_values = df["ygyro"].values.tolist()
        x_tumble_avg = sum(x_tumble_values)/len(x_tumble_values)
        y_tumble_avg = sum(y_tumble_values)/len(y_tumble_values)
        return x_tumble_avg > self.sfr.DETUMBLE_THRESHOLD or y_tumble_avg > self.sfr.DETUMBLE_THRESHOLD


class IMU_I2C(IMU):
    """
    Driver for the BNO055 9DOF IMU sensor via I2C.
    """

    @wrap_errors(IMUError)
    def __init__(self, state_field_registry=None, addr=0x28):
        self.buffer = bytearray(2)
        self.address = addr
        self.bus = SMBus(1)
        super().__init__(state_field_registry)

    @wrap_errors(IMUError)
    def _write_register(self, register, value):
        self.buffer[0] = register
        self.buffer[1] = value
        result = self.bus.write_byte_data(self.address, self.buffer[0], self.buffer[1])
        time.sleep(.02)
        return result

    @wrap_errors(IMUError)
    def _read_register(self, register):
        self.buffer[0] = register
        self.bus.write_byte(self.address, self.buffer[0])
        time.sleep(.01)
        self.buffer[1] = self.bus.read_byte(self.address)
        time.sleep(.01)
        return self.buffer[1]
