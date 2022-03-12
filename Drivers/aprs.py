from serial import Serial
import time
from Drivers.transmission_packet import TransmissionPacket, FullPacket
from lib.exceptions import wrap_errors, APRSError, LogicalError
from Drivers.device import Device
import copy


class APRS(Device):
    TRANSMISSION_ENERGY = 4.8  # Energy used per transmission, in J
    SERIAL_CONVERTERS = ["USB-UART"]
    PORT = '/dev/ttyACM0'
    DEVICE_PATH = '/sys/devices/platform/soc/20980000.usb/buspower'
    BAUDRATE = 19200
    MAX_DATASIZE = 100

    @wrap_errors(APRSError)
    def __init__(self, state_field_registry):
        super().__init__(state_field_registry)
        try:
            self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        except:
            self.clear_data_lines()
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
        print("entering firmware")
        self.write("\x1b\x1b\x1b")
        time.sleep(1)
        self.write("\x1b\x1b\x1b")
        time.sleep(1)
        self.write("\x1b\x1b\x1b")
        time.sleep(1)
        self.write("\x1b\x1b\x1b")
        time.sleep(1)
        self.write("\x1b\x1b\x1b")
        time.sleep(3)
        serinput = str(self.serial.read(300))
        print(serinput)
        if serinput.find("Byonics MTT4B Alpha") == -1:
            print("Failed")
            raise APRSError(details="Failed to enter firmware menu")
            
        return True

    @wrap_errors(APRSError)
    def exit_firmware_menu(self) -> bool:
        """
        Exit APRS firmware menu
        :return: whether exit was successful
        """
        self.write("QUIT")
        time.sleep(.5)
        result = str(self.serial.read(100))
        if result.find("Press ESC 3 times to enter TT4 Options Menu") == -1:
            raise APRSError(details="Failed to exit firmware")
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
    def enable_digi(self): 
        """
        Enables Hardware Digipeating
        """
        self.enter_firmware_menu()
        time.sleep(1)
        self.change_setting("TXFREQ", "144.39") #TODO: 145.825
        time.sleep(0.2)
        self.change_setting("RXFREQ", "144.39")
        time.sleep(0.2)
        self.change_setting("ALIAS1", "APRSAT")
        time.sleep(0.2)
        self.change_setting("ALIAS2", "ARISS")
        time.sleep(0.2)
        self.change_setting("ALIAS3", "WIDE")
        time.sleep(0.2)
        self.change_setting("PATH1", "ARISS")
        time.sleep(0.2)
        self.change_setting("PATH2", "WIDE2-1")
        time.sleep(0.2) 
        self.change_setting("HIPWR", "1")
        time.sleep(1)
        self.exit_firmware_menu()
        return True

    @wrap_errors(APRSError)
    def disable_digi(self):
        """
        Disables Hardware Digipeating
        This should also be run after initialization to set the default bank to 0
        """
        self.enter_firmware_menu()
        time.sleep(1)
        self.change_setting("TXFREQ", "144.39") #TODO: 145.825
        time.sleep(0.2)
        self.change_setting("RXFREQ", "144.39")
        time.sleep(0.2)
        self.change_setting("ALIAS1", "TEMP")
        time.sleep(0.2)
        self.change_setting("ALIAS2", "none")
        time.sleep(0.2)
        self.change_setting("ALIAS3", "none")
        time.sleep(0.2)
        self.change_setting("PATH1", "ARISS")
        time.sleep(0.2)
        self.change_setting("PATH2", "WIDE2-1")
        time.sleep(0.2) 
        self.change_setting("HIPWR", "1")
        time.sleep(1)
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
        self.write(setting)
        return self.read()

    @wrap_errors(APRSError)
    def change_setting(self, setting, value) -> bool:
        """
        Changes value of given setting
        Assumes firmware menu has already been entered successfully. Does not exit firmware menu afterwards
        :param setting: setting to change
        :param value: value to change setting to
        :return: (bool) whether process worked
        """
        self.write(setting + " " + str(value))
        result = self.read()
        print(result)
        if result.find("COMMAND NOT FOUND") != -1:
            raise LogicalError(details="No such setting")
        if result.find("is") == -1 and result.find("was") == -1:
            self.write(setting + " " + str(value))
            result = self.read()
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
        time.sleep(10)
        with open(self.DEVICE_PATH, "w") as f:
            f.write(str(1))
        time.sleep(5)

    @staticmethod
    @wrap_errors(APRSError)
    def split_packet(packet: TransmissionPacket) -> list:
        """
        Splits the packet into a list of packets which abide by size limits
        """
        if len(packet.return_data) == 0:
            # Special case to avoid losing packets with zero data
            return [packet]

        result = []
        if packet.numerical:
            data = packet.return_data
        else:
            data = packet.return_data[0]
            if len(data) == 0:
                return [packet]

        result.append(packet)
        lastindex = 0
        for i in range(len(data)):
            pckt = copy.deepcopy(result[-1])
            if packet.numerical:
                pckt.return_data = data[lastindex:i]
            else:
                pckt.return_data = [data[lastindex:i]]
            pckt.index = len(result) - 1
            if len(str(pckt)) <= APRS.MAX_DATASIZE:
                result[-1] = pckt
            else:
                lastindex = i
                pckt = copy.deepcopy(packet)
                pckt.return_data = [data[i]]
                pckt.index = len(result)
                result.append(pckt)
        return result

    @wrap_errors(APRSError)
    def transmit(self, packet: TransmissionPacket) -> bool:
        """
        Takes a descriptor and data, and transmits
        :param packet: (TransmissionPacket) packet to transmit
        :return: (bool) success
        """
        self.sfr.logs["transmission"].write({
            "ts0": (t := time.time()) // 100000,
            "ts1": int(t % 100000),
            "radio": "APRS",
            "size": len(str(packet)),
        })
        self.sfr.vars.BATTERY_CAPACITY_INT -= APRS.TRANSMISSION_ENERGY
        return self.write(str(packet))

    @wrap_errors(APRSError)
    def next_msg(self):
        """
        Reads in any messages, process, and add to queue
        """
        msg = self.read()
        print(msg)
        if msg.find(prefix := self.sfr.command_executor.TJ_PREFIX) != -1:
            print("TJ message received")
            processed = msg[msg.find(prefix) + len(prefix):].strip().split(":")[:-1]
            print(processed)
            if processed[0] in self.sfr.command_executor.primary_registry.keys():
                self.sfr.vars.command_buffer.append(FullPacket(processed[0], [float(s) for s in processed[2:]], int(processed[1])))
        elif msg.find(prefix := self.sfr.command_executor.OUTREACH_PREFIX) != -1:
            print("Outreach message received")
            processed = msg[msg.find(prefix) + len(prefix):].strip().split(":")[:-1]
            if processed[0] in self.sfr.command_executor.secondary_registry.keys():
                self.sfr.vars.outreach_buffer.append(FullPacket(processed[0], [float(s) for s in processed[2:]], int(processed[1]), outreach=True))

    @wrap_errors(APRSError)
    def write(self, message: str) -> bool:
        """
        Writes the message to the APRS radio through the serial port
        :param message: (str) message to write
        :return: (bool) whether or not the write worked
        """
        print(message)
        for i in list(message):
            self.serial.write(i.encode("utf-8"))
            time.sleep(.05)
        self.serial.write("\x0d".encode("utf-8"))
        #self.serial.write((message + "\x0d").encode("utf-8"))
        return True

    @wrap_errors(APRSError)
    def read(self) -> str:
        """
        Reads in as many available bytes as it can if timeout permits (terminating at a \n).
        :return: (str) message read ("" if no message read)
        """
        output = self.serial.read(300)
        print(output.decode("utf-8"))
        return output.decode('utf-8')
