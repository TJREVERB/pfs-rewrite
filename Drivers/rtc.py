""" DS3232 Driver
This driver does not include alarm functionality

Ported into python from:
https://github.com/JChristensen/DS3232RTC
Copyright (C) 2018 by Jack Christensen and licensed under
GNU GPL v3.0, https://www.gnu.org/licenses/gpl.html
"""

# https://datasheets.maximintegrated.com/en/ds/DS3232.pdf

from smbus2 import SMBus
from lib.exceptions import wrap_errors, RTCError
from Drivers.device import Device


class RTC(Device):
    # DS3232 Register Addresses
    RTC_SECONDS = 0x00
    RTC_MINUTES = 0x01
    RTC_HOURS = 0x02
    RTC_DAY = 0x03
    RTC_DATE = 0x04
    RTC_MONTH = 0x05
    RTC_YEAR = 0x06
    ALM1_SECONDS = 0x07
    ALM1_MINUTES = 0x08
    ALM1_HOURS = 0x09
    ALM1_DAYDATE = 0x0A
    ALM2_MINUTES = 0x0B
    ALM2_HOURS = 0x0C
    ALM2_DAYDATE = 0x0D
    RTC_CONTROL = 0x0E
    RTC_STATUS = 0x0F
    RTC_AGING = 0x10
    RTC_TEMP_MSB = 0x11
    RTC_TEMP_LSB = 0x12
    SRAM_START_ADDR = 0x14  # first SRAM address
    SRAM_SIZE = 236  # number of bytes of SRAM

    # Alarm mask bits
    MASK_A1M1 = 7
    MASK_A1M2 = 7
    MASK_A1M3 = 7
    MASK_A1M4 = 7
    MASK_A2M2 = 7
    MASK_A2M3 = 7
    MASK_A2M4 = 7

    # Control register bits
    MASK_EOSC = 7
    MASK_BBSQW = 6
    MASK_CONV = 5
    MASK_RS2 = 4
    MASK_RS1 = 3
    MASK_INTCN = 2
    MASK_A2IE = 1
    MASK_A1IE = 0

    # Status register bits
    MASK_OSF = 7
    MASK_BB32KHZ = 6
    MASK_CRATE1 = 5
    MASK_CRATE0 = 4
    MASK_EN32KHZ = 3
    MASK_BSY = 2
    MASK_A2F = 1
    MASK_A1F = 0

    # Frequency vs RS2, RS1 bits
    FREQ_DISABLE = (-1, -1)
    FREQ_1Hz = (0, 0)
    FREQ_1_024KHz = (0, 1)
    FREQ_4_096KHz = (1, 0)
    FREQ_8_192KHZ = (1, 1)

    @wrap_errors(RTCError)
    def __init__(self, sfr):
        super().__init__(sfr)
        # DS3232 I2C Address
        self.addr = 0x68
        self.bus = SMBus(1)

    @property
    @wrap_errors(RTCError)
    def OSF(self):
        self.bus.write_byte(self.addr, RTC.RTC_STATUS)
        raw = self.bus.read_byte(self.addr)
        return (raw >> RTC.MASK_OSF) & 1

    @wrap_errors(RTCError)
    def clr_OSF(self):  # Clear oscillator stop flag
        self.bus.write_byte(self.addr, RTC.RTC_STATUS)
        raw = self.bus.read_byte(self.addr)
        self.bus.write_byte_data(self.addr, RTC.RTC_STATUS, raw & ~(1 << RTC.MASK_OSF))

    @property
    @wrap_errors(RTCError)
    def seconds(self):
        self.bus.write_byte(self.addr, RTC.RTC_SECONDS)
        raw = self.bus.read_byte(self.addr)
        return (10 * ((raw >> 4) & 0x07)) + (raw & 0x0F)

    @seconds.setter
    @wrap_errors(RTCError)
    def seconds(self, new_seconds):
        b = ((new_seconds // 10) << 4) | (new_seconds % 10)
        self.bus.write_byte_data(self.addr, RTC.RTC_SECONDS, b)
        self.clr_OSF()

    @property
    @wrap_errors(RTCError)
    def minutes(self):
        self.bus.write_byte(self.addr, RTC.RTC_MINUTES)
        raw = self.bus.read_byte(self.addr)
        return (10 * ((raw >> 4) & 0x07)) + (raw & 0x0F)

    @minutes.setter
    @wrap_errors(RTCError)
    def minutes(self, new_minutes):
        b = ((new_minutes // 10) << 4) | (new_minutes % 10)
        self.bus.write_byte_data(self.addr, RTC.RTC_MINUTES, b)
        self.clr_OSF()

    @property
    @wrap_errors(RTCError)
    def hours(self):
        self.bus.write_byte(self.addr, RTC.RTC_HOURS)
        raw = self.bus.read_byte(self.addr)
        if (raw >> 6) & 1:  # 12 hour
            return 12 * ((raw >> 5) & 1) + 10 * ((raw >> 4) & 1) + (raw & 0x0F)
        else:  # 24 hour
            return 20 * ((raw >> 5) & 1) + 10 * ((raw >> 4) & 1) + (raw & 0x0F)

    @hours.setter
    @wrap_errors(RTCError)
    def hours(self, new_hours, mode=0):
        """
        :param new_hours: (int) new hour, in 24 hour format
        :param mode: (bool) 12 or 24 hour mode, default to 24h. 1 if 12 hour, 0 if 24 hour
        """
        if mode:  # 12 hour
            b = (mode << 6) | ((new_hours >= 12) << 5) | ((new_hours % 12 >= 10) << 4) | ((new_hours % 12) % 10)
        else:  # 24 hour
            b = (mode << 6) | ((new_hours >= 20) << 5) | ((new_hours % 20 >= 10) << 4) | (new_hours % 10)
        self.bus.write_byte_data(self.addr, RTC.RTC_HOURS, b)
        self.clr_OSF()

    @property
    @wrap_errors(RTCError)
    def day(self):
        self.bus.write_byte(self.addr, RTC.RTC_DAY)
        return self.bus.read_byte(self.addr)

    @day.setter
    @wrap_errors(RTCError)
    def day(self, new_day):
        """
        :param new_day: (int) date, 1-7
        """
        self.bus.write_byte_data(self.addr, RTC.RTC_DAY, new_day)
        self.clr_OSF()

    @property
    @wrap_errors(RTCError)
    def date(self):
        self.bus.write_byte(self.addr, RTC.RTC_DATE)
        raw = self.bus.read_byte(self.addr)
        return (raw >> 4) * 10 + (raw & 0x0F)

    @date.setter
    @wrap_errors(RTCError)
    def date(self, new_date):
        b = (new_date // 10 << 4) | (new_date % 10)
        self.bus.write_byte_data(self.addr, RTC.RTC_DATE, b)
        self.clr_OSF()

    @property
    @wrap_errors(RTCError)
    def month(self):
        self.bus.write_byte(self.addr, RTC.RTC_MONTH)
        raw = self.bus.read_byte(self.addr) & (0x1F)  # Ignore century bit
        return (raw >> 4) * 10 + (raw & 0x0F)

    @month.setter
    @wrap_errors(RTCError)
    def month(self, new_month):
        self.bus.write_byte(self.addr, RTC.RTC_MONTH)
        b = self.bus.read_byte(self.addr) & 0x80  # Read century bit to make sure it doesn't change
        b |= (new_month // 10 << 4) | (new_month % 10)
        self.bus.write_byte_data(self.addr, RTC.RTC_MONTH, b)
        self.clr_OSF()
    
    #NOTE: YEAR IS LAST TWO DIGITS OF YEAR ONLY i.e. 21
    @property
    @wrap_errors(RTCError)
    def year(self):
        self.bus.write_byte(self.addr, RTC.RTC_YEAR)
        raw = self.bus.read_byte(self.addr)
        return (raw >> 4) * 10 + (raw & 0x0F)

    @year.setter
    @wrap_errors(RTCError)
    def year(self, new_year):
        b = (new_year // 10 << 4) | (new_year % 10)
        self.bus.write_byte_data(self.addr, RTC.RTC_YEAR, b)
        self.clr_OSF()

    @wrap_errors(RTCError)
    def square_wave(self, freq):
        """
        Enables or disables square wave output
        :param freq: (tuple) bits to set (RS2, RS1) to for frequency selection. If sqw is to be disabled, freq = (-1, -1)
        """
        if freq[0] not in [0, 1] or freq[1] not in [0, 1]:
            # Disable sqw
            self.bus.write_byte(self.addr, RTC.RTC_STATUS)
            b = self.bus.read_byte(self.addr)
            b &= ~(1 << RTC.MASK_EN32KHZ)
            return self.bus.write_byte_data(self.addr, RTC.RTC_STATUS, b)
        self.bus.write_byte(self.addr, RTC.RTC_CONTROL)  # TODO: MAKE SURE THAT FIRST BYTE IS LS[0]
        ls = self.bus.read_i2c_block_data(self.addr, 0, 2)
        ls[0] |= (1 << RTC.MASK_EN32KHZ)
        ls[1] = (ls[1] & ~(1 << RTC.MASK_RS2)) | (freq[0] << RTC.MASK_RS2)  # Set RS2 bit
        ls[1] = (ls[1] & ~(1 << RTC.MASK_RS1)) | (freq[1] << RTC.MASK_RS1)  # Set RS1 bit
        self.bus.write_i2c_block_data(self.addr, RTC.RTC_CONTROL, ls)

    @wrap_errors(RTCError)
    def temperature(self):
        """
        Reads and returns temperature in C
        :return: (int) temperature, degrees celsius
        """
        self.bus.write_byte(self.addr, RTC.RTC_TEMP_MSB)
        ls = self.bus.read_i2c_block_data(self.addr, 0, 2)
        raw = (ls[1] >> 6) | (ls[0] << 2)
        if (raw >> 9) & 1:  # convert from twos comp to decimal, if sign bit is 1
            raw &= 0x1ff
            raw -= (1 << 9)
        return raw / 4
