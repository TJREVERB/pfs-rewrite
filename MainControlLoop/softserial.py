import pigpio
import time

class SoftwareUART():
    """Bitbang uart driver using pigpio and interrupts"""
    
    def __init__(self, RX, TX, baud):
        self.pi = pigpio.pi()
        self.RXPin = RX
        self.TXPin = TX
        self.baudrate = baud
        self.wave = None
        self.pi.set_mode(TX, pigpio.OUTPUT)
        self.pi.bb_serial_read_open(RX)

    def __del__(self):
        pigpio.exceptions = False #fatal excpetions off in case bbserial doesnt exists
        pi.wave_delete(self.wave)
        pi.bb_serial_read_close(self.RXPin)
        pi.stop()
        pigpio.exceptions = True 
    
    def write(self, msg):
        

    def read(self, len):
