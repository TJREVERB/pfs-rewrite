from smbus2 import SMBus
from MainControlLoop.lib.exceptions import decorate_all_callables, wrap_errors, SystemError

class Serial:
    """
    Custom class for i2c to serial functionality of second core
    """
    @wrap_errors(SystemError)
    def __init__(self):
        self.bus = SMBus(1)
        self.addr = 0x45
        decorate_all_callables(self, SystemError)
    
    def write(self, data):
        self.bus.write_i2c_block_data(self.addr, 0, list(data))

    def read(self):
        self.bus.write_byte(self.addr, 1)
        return self.bus.read_i2c_block_data(self.addr, 0, 255)

    def flush(self):
        self.read()

    def close(self):
        self.bus.close()
    