""" DS3232 Driver

Ported into python from:
https://github.com/JChristensen/DS3232RTC
Copyright (C) 2018 by Jack Christensen and licensed under
GNU GPL v3.0, https://www.gnu.org/licenses/gpl.html
"""
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
    A1M1 = 7
    A1M2 = 7
    A1M3 = 7
    A1M4 = 7
    A2M2 = 7
    A2M3 = 7
    A2M4 = 7

    # Control register bits
    EOSC = 7
    BBSQW = 6
    CONV = 5
    RS2 = 4
    RS1 = 3
    INTCN = 2
    A2IE = 1
    A1IE = 0

    # Status register bits
    OSF = 7
    BB32KHZ = 6
    CRATE1 = 5
    CRATE0 = 4
    EN32KHZ = 3
    BSY = 2
    A2F = 1
    A1F = 0

    # Other
    HR1224 = 6                   # Hours register 12 or 24 hour mode (24 hour mode==0)
    CENTURY = 7                  # Century bit in Month register
    DYDT = 6                     # Day/Date flag bit in alarm Day/Date registers

    def __init__(self):
        # DS3232 I2C Address
        self.addr = 0x68
        self.bus = SMBus(1)

    @property
    def seconds(self):
        self.bus.write_byte(self.addr, RTC.RTC_SECONDS)
        raw = self.read_byte(self.addr)
        return (10 * ((raw >> 4) & 0x07)) + (raw & 0x0F)

    @seconds.setter
    def seconds(self, new_seconds):
        b = (int(new_seconds/10) << 4) | (new_seconds%10)
        return self.bus.write_byte_data(self.addr, RTC.RTC_SECONDS, b)
    
    @property
    def minutes(self):
        self.bus.write_byte(self.addr, RTC.RTC_MINUTES)
        raw = self.read_byte(self.addr)
        return (10 * ((raw >> 4) & 0x07)) + (raw & 0x0F)

    @minutes.setter
    def minutes(self, new_minutes):
        b = (int(new_minutes/10) << 4) | (new_minutes%10)
        return self.bus.write_byte_data(self.addr, RTC.RTC_MINUTES, b)

    // Read the current time from the RTC and return it as a time_t
    // value. Returns a zero value if an I2C error occurred (e.g. RTC
    // not present).
    time_t DS3232RTC::get()
    {
        tmElements_t tm;

        if ( read(tm) ) return 0;
        return( makeTime(tm) );
    }

    // Set the RTC to the given time_t value and clear the
    // oscillator stop flag (OSF) in the Control/Status register.
    // Returns the I2C status (zero if successful).
    byte DS3232RTC::set(time_t t)
    {
        tmElements_t tm;

        breakTime(t, tm);
        return ( write(tm) );
    }

    // Read the current time from the RTC and return it in a tmElements_t
    // structure. Returns the I2C status (zero if successful).
    byte DS3232RTC::read(tmElements_t &tm)
    {
        i2cBeginTransmission(RTC_ADDR);
        i2cWrite((uint8_t)RTC_SECONDS);
        if ( byte e = i2cEndTransmission() ) { errCode = e; return e; }
        // request 7 bytes (secs, min, hr, dow, date, mth, yr)
        i2cRequestFrom(RTC_ADDR, tmNbrFields);
        tm.Second = bcd2dec(i2cRead() & ~_BV(DS1307_CH));
        tm.Minute = bcd2dec(i2cRead());
        tm.Hour = bcd2dec(i2cRead() & ~_BV(HR1224));    // assumes 24hr clock
        tm.Wday = i2cRead();
        tm.Day = bcd2dec(i2cRead());
        tm.Month = bcd2dec(i2cRead() & ~_BV(CENTURY));  // don't use the Century bit
        tm.Year = y2kYearToTm(bcd2dec(i2cRead()));
        return 0;
    }

    // Set the RTC time from a tmElements_t structure and clear the
    // oscillator stop flag (OSF) in the Control/Status register.
    // Returns the I2C status (zero if successful).
    byte DS3232RTC::write(tmElements_t &tm)
    {
        i2cBeginTransmission(RTC_ADDR);
        i2cWrite((uint8_t)RTC_SECONDS);
        i2cWrite(dec2bcd(tm.Second));
        i2cWrite(dec2bcd(tm.Minute));
        i2cWrite(dec2bcd(tm.Hour));         // sets 24 hour format (Bit 6 == 0)
        i2cWrite(tm.Wday);
        i2cWrite(dec2bcd(tm.Day));
        i2cWrite(dec2bcd(tm.Month));
        i2cWrite(dec2bcd(tmYearToY2k(tm.Year)));
        byte ret = i2cEndTransmission();
        uint8_t s = readRTC(RTC_STATUS);        // read the status register
        writeRTC( RTC_STATUS, s & ~_BV(OSF) );  // clear the Oscillator Stop Flag
        return ret;
    }

    // Write multiple bytes to RTC RAM.
    // Valid address range is 0x00 - 0xFF, no checking.
    // Number of bytes (nBytes) must be between 1 and 31 (Wire library
    // limitation).
    // Returns the I2C status (zero if successful).
    byte DS3232RTC::writeRTC(byte addr, byte *values, byte nBytes)
    {
        i2cBeginTransmission(RTC_ADDR);
        i2cWrite(addr);
        for (byte i=0; i<nBytes; i++) i2cWrite(values[i]);
        return i2cEndTransmission();
    }

    // Write a single byte to RTC RAM.
    // Valid address range is 0x00 - 0xFF, no checking.
    // Returns the I2C status (zero if successful).
    byte DS3232RTC::writeRTC(byte addr, byte value)
    {
        return ( writeRTC(addr, &value, 1) );
    }

    // Read multiple bytes from RTC RAM.
    // Valid address range is 0x00 - 0xFF, no checking.
    // Number of bytes (nBytes) must be between 1 and 32 (Wire library
    // limitation).
    // Returns the I2C status (zero if successful).
    byte DS3232RTC::readRTC(byte addr, byte *values, byte nBytes)
    {
        i2cBeginTransmission(RTC_ADDR);
        i2cWrite(addr);
        if ( byte e = i2cEndTransmission() ) return e;
        i2cRequestFrom( (uint8_t)RTC_ADDR, nBytes );
        for (byte i=0; i<nBytes; i++) values[i] = i2cRead();
        return 0;
    }

    // Read a single byte from RTC RAM.
    // Valid address range is 0x00 - 0xFF, no checking.
    byte DS3232RTC::readRTC(byte addr)
    {
        byte b;

        readRTC(addr, &b, 1);
        return b;
    }

    // Set an alarm time. Sets the alarm registers only.  To cause the
    // INT pin to be asserted on alarm match, use alarmInterrupt().
    // This method can set either Alarm 1 or Alarm 2, depending on the
    // value of alarmType (use a value from the ALARM_TYPES_t enumeration).
    // When setting Alarm 2, the seconds value must be supplied but is
    // ignored, recommend using zero. (Alarm 2 has no seconds register.)
    void DS3232RTC::setAlarm(ALARM_TYPES_t alarmType, byte seconds, byte minutes, byte hours, byte daydate)
    {
        uint8_t addr;

        seconds = dec2bcd(seconds);
        minutes = dec2bcd(minutes);
        hours = dec2bcd(hours);
        daydate = dec2bcd(daydate);
        if (alarmType & 0x01) seconds |= _BV(A1M1);
        if (alarmType & 0x02) minutes |= _BV(A1M2);
        if (alarmType & 0x04) hours |= _BV(A1M3);
        if (alarmType & 0x10) daydate |= _BV(DYDT);
        if (alarmType & 0x08) daydate |= _BV(A1M4);

        if ( !(alarmType & 0x80) )  // alarm 1
        {
            addr = ALM1_SECONDS;
            writeRTC(addr++, seconds);
        }
        else
        {
            addr = ALM2_MINUTES;
        }
        writeRTC(addr++, minutes);
        writeRTC(addr++, hours);
        writeRTC(addr++, daydate);
    }

    // Set an alarm time. Sets the alarm registers only. To cause the
    // INT pin to be asserted on alarm match, use alarmInterrupt().
    // This method can set either Alarm 1 or Alarm 2, depending on the
    // value of alarmType (use a value from the ALARM_TYPES_t enumeration).
    // However, when using this method to set Alarm 1, the seconds value
    // is set to zero. (Alarm 2 has no seconds register.)
    void DS3232RTC::setAlarm(ALARM_TYPES_t alarmType, byte minutes, byte hours, byte daydate)
    {
        setAlarm(alarmType, 0, minutes, hours, daydate);
    }

    // Enable or disable an alarm "interrupt" which asserts the INT pin
    // on the RTC.
    void DS3232RTC::alarmInterrupt(byte alarmNumber, bool interruptEnabled)
    {
        uint8_t controlReg, mask;

        controlReg = readRTC(RTC_CONTROL);
        mask = _BV(A1IE) << (alarmNumber - 1);
        if (interruptEnabled)
            controlReg |= mask;
        else
            controlReg &= ~mask;
        writeRTC(RTC_CONTROL, controlReg);
    }

    // Returns true or false depending on whether the given alarm has been
    // triggered, and resets the alarm flag bit.
    bool DS3232RTC::alarm(byte alarmNumber)
    {
        uint8_t statusReg = readRTC(RTC_STATUS);
        uint8_t mask = _BV(A1F) << (alarmNumber - 1);
        if (statusReg & mask) {
            statusReg &= ~mask;
            writeRTC(RTC_STATUS, statusReg);
            return true;
        }
        else {
            return false;
        }
    }

    // Returns true or false depending on whether the given alarm has been
    // triggered, without resetting the alarm flag bit.
    bool DS3232RTC::checkAlarm(byte alarmNumber)
    {
        uint8_t statusReg = readRTC(RTC_STATUS);
        uint8_t mask = _BV(A1F) << (alarmNumber - 1);
        return (statusReg & mask);
    }

    // Clears the given alarm flag bit if it is set.
    // Returns the value of the flag bit before if was cleared.
    bool DS3232RTC::clearAlarm(byte alarmNumber)
    {
        uint8_t statusReg = readRTC(RTC_STATUS);
        uint8_t mask = _BV(A1F) << (alarmNumber - 1);
        bool retVal = statusReg & mask;
        if (retVal) {
            statusReg &= ~mask;
            writeRTC(RTC_STATUS, statusReg);
        }
        return retVal;
    }

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

    // Returns the value of the oscillator stop flag (OSF) bit in the
    // control/status register which indicates that the oscillator is or    *
    // was stopped, and that the timekeeping data may be invalid.
    // Optionally clears the OSF bit depending on the argument passed.
    bool DS3232RTC::oscStopped(bool clearOSF)
    {
        uint8_t s = readRTC(RTC_STATUS);    // read the status register
        bool ret = s & _BV(OSF);            // isolate the osc stop flag to return to caller
        if (ret && clearOSF)                // clear OSF if it's set and the caller wants to clear it
        {
            writeRTC( RTC_STATUS, s & ~_BV(OSF) );
        }
        return ret;
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

    // Decimal-to-BCD conversion
    uint8_t DS3232RTC::dec2bcd(uint8_t n)
    {
        return n + 6 * (n / 10);
    }

    // BCD-to-Decimal conversion
    uint8_t __attribute__ ((noinline)) DS3232RTC::bcd2dec(uint8_t n)
    {
        return n - 6 * (n >> 4);
    }

    #ifdef ARDUINO_ARCH_AVR
    DS3232RTC RTC;      // instantiate an RTC object
    #endif