import random

with open("lib/data/command_log.csv", "w") as f:
    f.write("ts0,ts1,radio,command,arg,registry,msn,result\n")
    for i in range(0, 100000):
        f.write(str(random.randint(0, 99999)) + "," + str(random.randint(0, 99999)) + ",APRS,GPL,123:234:342789:328,Primary,8129393,adsf:324:82399\n")
    f.close()


with open("lib/data/iridium_data.csv", "w") as f:
    f.write("ts0,ts1,latitude,longitude,altitude,signal\n")
    for i in range(0, 100000):
        f.write(str(random.randint(0, 99999)) + "," + str(random.randint(0, 99999)) + ",1.234567, 1.234567, 1.234567, 3\n")
    f.close()

with open("lib/data/orbits_log.csv", "w") as f:
    f.write("ts0,ts1,phase\n")
    for i in range(0, 100000):
        f.write(str(random.randint(0, 99999)) + "," + str(random.randint(0, 99999)) + ",daylight\n")
    f.close()

with open("lib/data/pwr_draw_log.csv", "w") as f:
    f.write("ts0,ts1,buspower,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,0x0A\n")
    for i in range(0, 100000):
        f.write(str(random.randint(0, 99999)) + "," + str(random.randint(0, 99999)) + ",0.023,1.001,1.001,1.001,1.001,1.001,1.001,1.001,1.001,1.001,1.001\n")
    f.close()
    
with open("lib/data/solar_generation_log.csv", "w") as f:
    f.write("ts0,ts1,bcr1,bcr2,bcr3\n")
    for i in range(0, 100000):
        f.write(str(random.randint(0, 99999)) + "," + str(random.randint(0, 99999)) + ",1.234,,1.234,,1.234\n")
    f.close()

with open("lib/data/transmission_log.csv", "w") as f:
    f.write("ts0,ts1,radio,size\n")
    for i in range(0, 100000):
        f.write(str(random.randint(0, 99999)) + "," + str(random.randint(0, 99999)) + ",APRS,80\n")
    f.close()

with open("lib/data/imu_data.csv", "w") as f:
    f.write("ts0,ts1,xgyro,ygyro,zgyro\n")
    for i in range(0, 100000):
        f.write(str(random.randint(0, 99999)) + "," + str(random.randint(0, 99999)) + ",1234.678,1234.678,1234.678\n")
    f.close()







  
    
    

    


