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

def _twos_comp(val, bits):
    # Convert an unsigned integer in 2's compliment form of the specified bit
    # length to its signed integer value and return it.
    if val & (1 << (bits - 1)) != 0:
        return val - (1 << bits)
    return val

class IMU:
    """
    Class for LSM9DS1 IMU Breakout Board
    Referenced from https://github.com/adafruit/Adafruit_CircuitPython_LSM9DS1/blob/main/adafruit_lsm9ds1.py
    """

    #USER FACING CONSTANTS
    ACCELRANGE_2G: bin = 0b00 << 3
    ACCELRANGE_16G: bin = 0b01 << 3
    ACCELRANGE_4G: bin = 0b10 << 3
    ACCELRANGE_8G: bin = 0b11 << 3
    MAGGAIN_4GAUSS: bin = 0b00 << 5 #+/- 4 gauss
    MAGGAIN_8GAUSS: bin = 0b01 << 5 #+/- 8 gauss
    MAGGAIN_12GAUSS: bin = 0b10 << 5 #+/- 12 gauss
    MAGGAIN_16GAUSS: bin = 0b11 << 5 #+/- 16 gauss
    GYROSCALE_245DPS: bin = 0b00 << 3 #+/- 245 degrees/s rotation
    GYROSCALE_500DPS: bin = 0b01 << 3 #+/- 500 degrees/s rotation
    GYROSCALE_2000DPS: bin = 0b11 << 3 #+/- 2000 degrees/s rotation

    #INTERNAL CONSTANTS
    ADDRESS_ACCELGYRO: hex = 0x6B
    ADDRESS_MAG: hex = 0x1E
    XG_ID: bin = 0b01101000
    MAG_ID: bin = 0b00111101
    ACCEL_MG_LSB_2G = 0.061
    ACCEL_MG_LSB_4G = 0.122
    ACCEL_MG_LSB_8G = 0.244
    ACCEL_MG_LSB_16G = 0.732
    MAG_MGAUSS_4GAUSS = 0.14
    MAG_MGAUSS_8GAUSS = 0.29
    MAG_MGAUSS_12GAUSS = 0.43
    MAG_MGAUSS_16GAUSS = 0.58
    GYRO_DPS_DIGIT_245DPS = 0.00875
    GYRO_DPS_DIGIT_500DPS = 0.01750
    GYRO_DPS_DIGIT_2000DPS = 0.07000
    TEMP_LSB_CELSIUS = 8 #1C = 8, 25C = 200, etc.
    REGISTER_WHOAMI_XG: hex = 0x0F
    REGISTER_CTRL_REG1_G: hex = 0x10
    REGISTER_CTRL_REG2_G: hex = 0x11
    REGISTER_CTRL_REG3_G: hex = 0x12
    REGISTER_TEMP_OUT_L: hex = 0x15
    REGISTER_TEMP_OUT_H: hex = 0x16
    REGISTER_STATUS_REG: hex = 0x17
    REGISTER_OUT_XLG: hex = 0x18
    REGISTER_OUT_XHG: hex = 0x19
    REGISTER_OUT_YLG: hex = 0x1A
    REGISTER_OUT_YHG: hex = 0x1B
    REGISTER_OUT_ZLG: hex = 0x1C
    REGISTER_OUT_ZHG: hex = 0x1D
    REGISTER_CTRL_REG4: hex = 0x1E
    REGISTER_CTRL_REG5_XL: hex = 0x1F
    REGISTER_CTRL_REG6_XL: hex = 0x20
    REGISTER_CTRL_REG7_XL: hex = 0x21
    REGISTER_CTRL_REG8: hex = 0x22
    REGISTER_CTRL_REG9: hex = 0x23
    REGISTER_CTRL_REG10: hex = 0x24
    REGISTER_OUT_XLXL: hex = 0x28
    REGISTER_OUT_XHXL: hex = 0x29
    REGISTER_OUT_YLXL: hex = 0x2A
    REGISTER_OUT_YHXL: hex = 0x2B
    REGISTER_OUT_ZLXL: hex = 0x2C
    REGISTER_OUT_ZHXL: hex = 0x2D
    REGISTER_WHOAMI_M: hex = 0x0F
    REGISTER_CTRL_REG1_M: hex = 0x20
    REGISTER_CTRL_REG2_M: hex = 0x21
    REGISTER_CTRL_REG3_M: hex = 0x22
    REGISTER_CTRL_REG4_M: hex = 0x23
    REGISTER_CTRL_REG5_M: hex = 0x24
    REGISTER_STATUS_REG_M: hex = 0x27
    REGISTER_OUT_XLM: hex = 0x28
    REGISTER_OUT_XHM: hex = 0x29
    REGISTER_OUT_YLM: hex = 0x2A
    REGISTER_OUT_YHM: hex = 0x2B
    REGISTER_OUT_ZLM: hex = 0x2C
    REGISTER_OUT_ZHM: hex = 0x2D
    REGISTER_CFG_M: hex = 0x30
    REGISTER_INT_SRC_M: hex = 0x31
    MAGTYPE = True
    XGTYPE = False
    SENSORS_GRAVITY_STANDARD = 9.80665
    SPI_AUTO_INCR: hex = 0x40

    def __init__(self, state_field_registry):
        self.sfr = state_field_registry
        # soft reset & reboot accel/gyro
        self._write_u8(IMU.XGTYPE, IMU.REGISTER_CTRL_REG8, 0x05)
        # soft reset & reboot magnetometer
        self._write_u8(IMU.MAGTYPE, IMU.REGISTER_CTRL_REG2_M, 0x0C)
        time.sleep(0.01)
        # Check ID registers.
        if (
            self._read_u8(IMU.XGTYPE, IMU.REGISTER_WHOAMI_XG) != IMU.XG_ID
            or self._read_u8(IMU.MAGTYPE, IMU.REGISTER_WHOAMI_M) != IMU.MAG_ID
        ):
            raise RuntimeError("Could not find LSM9DS1, check wiring!")
        # enable gyro continuous
        self._write_u8(IMU.XGTYPE, IMU.REGISTER_CTRL_REG1_G, 0xC0)  # on XYZ
        # Enable the accelerometer continous
        self._write_u8(IMU.XGTYPE, IMU.REGISTER_CTRL_REG5_XL, 0x38)
        self._write_u8(IMU.XGTYPE, IMU.REGISTER_CTRL_REG6_XL, 0xC0)
        # enable mag continuous
        self._write_u8(IMU.MAGTYPE, IMU.REGISTER_CTRL_REG3_M, 0x00)
        # Set default ranges for the various sensors
        self._accel_mg_lsb = None
        self._mag_mgauss_lsb = None
        self._gyro_dps_digit = None
        self.accel_range = IMU.ACCELRANGE_2G
        self.mag_gain = IMU.MAGGAIN_4GAUSS
        self.gyro_scale = IMU.GYROSCALE_245DPS
    
    def accel_range(self):
        """The accelerometer range.  Must be a value of:
        - ACCELRANGE_2G
        - ACCELRANGE_4G
        - ACCELRANGE_8G
        - ACCELRANGE_16G
        """
        reg = self._read_u8(IMU.XGTYPE, IMU.REGISTER_CTRL_REG6_XL)
        return (reg & 0b00011000) & 0xFF

    def accel_range(self, val):
        assert val in (IMU.ACCELRANGE_2G, IMU.ACCELRANGE_4G, IMU.ACCELRANGE_8G, IMU.ACCELRANGE_16G)
        reg = self._read_u8(IMU.XGTYPE, IMU.REGISTER_CTRL_REG6_XL)
        reg = (reg & ~(0b00011000)) & 0xFF
        reg |= val
        self._write_u8(IMU.XGTYPE, IMU.REGISTER_CTRL_REG6_XL, reg)
        if val == IMU.ACCELRANGE_2G:
            self._accel_mg_lsb = IMU.ACCEL_MG_LSB_2G
        elif val == IMU.ACCELRANGE_4G:
            self._accel_mg_lsb = IMU.ACCEL_MG_LSB_4G
        elif val == IMU.ACCELRANGE_8G:
            self._accel_mg_lsb = IMU.ACCEL_MG_LSB_8G
        elif val == IMU.ACCELRANGE_16G:
            self._accel_mg_lsb = IMU.ACCEL_MG_LSB_16G
    
    def mag_gain(self):
        """The magnetometer gain.  Must be a value of:
        - MAGGAIN_4GAUSS
        - MAGGAIN_8GAUSS
        - MAGGAIN_12GAUSS
        - MAGGAIN_16GAUSS
        """
        reg = self._read_u8(IMU.MAGTYPE, IMU.REGISTER_CTRL_REG2_M)
        return (reg & 0b01100000) & 0xFF

    def mag_gain(self, val):
        assert val in (IMU.MAGGAIN_4GAUSS, IMU.MAGGAIN_8GAUSS, IMU.MAGGAIN_12GAUSS, IMU.MAGGAIN_16GAUSS)
        reg = self._read_u8(IMU.MAGTYPE, IMU.REGISTER_CTRL_REG2_M)
        reg = (reg & ~(0b01100000)) & 0xFF
        reg |= val
        self._write_u8(IMU.MAGTYPE, IMU.REGISTER_CTRL_REG2_M, reg)
        if val == IMU.MAGGAIN_4GAUSS:
            self._mag_mgauss_lsb = IMU.MAG_MGAUSS_4GAUSS
        elif val == IMU.MAGGAIN_8GAUSS:
            self._mag_mgauss_lsb = IMU.MAG_MGAUSS_8GAUSS
        elif val == IMU.MAGGAIN_12GAUSS:
            self._mag_mgauss_lsb = IMU.MAG_MGAUSS_12GAUSS
        elif val == IMU.MAGGAIN_16GAUSS:
            self._mag_mgauss_lsb = IMU.MAG_MGAUSS_16GAUSS

    def gyro_scale(self):
        """The gyroscope scale.  Must be a value of:
        * GYROSCALE_245DPS
        * GYROSCALE_500DPS
        * GYROSCALE_2000DPS
        """
        reg = self._read_u8(IMU.XGTYPE, IMU.REGISTER_CTRL_REG1_G)
        return (reg & 0b00011000) & 0xFF

    def gyro_scale(self, val):
        assert val in (IMU.GYROSCALE_245DPS, IMU.GYROSCALE_500DPS, IMU.GYROSCALE_2000DPS)
        reg = self._read_u8(IMU.XGTYPE, IMU.REGISTER_CTRL_REG1_G)
        reg = (reg & ~(0b00011000)) & 0xFF
        reg |= val
        self._write_u8(IMU.XGTYPE, IMU.REGISTER_CTRL_REG1_G, reg)
        if val == IMU.GYROSCALE_245DPS:
            self._gyro_dps_digit = IMU.GYRO_DPS_DIGIT_245DPS
        elif val == IMU.GYROSCALE_500DPS:
            self._gyro_dps_digit = IMU.GYRO_DPS_DIGIT_500DPS
        elif val == IMU.GYROSCALE_2000DPS:
            self._gyro_dps_digit = IMU.GYRO_DPS_DIGIT_2000DPS

    def read_accel_raw(self):
        """Read the raw accelerometer sensor values and return it as a
        3-tuple of X, Y, Z axis values that are 16-bit unsigned values.  If you
        want the acceleration in nice units you probably want to use the
        accelerometer property!
        """
        # Read the accelerometer
        self._read_bytes(IMU.XGTYPE, 0x80 | IMU.REGISTER_OUT_XLXL, 6, self._BUFFER)
        raw_x, raw_y, raw_z = struct.unpack_from("<hhh", self._BUFFER[0:6])
        return (raw_x, raw_y, raw_z)

    def acceleration(self):
        """The accelerometer X, Y, Z axis values as a 3-tuple of
        :math:`m/s^2` values.
        """
        raw = self.read_accel_raw()
        return map(
            lambda x: x * self._accel_mg_lsb / 1000.0 * IMU.SENSORS_GRAVITY_STANDARD, raw
        )

    def read_mag_raw(self):
        """Read the raw magnetometer sensor values and return it as a
        3-tuple of X, Y, Z axis values that are 16-bit unsigned values.  If you
        want the magnetometer in nice units you probably want to use the
        magnetometer property!
        """
        # Read the magnetometer
        self._read_bytes(IMU.MAGTYPE, 0x80 | IMU.REGISTER_OUT_X_L_M, 6, self._BUFFER)
        raw_x, raw_y, raw_z = struct.unpack_from("<hhh", self._BUFFER[0:6])
        return (raw_x, raw_y, raw_z)
    
    def magnetic(self):
        """The magnetometer X, Y, Z axis values as a 3-tuple of
        gauss values.
        """
        raw = self.read_mag_raw()
        return map(lambda x: x * self._mag_mgauss_lsb / 1000.0, raw)

    def read_gyro_raw(self):
        """Read the raw gyroscope sensor values and return it as a
        3-tuple of X, Y, Z axis values that are 16-bit unsigned values.  If you
        want the gyroscope in nice units you probably want to use the
        gyroscope property!
        """
        # Read the gyroscope
        self._read_bytes(IMU.XGTYPE, 0x80 | IMU.REGISTER_OUT_X_L_G, 6, self._BUFFER)
        raw_x, raw_y, raw_z = struct.unpack_from("<hhh", self._BUFFER[0:6])
        return (raw_x, raw_y, raw_z)

    def gyro(self):
        """The gyroscope X, Y, Z axis values as a 3-tuple of
        rad/s values.
        """
        raw = self.read_gyro_raw()
        return map(lambda x: radians(x * self._gyro_dps_digit), raw)

    def read_temp_raw(self):
        """Read the raw temperature sensor value and return it as a 12-bit
        signed value.  If you want the temperature in nice units you probably
        want to use the temperature property!
        """
        # Read temp sensor
        self._read_bytes(IMU.XGTYPE, 0x80 | IMU.REGISTER_TEMP_OUT_L, 2, self._BUFFER)
        temp = ((self._BUFFER[1] << 8) | self._BUFFER[0]) >> 4
        return _twos_comp(temp, 12)

    def temperature(self):
        """The temperature of the sensor in degrees Celsius."""
        # This is just a guess since the starting point (21C here) isn't documented :(
        # See discussion from:
        #  https://github.com/kriswiner/LSM9DS1/issues/3
        temp = self.read_temp_raw()
        temp = 27.5 + temp / 16
        return temp

    def _read_u8(self, sensor_type, address):
        # Read an 8-bit unsigned value from the specified 8-bit address.
        # The sensor_type boolean should be _MAGTYPE when talking to the
        # magnetometer, or _XGTYPE when talking to the accel or gyro.
        # MUST be implemented by subclasses!
        raise NotImplementedError()

    def _read_bytes(self, sensor_type, address, count, buf):
        # Read a count number of bytes into buffer from the provided 8-bit
        # register address.  The sensor_type boolean should be _MAGTYPE when
        # talking to the magnetometer, or _XGTYPE when talking to the accel or
        # gyro.  MUST be implemented by subclasses!
        raise NotImplementedError()

    def _write_u8(self, sensor_type, address, val):
        # Write an 8-bit unsigned value to the specified 8-bit address.
        # The sensor_type boolean should be _MAGTYPE when talking to the
        # magnetometer, or _XGTYPE when talking to the accel or gyro.
        # MUST be implemented by subclasses!
        raise NotImplementedError()

