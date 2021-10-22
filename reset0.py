#recursively generated python scripts lmao
import os
import shutil
from smbus2 import SMBus

num = 1
f = open("resetLog.txt", "r")
if str(f.read()) == "1":
    num = 0
f.close()
f = open("resetLog.txt", "w")
f.write(str(num))
f.close()
src_dir = os.getcwd()
dest_dir = os.path.join(src_dir, "reset" + str(num) + ".py")
src_file = os.path.join(src_dir, "reset" + str(-1*num + 1) + ".py")
shutil.copy(src_file,dest_dir) #copy the file to destination directory

with SMBus() as bus:
    bus.write_i2c_block_data(0x2B, 0x70, [0x0F]) #commit sudoku
