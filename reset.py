# DO NOT RUN!!!
# Use exec(open("reset.py").read()) in python shell to avoid corrupting file
from smbus2 import SMBusWrapper
from smbus2 import SMBus

with SMBusWrapper(1) as bus:
    bus.write_i2c_block_data(0x2B, 0x70, [0x0F])
