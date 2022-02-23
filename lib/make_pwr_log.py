import random

with open("pwr_draw_log.csv", "w") as f:
    f.write("ts0,ts1,buspower,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0A\n")
    for i in range(0, 10000):
        f.write(str(random.randint(0, 99999)) + "," + str(random.randint(0, 99999)) + ",0.023,1.001,1.001,1.001,1.001,1.001,1.001,1.001,1.001,1.001,1.001\n")
    f.close()


