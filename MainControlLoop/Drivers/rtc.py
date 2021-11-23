""" DS3232 Driver

Ported into python from:
https://github.com/JChristensen/DS3232RTC
Copyright (C) 2018 by Jack Christensen and licensed under
GNU GPL v3.0, https://www.gnu.org/licenses/gpl.html
"""

#https://datasheets.maximintegrated.com/en/ds/DS3232.pdf

import datetime
import os
import time
from smbus2 import SMBus

class RTC:
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
    SRAM_START_ADDR = 0x14 # first SRAM address
    SRAM_SIZE = 236 # number of bytes of SRAM

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

    def __init__(self):
        # DS3232 I2C Address
        self.addr = 0x68
        self.bus = SMBus(1)

    @property
    def OSF(self):
        self.bus.write_byte(self.addr, RTC.RTC_STATUS)
        raw = self.bus.read_byte(self.addr)
        return (raw >> RTC.MASK_OSF) & 1
    
    def clr_OSF(self): #Clear oscillator stop flag
        self.bus.write_byte(self.addr, RTC.RTC_STATUS)
        raw = self.bus.read_byte(self.addr)
        self.bus.write_byte_data(self.addr, RTC.RTC_STATUS, raw | (1 << RTC.MASK_OSF))

    @property
    def seconds(self):
        self.bus.write_byte(self.addr, RTC.RTC_SECONDS)
        raw = self.bus.read_byte(self.addr)
        return (10 * ((raw >> 4) & 0x07)) + (raw & 0x0F)

    @seconds.setter
    def seconds(self, new_seconds):
        b = ((new_seconds//10) << 4) | (new_seconds%10)
        self.bus.write_byte_data(self.addr, RTC.RTC_SECONDS, b)
        self.clr_OSF()
    
    @property
    def minutes(self):
        self.bus.write_byte(self.addr, RTC.RTC_MINUTES)
        raw = self.bus.read_byte(self.addr)
        return (10 * ((raw >> 4) & 0x07)) + (raw & 0x0F)

    @minutes.setter
    def minutes(self, new_minutes):
        b = ((new_minutes//10) << 4) | (new_minutes%10)
        self.bus.write_byte_data(self.addr, RTC.RTC_MINUTES, b)
        self.clr_OSF()

    @property
    def hours(self):
        self.bus.write_byte(self.addr, RTC.RCT_HOURS)
        raw = self.bus.read_byte(self.addr)
        if (raw >> 6) & 1: # 12 hour
            return 12 * ((raw >> 5) & 1) + 10 * ((raw >> 4) & 1) + (raw & 0x0F)
        else: # 24 hour
            return 20 * ((raw >> 5) & 1) + 10 * ((raw >> 4) & 1) + (raw & 0x0F)

    @hours.setter
    def hours(self, new_hours, mode=0):
        """
        :param new_hours: (int) new hour, in 24 hour format
        :param mode: (bool) 12 or 24 hour mode, default to 24h. 1 if 12 hour, 0 if 24 hour
        """ 
        if mode: # 12 hour
            b = (mode << 6) | ((new_hours >= 12) << 5) | ((new_hours%12 >= 10) << 4) | ((new_hours%12)%10)
        else: # 24 hour
            b = (mode << 6) | ((new_hours >= 20) << 5) | ((new_hours%20 >= 10) << 4) | (new_hours%10)
        self.bus.write_byte_data(self.addr, RTC.RTC_HOURS, b)
        self.clr_OSF()

    @property
    def day(self):
        self.bus.write_byte(self.addr, RTC.RTC_DAY)
        return self.bus.read_byte(self.addr)
    
    @day.setter
    def day(self, new_day):
        """
        :param new_day: (int) date, 1-7
        """
        self.bus.write_byte_data(self.addr, RTC.RTC_DAY, new_day)
        self.clr_OSF()

    @property
    def date(self):
        self.bus.write_byte(self.addr, RTC.RTC_DATE)
        raw = self.bus.read_byte(self.addr)
        return (raw >> 4) * 10 + (raw & 0x0F)
    
    @date.setter
    def date(self, new_date):
        b = (new_date//10 << 4) | (new_date%10)
        self.bus.write_byte_data(self.addr, RTC.RTC_DATE, b)
        self.clr_OSF()

    @property
    def month(self):
        self.bus.write_byte(self.addr, RTC.RTC_MONTH)
        raw = self.bus.read_byte(self.addr) & (0x1F) #Ignore century bit
        return (raw >> 4) * 10 + (raw & 0x0F)

    @month.setter
    def month(self, new_month):
        self.bus.write_byte(self.addr, RTC.RTC_MONTH)
        b = self.bus.read_byte(self.addr) & 0x80 #Read century bit to make sure it doesn't change
        b |= (new_month//10 << 4) | (new_month%10)
        self.bus.write_byte_data(self.addr, RTC.RTC_MONTH, b)
        self.clr_OSF()

    @property
    def year(self):
        self.bus.write_byte(self.addr, RTC.RTC_YEAR)
        raw = self.bus.read_bytes(self.addr)
        return (raw >> 4) * 10 + (raw & 0x0F)

    @year.setter
    def year(self, new_year):
        b = (new_year//10 << 4) | (new_year%10)
        self.bus.write_byte_data(self.addr, RTC.RTC_YEAR, b)
        self.clr_OSF()

    #TODO: Convert the following to python
    // Enable or disable the square wave output.
    // Use a value from the SQWAVE_FREQS_t enumeration for the parameter.
    void DS3232RTC::squareWave(SQWAVE_FREQS_t freq)
    {
        uint8_t controlReg;

        controlReg = readRTC(RTC_CONTROL);
        if (freq >= SQWAVE_NONE)
        {
            controlReg |= _BV(INTCN);
        }
        else
        {
            controlReg = (controlReg & 0xE3) | (freq << RS1);
        }
        writeRTC(RTC_CONTROL, controlReg);
    }

    // Returns the temperature in Celsius times four.
    int16_t DS3232RTC::temperature()
    {
        union int16_byte {
            int16_t i;
            byte b[2];
        } rtcTemp;

        rtcTemp.b[0] = readRTC(RTC_TEMP_LSB);
        rtcTemp.b[1] = readRTC(RTC_TEMP_MSB);
        return rtcTemp.i / 64;
    }