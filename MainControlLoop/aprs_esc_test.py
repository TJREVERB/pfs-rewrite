from serial import Serial
import time


PORT = '/dev/ttyACM0'
BAUDRATE = 19200
serial = Serial(port=PORT, baudrate=BAUDRATE, timeout=1)  # connect serial
while not serial.is_open:
    time.sleep(0.5)
serial.flush()
serial.write("Test\n".encode("utf-8"))
print("Writing to serial successful")
serial.flush()
serial.write("\x1b\n".encode("utf-8"))
print("Writing esc key to serial successful")
