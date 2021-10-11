import spidev


class SC16IS752:
    PORT = '/dev/spidev0.0'
    BAUDRATE = 19200
    BUS = 0 #SPI bus, only bus 0 is available
    DEVICE = 0 #Chip select pin
    CRYSTAL_FREQ = 1843200

    #Device address
    ADDRESS_AA: hex = 0x90
    ADDRESS_AB: hex = 0x92
    ADDRESS_AC: hex = 0x94
    ADDRESS_AD: hex = 0x96
    ADDRESS_BA: hex = 0x98
    ADDRESS_BB: hex = 0x9A
    ADDRESS_BC: hex = 0x9C
    ADDRESS_BD: hex = 0x9E
    ADDRESS_CA: hex = 0xA0
    ADDRESS_CB: hex = 0xA2
    ADDRESS_CC: hex = 0xA4
    ADDRESS_CD: hex = 0xA6
    ADDRESS_DA: hex = 0xA8
    ADDRESS_DB: hex = 0xAA
    ADDRESS_DC: hex = 0xAC
    ADDRESS_DD: hex = 0xAE

    #General registers
    REG_RHR: hex = 0x00
    REG_THR: hex = 0x00
    REG_IER: hex = 0x01
    REG_FCR: hex = 0x02
    REG_IIR: hex = 0x02
    REG_LCR: hex = 0x03
    REG_MCR: hex = 0x04
    REG_LSR: hex = 0x05
    REG_MSR: hex = 0x06
    REG_SPR: hex = 0x07
    REG_TCR: hex = 0x06
    REG_TLR: hex = 0x07
    REG_TXLVL: hex = 0x08
    REG_RXLVL: hex = 0x09
    REG_IODIR: hex = 0x0A
    REG_IOSTATE: hex = 0x0B
    REG_IOINTENA: hex = 0x0C
    REG_IOCONTROL: hex = 0x0E
    REG_EFCR: hex = 0x0F

    #Special registers
    REG_DLL: hex = 0x00
    REG_DLH: hex = 0x01

    #Enhanced registers
    REG_EFR: hex = 0x02
    REG_XON1: hex = 0x04
    REG_XON2: hex = 0x05
    REG_XOFF1: hex = 0x06
    REG_XOFF2: hex = 0x07

    INT_CTS: hex = 0x80
    INT_RTS: hex = 0x40
    INT_XOFF: hex = 0x20
    INT_SLEEP: hex = 0x10
    INT_MODEM: hex = 0x08
    INT_LINE: hex = 0x04
    INT_THR: hex = 0x02
    INT_RHR: hex = 0x01

    CHANNEL_A: hex = 0x00
    CHANNEL_B: hex = 0x01
    CHANNEL_BOTH: hex = 0x00

    def __init__(self):
        self.peek_buf = [-1, -1]
        self.peek_flag = [0, 0]
        self.fifo_available = [0, 0]

        self.spi = spidev.SpiDev()
        self.spi.open(SC16IS752.BUS, SC16IS752.DEVICE)

        self.spi.max_speed_hz=19200
        self.spi.mode = 0 #Sampling mode: mode 0 samples at rising edge, mode 1 samples at falling edge, mode 2 samples at falling edge active low, mode 3 samples at rising edge active low

    def readRegister(self, channel, address) -> bytes:
        """
        Reads selected register using SPI
        :return: (bytes) data
        """
        result = 0
        self.spi.xfer([0x80 | (address << 3 | channel << 1)])
        result = self.spi.xfer([0xFF])
        return result

    def writeRegister(self, channel, address, val):
        """
        Writes data to selected register using SPI
        """
        self.spi.xfer([(address << 3 | channel << 1)])
        self.spi.xfer(val)

    def setBaud(self, channel) -> float:
        """
        Sets baud rate to preset constant
        :return: (float) error in baud rate
        """
        prescaler=4
        if self.readRegister(channel, SC16IS752.REG_MCR) & 0x80 ==0:
            prescaler=1

        divisor = (SC16IS752.CRYSTAL_FREQ/prescaler)/(SC16IS752.BAUDRATE*16)

        temp_lcr = (self.readRegister(channel, SC16IS752.REG_LCR)|0x80)
        self.writeRegister(channel, SC16IS752.REG_LCR, temp_lcr)

        #Write to DLL
        self.writeRegister(channel, SC16IS752.REG_DLL, (int)(divisor))

        #Write to DLH
        self.writeRegister(channel, SC16IS752.REG_DLH, (int)(divisor) >> 8)
        temp_lcr &= 0x7F
        self.writeRegister(channel, SC16IS752.REG_LCR, temp_lcr)

        actual_baudrate = (SC16IS752.CRYSTAL_FREQ/prescaler)/(16*divisor)
        error = (actual_baudrate-SC16IS752.BAUDRATE)*1000/SC16IS752.BAUDRATE

        return error

    def FIFOEnable(self, channel, fifo_enable):
        """
        does something idk
        """
        temp_fcr = self.readRegister(channel, SC16IS752.REG_FCR)

        if fifo_enable == 0:
            temp_fcr &= 0xFE
        else:
            temp_fcr |= 0x01

        self.writeRegister(channel, SC16IS752.REG_FCR, temp_fcr)

    def setLine(self, channel, data_length, parity_select, stop_length):
        """
        does something? I really dunno
        """
        temp_lcr = (self.readRegister(channel, SC16IS752.REG_LCR) & 0xC0)
        if data_length == 5:
            pass
        elif data_length == 6:
            temp_lcr |= 0x01
        elif data_length == 7:
            temp_lcr |= 0x02
        elif data_length == 8:
            temp_lcr |= 0x03
        else:
            temp_lcr |= 0x03

        if stop_length == 2:
            temp_lcr |= 0x04
        
        if parity_select == 0:
            pass
        elif parity_select == 1:
            temp_lcr |= 0x08
        elif parity_select == 2:
            temp_lcr |= 0x18
        elif parity_select == 3:
            temp_lcr |= 0x03
        elif parity_select == 4:
            pass
        else:
            pass

        self.writeRegister(channel, SC16IS752.REG_LCR, temp_lcr)

    def available(self, channel) -> int:
        if self.fifo_available[channel] == 0:
            self.fifo_available[channel] = self.readRegister(channel, SC16IS752.REG_RXLVL)
        return self.fifo_available[channel]

    def readByte(self, channel):
        if self.available(channel) == 0:
            return -1
        else:
            if self.fifo_available[channel] > 0:
                self.fifo_available[channel] -= 1
            val = self.readRegister(channel, SC16IS752.REG_RHR)
            return val

    def read(self, channel):
        if self.peek_flag[channel] == 0:
            return self.readByte(channel)
        self.peek_flag[channel] = 0
        return self.peek_buf[channel]

    def write(self, channel, val):
        temp_lsr = self.readRegister(channel, SC16IS752.REG_LSR)
        while (temp_lsr & 0x20) == 0:
            temp_lsr = self.readRegister(channel, SC16IS752.REG_LSR)
        self.writeRegister(channel, REG_THR, val)

    def begin(self):
        """
        start transmission, set baud rate
        """
        self.FIFOEnable(SC16IS752.CHANNEL_A, 1)
        self.setBaud(SC16IS752.CHANNEL_A)
        self.setLine(SC16IS752.CHANNEL_A, 8, 0, 1)