class LSM9DS1_I2C(IMU):
    """Driver for the LSM9DS1 connect over I2C.
    :param ~busio.I2C i2c: The I2C bus the device is connected to
    :param int mag_address: A 8-bit integer that represents the i2c address of the
        LSM9DS1's magnetometer. Options are limited to :const:`0x1C` or :const:`0x1E`
        Defaults to :const:`0x1E`.
    :param int xg_address: A 8-bit integer that represents the i2c address of the
        LSM9DS1's accelerometer and gyroscope. Options are limited to :const:`0x6A`
        or :const:`0x6B`. Defaults to :const:`0x6B`.
    **Quickstart: Importing and using the device**
        Here is an example of using the :class:`LSM9DS1` class.
        First you will need to import the libraries to use the sensor
        .. code-block:: python
            import board
            import adafruit_lsm9ds1
        Once this is done you can define your `board.I2C` object and define your sensor object
        .. code-block:: python
            i2c = board.I2C()  # uses board.SCL and board.SDA
            sensor = adafruit_lsm9ds1.LSM9DS1_I2C(i2c)
        Now you have access to the :attr:`acceleration`, :attr:`magnetic`
        :attr:`gyro` and :attr:`temperature` attributes
        .. code-block:: python
            acc_x, acc_y, acc_z = sensor.acceleration
            mag_x, mag_y, mag_z = sensor.magnetic
            gyro_x, gyro_y, gyro_z = sensor.gyro
            temp = sensor.temperature
    """

    def __init__(
        self,
        i2c,
        mag_address=IMU.ADDRESS_MAG,
        xg_address=IMU.ADDRESS_ACCELGYRO,
    ):
        if mag_address in (0x1C, 0x1E) and xg_address in (0x6A, 0x6B):
            self.mag_address = mag_address
            self.xg_address = xg_address
            super().__init__()
        else:
            raise ValueError(
                "address parmeters are incorrect. Read the docs at "
                "circuitpython.rtfd.io/projects/lsm9ds1/en/latest"
                "/api.html#adafruit_lsm9ds1.LSM9DS1_I2C"
            )

    def _read_u8(self, sensor_type, address):
        if sensor_type == IMU.MAGTYPE:
            device = self.mag_address
        else:
            device = self.xg_address
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(device, address&0xFF, [0x00]) #will this work? no idea
            time.sleep(.25)
            result = bus.read_i2c_block_data(device, 0, 2)
            time.sleep(.25) 

        """with device as i2c:
            self._BUFFER[0] = address & 0xFF
            i2c.write_then_readinto(
                self._BUFFER, self._BUFFER, out_end=1, in_start=1, in_end=2
            )
        return self._BUFFER[1]"""

    def _read_bytes(self, sensor_type, address, count, buf):
        if sensor_type == IMU.MAGTYPE:
            device = self.mag_address
        else:
            device = self.xg_address
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(device, address&0xFF, [0x00]) #will this work? no idea
            time.sleep(.25)
        
        with device as i2c:
            buf[0] = address & 0xFF
            i2c.write_then_readinto(buf, buf, out_end=1, in_end=count)

    def _write_u8(self, sensor_type, address, val):
        if sensor_type == IMU.MAGTYPE:
            device = self._mag_device
        else:
            device = self._xg_device
        with device as i2c:
            self._BUFFER[0] = address & 0xFF
            self._BUFFER[1] = val & 0xFF
            i2c.write(self._BUFFER, end=2)
        
