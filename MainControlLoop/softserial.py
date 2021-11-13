import pigpio
import time
import os

class SoftwareUART():
    """Bitbang uart driver using pigpio and interrupts"""
    
    def __init__(self, RX, TX, baud):
        self.pi = pigpio.pi()
        # test to see if the daemon is already running
        if not self.pi.connected:
            # if the daemon is not running, start it
            os.system("sudo pigpiod")
            time.sleep(1)
            self.pi = pigpio.pi()
        self.RXPin = RX
        self.TXPin = TX
        self.baudrate = baud
        self.wave = None
        self.pi.set_mode(TX, pigpio.OUTPUT)
        self.pi.bb_serial_read_open(self.RXPin, self.baudrate)

    def __del__(self):
        pigpio.exceptions = False #fatal excpetions off in case bbserial doesnt exists
        self.pi.wave_delete(self.wave)
        self.pi.bb_serial_read_close(self.RXPin)
        self.pi.stop()
        pigpio.exceptions = True 
    
    def write(self, msg):
        """Writes a message over bitbang serial
        :param msg: (bytes) message to write"""
        self.pi.bb_serial_read_close(self.RXPin)
        self.pi.wave_clear()
        self.pi.wave_add_serial(self.TXPin, self.baudrate, msg)
        self.wave = self.pi.wave_create()
        self.pi.wave_send_once(self.wave)
        self.pi.wave_delete(self.wave)
        self.pi.bb_serial_read_open(self.RXPin, self.baudrate)
        return 1

    def read(self, len):
        """Reads and returns message over bitbang serial
        :return: (tuple) error code (1 if succesful), message"""
        msg = bytes()
        for _ in range(len):
            count, data = self.pi.bb_serial_read(self.RXPin)
            if count:
                msg += data
            else:
                return count, msg
        return 1, msg
