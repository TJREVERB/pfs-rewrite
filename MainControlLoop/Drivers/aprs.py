from serial import Serial
import time, datetime
import pandas as pd
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket

class APRS:
    """
    Class for APRS
    """
    PORT = '/dev/serial0'
    DEVICE_PATH = '/sys/devices/platform/soc/20980000.usb/buspower'
    BAUDRATE = 19200

    def __init__(self, state_field_registry):
        self.sfr = state_field_registry
        self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        while not self.serial.is_open:
            time.sleep(0.5)

    def __del__(self):
        self.serial.close()

    def __str__(self):
        return "APRS"

    def enter_firmware_menu(self) -> bool:
        """
        Enter APRS firmware menu
        :return: (bool) whether entering menu was successful
        """
        serinput = ""
        attempts = 0
        while serinput.find("Press ESC 3 times to enter TT4 Options Menu") == -1 or attempts > 2:
            self.serial.write("\x1b\x1b\x1b".encode("utf-8"))
            time.sleep(.2)
            self.serial.write("\x0d".encode("utf-8"))
            time.sleep(1)
            serinput += str(self.serial.read(100))
            print(serinput)
            attempts+=1
        if attempts > 2:
            return False

        serinput = ""
        attempts = 0
        while serinput.find("Byonics MTT4B Alpha v0.73 (1284)") == -1 or attempts > 2:
            self.serial.write("\x1b".encode("utf-8"))
            time.sleep(.2)
            self.serial.write("\x1b".encode("utf-8"))
            time.sleep(.2)
            self.serial.write("\x1b".encode("utf-8"))
            time.sleep(3)
            serinput += str(self.serial.read(100))
            print(serinput)
            attempts += 1
        if attempts > 2:
            return False
        return True
    
    def exit_firmware_menu(self) -> bool:
        """
        Exit APRS firmware menu
        :return: whether exit was successful
        """
        self.serial.write("QUIT".encode("utf-8"))
        time.sleep(.2)
        self.serial.write("\x0d".encode("utf-8"))
        time.sleep(.5)
        result = str(self.serial.read(100))
        if result.find("Press ESC 3 times to enter TT4 Options Menu") == -1:
            return False
        return True

    def functional(self) -> bool:
        """
        Checks the state of the serial port (initializing it if needed)
        Calls powered_on() to check whether APRS is on and working
        :return: (bool) APRS and serial connection are working
        """
        if self.serial is None:
            try:
                self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)
            except:
                raise RuntimeError("Serial port can't be created")
        if not self.serial.is_open:
            try:
                self.serial.open()
            except:
                raise RuntimeError("Serial port can't be opened")
        
        if not self.enter_firmware_menu():
            raise RuntimeError("Failed to open firmware menu")
        
        if not self.exit_firmware_menu():
            raise RuntimeError("Failed to exit firmware menu")
        
        return True

    def enable_digi(self): #TODO: Test these
        """
        Enables Hardware Digipeating
        """
        if self.enter_firmware_menu():
            self.change_setting("BANK", "0")
            time.sleep(0.1)
            #self.change_setting("ABAUD", "19200")
            #time.sleep(0.1)
            if not self.exit_firmware_menu():
                raise RuntimeError("Unable to exit firmware menu")
        else:
            raise RuntimeError("Unable to enter firmware menu")
        return True

    def disable_digi(self):
        """
        Disables Hardware Digipeating
        This should also be run after initialization to set the default bank to 0
        """
        if self.enter_firmware_menu():
            self.change_setting("BANK", "1")
            time.sleep(0.1)
            #self.change_setting("ABAUD", "19200")
            #time.sleep(0.1)
            if not self.exit_firmware_menu():
                raise RuntimeError("Unable to exit firmware menu")
        else:
            raise RuntimeError("Unable to enter firmware menu")
        return True
    
    def request_setting(self, setting) -> str:
        """
        Requests and returns value of given firmware setting. 
        Assumes firmware menu has already been entered successfully. Does not exit firmware menu afterwards
        :param setting: firmware setting to request
        :return: (str) text that APRS returns
        """
        self.serial.write((setting + "\x0d").encode("utf-8"))
        try:
            return self.serial.read(50).decode("utf-8")
        except:
            raise RuntimeError("Failed to read setting")

    def change_setting(self, setting, value) -> bool:
        """
        Changes value of given setting
        Assumes firmware menu has already been entered successfully. Does not exit firmware menu afterwards
        :param setting: setting to change
        :param value: value to change setting to
        :return: (bool) whether process worked
        """
        self.serial.write((setting + " " + str(value) + "\x0d").encode("utf-8"))
        try:
            result = self.serial.read(100).decode("utf-8")
            if result.find("COMMAND NOT FOUND") != -1:
                raise RuntimeError("No such setting")
            if result.find("is") == -1 and result.find("was") == -1:
                raise RuntimeError("Failed to change setting")
        except:
            raise RuntimeError("Failed to read setting")

    def clear_data_lines(self) -> None:
        """
        Switch off USB bus power, then switch it back on.
        This addresses problem with data lines becoming clogged.
        Equivalent of tester.sh
        """
        with open(self.DEVICE_PATH, "w") as f:
            f.write(str(0))
        time.sleep(15)
        with open(self.DEVICE_PATH, "w") as f:
            f.write(str(1))
        time.sleep(5)

    def transmit(self, packet: TransmissionPacket) -> bool:
        """
        Takes a descriptor and data, and transmits
        :param packet: (TransmissionPacket) packet to transmit
        :return: (bool) success
        """
        if packet.simulate:
            return True
        pd.DataFrame([
            {"timestamp": time.time()},
            {"radio": "APRS"},
            {"size": len(str(packet))},
        ]).to_csv(self.sfr.transmission_log_path, mode="a", header=False)
        return self.write(str(packet))

    def next_msg(self):
        """
        Reads in any messages, process, and add to queue
        """
        msg = self.read()
        if msg.find(prefix := self.sfr.command_executor.TJ_PREFIX) != -1:
            processed = msg[msg.find(prefix) + len(prefix):].strip().split(":")[:-1]
            self.sfr.vars.command_buffer.append(TransmissionPacket(processed[0], [float(s) for s in processed[2:]], int(processed[1])))
        elif msg.find(prefix := self.sfr.command_executor.OUTREACH_PREFIX) != -1:
            processed = msg[msg.find(prefix) + len(prefix):].strip().split(":")[:-1]
            self.sfr.vars.outreach_buffer.append(TransmissionPacket(processed[0], [float(s) for s in processed[2:]], int(processed[1])))

    def write(self, message: str) -> bool:
        """
        Writes the message to the APRS radio through the serial port
        :param message: (str) message to write
        :return: (bool) whether or not the write worked
        """
        try:
            self.serial.write((message + "\x0d").encode("utf-8"))
            self.serial.flush()
            return True
        except:
            return False

    def read(self) -> str:
        """
        Reads in as many available bytes as it can if timeout permits (terminating at a \n).
        :return: (str) message read ("" if no message read)
        """
        output = bytes()  # create an output variable
        for loop in range(50):
            try:
                next_byte = self.serial.read(size=1)
            except:
                return output
            if next_byte == bytes():
                break
            output += next_byte  # append next_byte to output
            # stop reading if it reaches a newline
            if next_byte == '\n'.encode('utf-8'):
                break
        return output.decode('utf-8')
        
