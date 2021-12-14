from smbus2 import SMBus
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class Serial:
    """
    Custom class for i2c to serial functionality of second core
    """

    @wrap_errors(LogicalError)
    def __init__(self):
        self.bus = SMBus(1)
        self.addr = 0x45

    @wrap_errors(LogicalError)
    def write(self, data):
        for d in list(data):
            self.bus.write_byte_data(self.addr, 0, d)

    @wrap_errors(LogicalError)
    def read(self, length=255):
        result = []
        for _ in range(length):
            result.append(self.bus.read_byte_data(self.addr, 1))
        return result

    @wrap_errors(LogicalError)
    def flush(self):
        self.read()

    @wrap_errors(LogicalError)
    def close(self):
        self.bus.close()
