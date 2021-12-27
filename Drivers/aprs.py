from serial import Serial
import time
from Drivers.transmission_packet import ResponsePacket
from lib.exceptions import wrap_errors, APRSError, LogicalError
from Drivers.device import Device
import copy

class APRS(Device):
    """
    Class for APRS
    """
    SERIAL_CONVERTERS = ["SPI-UART"]
    PORT = '/dev/serial0'
    DEVICE_PATH = '/sys/devices/platform/soc/20980000.usb/buspower'
    BAUDRATE = 19200
    MAX_DATASIZE = 100

    @wrap_errors(APRSError)
    def __init__(self, state_field_registry):
        super().__init__(state_field_registry)
        self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        while not self.serial.is_open:
            time.sleep(0.5)
        self.disable_digi()

    @wrap_errors(APRSError)
    def terminate(self):
        self.serial.close()

    @wrap_errors(LogicalError)
    def __str__(self):
        return "APRS"

    @wrap_errors(APRSError)
    def enter_firmware_menu(self) -> bool:
        """
        Enter APRS firmware menu
        :return: (bool) whether entering menu was successful
        """
        serinput = ""
        attempts = 0
        while serinput.find("Press ESC 3 times to enter TT4 Options Menu") == -1 and attempts > 2:
            self.serial.write("\x1b\x1b\x1b".encode("utf-8"))
            time.sleep(.2)
            self.serial.write("\x0d".encode("utf-8"))
            time.sleep(1)
            serinput += str(self.serial.read(100))
            print(serinput)
            attempts += 1
        if attempts > 2:
            raise APRSError()

        serinput = ""
        attempts = 0
        while serinput.find("Byonics MTT4B Alpha v0.73 (1284)") == -1 and attempts > 2:
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
            raise APRSError()
        return True

    @wrap_errors(APRSError)
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
            raise APRSError()
        return True

    @wrap_errors(APRSError)
    def functional(self) -> bool:
        """
        Checks the state of the serial port (initializing it if needed)
        Calls powered_on() to check whether APRS is on and working
        :return: (bool) APRS and serial connection are working
        """
        if self.serial is None:
            self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)
        self.enter_firmware_menu()
        self.exit_firmware_menu()
        return True

    @wrap_errors(APRSError)
    def enable_digi(self):  # TODO: Test these
        """
        Enables Hardware Digipeating
        """
        self.enter_firmware_menu()
        self.change_setting("BANK", "0")
        time.sleep(0.1)
        self.exit_firmware_menu()
        return True

    @wrap_errors(APRSError)
    def disable_digi(self):
        """
        Disables Hardware Digipeating
        This should also be run after initialization to set the default bank to 0
        """
        self.enter_firmware_menu()
        self.change_setting("BANK", "1")
        time.sleep(0.1)
        self.exit_firmware_menu()
        return True

    @wrap_errors(APRSError)
    def request_setting(self, setting) -> str:
        """
        Requests and returns value of given firmware setting. 
        Assumes firmware menu has already been entered successfully. Does not exit firmware menu afterwards
        :param setting: firmware setting to request
        :return: (str) text that APRS returns
        """
        self.serial.write((setting + "\x0d").encode("utf-8"))
        return self.serial.read(50).decode("utf-8")

    @wrap_errors(APRSError)
    def change_setting(self, setting, value) -> bool:
        """
        Changes value of given setting
        Assumes firmware menu has already been entered successfully. Does not exit firmware menu afterwards
        :param setting: setting to change
        :param value: value to change setting to
        :return: (bool) whether process worked
        """
        self.serial.write((setting + " " + str(value) + "\x0d").encode("utf-8"))
        result = self.serial.read(100).decode("utf-8")
        if result.find("COMMAND NOT FOUND") != -1:
            raise LogicalError(details="No such setting")
        if result.find("is") == -1 and result.find("was") == -1:
            raise APRSError(details="Failed to change setting")
        return True

    @wrap_errors(LogicalError)
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

    @wrap_errors(APRSError)
    def split_packet(self, packet: ResponsePacket) -> list:
        """
        Splits the packet into a list of packets which abide by size limits
        """
        result = []
        if packet.return_code == "ERR":
            data = packet.return_data()[0]
            descriptor = f"{packet.command_string}:{packet.return_code}:{packet.msn}:{packet.timestamp[0]}\
                -{packet.timestamp[1]}-{packet.timestamp[2]}:{packet.return_data[0]}::" # Includes the final : after the data
            ls = [data[0 + i:APRS.MAX_DATASIZE - len(descriptor) + i] for i in range(0, len(data), APRS.MAX_DATASIZE - len(descriptor))]
            result = [copy.deepcopy(packet) for _ in range(len(ls))]
            for _ in range(len(ls)):
                result[_].return_data = [ls[_]]
        else:
            data = packet.return_data()
            descriptor = f"{packet.command_string}:{packet.return_code}:{packet.msn}:{packet.timestamp[0]}\
                -{packet.timestamp[1]}-{packet.timestamp[2]}:{packet.return_data[0]}:" # Does not include the final : after the data
            ls = [[]]
            count = len(descriptor)
            for _ in range(len(data)):
                if count > APRS.MAX_DATASIZE:
                    count = len(descriptor)
                    ls.append([])
                count += len(f"{data[_]:.5}:")
                ls[-1].append(data[_])
            result = [copy.deepcopy(packet) for _ in range(len(ls))]
            for _ in range(len(ls)):
                result[_].return_data = ls[_]
        return result

    @wrap_errors(APRSError)
    def transmit(self, packet: ResponsePacket) -> bool:
        """
        Takes a descriptor and data, and transmits
        :param packet: (ResponsePacket) packet to transmit
        :return: (bool) success
        """
        if packet.simulate:
            return True
        self.sfr.logs["transmission"].write({
            "ts0": (t := time.time()) // 100000,
            "ts1": int(t % 100000),
            "radio": "APRS",
            "size": len(str(packet)),
        })
        return self.write(str(packet))

    @wrap_errors(APRSError)
    def next_msg(self):
        """
        Reads in any messages, process, and add to queue
        """
        msg = self.read()
        if msg.find(prefix := self.sfr.command_executor.TJ_PREFIX) != -1:
            processed = msg[msg.find(prefix) + len(prefix):].strip().split(":")[:-1]
            self.sfr.vars.command_buffer.append(ResponsePacket(processed[0], [float(s) for s in processed[2:]], int(processed[1])))
        elif msg.find(prefix := self.sfr.command_executor.OUTREACH_PREFIX) != -1:
            processed = msg[msg.find(prefix) + len(prefix):].strip().split(":")[:-1]
            self.sfr.vars.outreach_buffer.append(ResponsePacket(processed[0], [float(s) for s in processed[2:]], int(processed[1], outreach=True)))

    @wrap_errors(APRSError)
    def write(self, message: str) -> bool:
        """
        Writes the message to the APRS radio through the serial port
        :param message: (str) message to write
        :return: (bool) whether or not the write worked
        """
        self.serial.write((message + "\x0d").encode("utf-8"))
        self.serial.flush()
        return True

    @wrap_errors(APRSError)
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
        print(output.decode("utf-8"))
        return output.decode('utf-8')
