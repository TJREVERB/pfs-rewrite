import time, datetime
import math
from serial import Serial
import copy
from Drivers.transmission_packet import TransmissionPacket, FullPacket
from lib.exceptions import wrap_errors, IridiumError, LogicalError, InvalidCommandException, \
    NoSignalException
from Drivers.device import Device


# https://www.beamcommunications.com/document/328-iridium-isu-at-command-reference-v5
# https://docs.rockblock.rock7.com/reference/sbdwt
# https://www.ydoc.biz/download/IRDM_IridiumSBDService.pdf

# MO/Mobile Originated Buffer: Contains messages to be sent from iridium device
# MT/Mobile Terminated Buffer: Contains messages received from the Iridium constellation
# GSS: Iridium SBD Gateway Subsystem: Transfers messages from ISU to Ground
# ISU: Iridium Subscriber Unit: basically our radio
# FA: Field Application: basically our flight-pi

# FA <-UART/RS232 Interface-> ISU - MO buffer -> Iridium Constellation <-> GSS <-> IP Socket/Email
#                                <- MT buffer -

def is_hex(string):
    try:
        int(string, 16)
        return True
    except ValueError:
        return False
    

class Iridium(Device):
    AVG_TRANSMISSION_POWER = 1 # VERY VERY TENTATIVE NUMBER
    SERIAL_CONVERTERS = ["UART-RS232"]
    PORT = '/dev/serial0'
    BAUDRATE = 19200

    # Maximum permissible data size including descriptor size, in bytes. Hardware limitation should be 340 bytes total
    MAX_DATASIZE = 300

    EPOCH = datetime.datetime(2014, 5, 11, 14, 23, 55).timestamp()  # Set epoch date to 5 May, 2014, at 14:23:55 GMT

    ASCII_ARGS = {"ICE", "ZMV"}  # Commands whose arguments should be decoded as ascii

    @wrap_errors(IridiumError)
    def __init__(self, state_field_registry):
        super().__init__(state_field_registry)
        self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        while not self.serial.is_open:
            time.sleep(0.5)
        
        # Maps each 3 character string to a number code
        self.ENCODED_REGISTRY = list(self.sfr.command_executor.primary_registry.keys())
        self.ENCODED_REGISTRY.insert(0, "GRB")

        self.GEO_C = lambda: self.request("AT-MSGEO")  # Current geolocation, xyz cartesian
        # return format: <x>, <y>, <z>, <time_stamp>
        # time_stamp uses same 32 bit format as MSSTM

        # Performs a manual registration, consisting of attach and location update. No MO/MT messages transferred
        # Optional param location
        self.REGISTER = lambda location=None: self.request(f"AT+SBDREG={location}") if location \
            else self.request("AT+SBDREG")

        self.MODEL = lambda: self.request("AT+CGMM")
        self.PHONE_REV = lambda: self.request("AT+CGMR")
        self.IMEI = lambda: self.request("AT+CSGN")

        self.NETWORK_TIME = lambda: self.request("AT-MSSTM")
        # System time, GMT, retrieved from satellite network (used as a network check)
        # returns a 32 bit integer formatted in hex, with no leading zeros. Counts number of 90 millisecond intervals
        # that have elapsed since the epoch current epoch is May 11, 2014, at 14:23:55, and will change again around
        # 2026

        self.SHUTDOWN = lambda: self.request("AT*F", 1)
        self.RSSI = lambda: self.request("AT+CSQ", 10)  # Returns strength of satellite connection, may take up to
        # ten seconds if iridium is in satellite handoff
        self.LAST_RSSI = lambda: self.request("AT+CSQF")  # Returns last known signal strength, immediately

        # Sets unsolicited notifications of signal strength on or off
        self.CIER = lambda ls: self.request("AT+CIER=" + ",".join([str(s) for s in ls]))

        # Enable or disable ring indications for SBD Ring Alerts. When ring indication is enabled, ISU asserts RI
        # line and issues the unsolicited result code SBDRING when an SBD ring alert is received Ring alerts can only
        # be sent after the unit is registered :optional param b: set 1/0 enable/disable
        self.RING_ALERT = lambda b="": self.request(f"AT+SBDMTA{b}")

        # doesn't seem relevant to us?
        self.BAT_CHECK = lambda: self.request("AT+CBC")

        # Resets settings without power cycle
        self.SOFT_RST = lambda: self.request("ATZn", 1)

        # Load message into mobile originated buffer. SBDWT uses text, SBDWB uses binary. 
        self.SBD_WT = lambda message: self.request(f"AT+SBDWT={message}")
        # For SBDWB, input message byte length
        # Once "READY" is read in, write each byte, then the two least significant checksum bytes, MSB first
        # Final response: 0: success, 1: timeout (insufficient number of bytes transferred in 60 seconds)
        # 2: Checksum does not match calculated checksum, 3: message length too long or short
        # Keep messages 340 bytes or shorter
        self.SBD_WB = lambda length: self.write(f"AT+SBDWB={length}")
        # Read message from mobile terminated buffer. SBDRT uses text, SBDRB uses binary. Only one message is
        # contained in buffer at a time
        self.SBD_RT = lambda: self.request("AT+SBDRT")
        self.SBD_RB = lambda: self.write("AT+SBDRB")

        # Returns state of mobile originated and mobile terminated buffers
        # SBDS return format: <MO flag>, <MOMSN>, <MT flag>, <MTMSN>
        self.SBD_STATUS = lambda: self.request("AT+SBDS")  # beamcommunications 101-102
        # SBDSX return format: <MO flag>, <MOMSN>, <MT Flag>, <MTMSN>, <RA flag>, <msg waiting>
        self.SBD_STATUS_EX = lambda: self.request("AT+SBDSX")  # beamcommunications 103
        # MO flag: (1/0) whether message in mobile originated buffer
        # MOMSN: sequence number that will be used in the next mobile originated SBD session
        # MT flag: (1/0) whether message in mobile terminated buffer
        # MTMSN: sequence number in the next mobile terminated SBD session, -1 if nothing in the MT buffer
        # RA flag: (1/0) whether an SBD ring alert has been received and needs to be answered
        # msg waiting: how many SBD mobile terminated messages are queued at the gateway for collection by ISU

        # Reads or sets session timeout settings, after which time ISU will stop trying to transmit/receive to GSS,
        # in seconds. 0 means infinite timeout
        self.SBD_TIMEOUT = lambda t=None: self.request(f"AT+SBDST={t}") if t else self.request("AT+SBDST")

        # Transfers contents of mobile originated buffer to mobile terminated buffer, to test reading and writing to
        # ISU without initiating SBD sessions with GSS/ESS returns response of the form "SBDTC: Outbound SBD copied
        # to Inbound SBD: size = <size>" followed by "OK", where size is message length in bytes
        self.SBD_TRANSFER_MOMT = lambda: self.request("AT+SBDTC")  # beamcommunications 104

        # Transmits contents of mobile originated buffer to GSS, transfer oldest message in GSS queuefrom GSS to ISU
        self.SBD_INITIATE = lambda: self.request("AT+SBDI", 60)  # beamcommunications 94-95
        # Like SBDI but it always attempts SBD registration, consisting of attach and location update. a should be
        # "A" if in response to SBD ring alert, otherwise unspecified. location is an optional param,
        # format =[+|-]DDMM.MMM, [+|-]dddmm.mmm
        self.SBD_INITIATE_EX = lambda a="", location="": self.request("AT+SBDIX" + a, 60) if len(location) == 0 \
            else self.request("AT+SBDIX" + a + "=" + location)  # beamcommunications 95-96
        # returns: <MO status>,<MOMSN>,<MT status>,<MTMSN>,<MT length>,<MT queued>
        # MO status: 0: no message to send, 1: successful send, 2: error while sending
        # MOMSN: sequence number for next MO transmission
        # MT status: 0: no message to receive, 1: successful receive, 2: error while receiving
        # MTMSN: sequence number for next MT receive
        # MT length: length in bytes of received message
        # MT queued: number of MT messages in GSS waiting to be transferred to ISU

        # Clear one or both buffers. BUFFERS MUST BE CLEARED AFTER ANY MESSAGING ACTIVITY
        # param type: buffers to clear. 0 = mobile originated, 1 = mobile terminated, 2 = both
        # returns bool if buffer wasnt cleared successfully (1 = error, 0 = successful)
        self.SBD_CLR = lambda type: self.request("AT+SBDD" + str(type))

    @wrap_errors(IridiumError)
    def terminate(self):
        self.check_buffer()
        self.SHUTDOWN()
        self.serial.close()

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Iridium"

    @wrap_errors(IridiumError)
    def serial_test(self) -> bool:
        """
        Checks the state of the serial port (initializing it if needed) and verifies that AT returns OK
        :return: (bool) serial connection is working
        """
        if self.serial is None:
            self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        self.serial.flush()
        result = self.request("AT", 1)  # Give Iridium one second to respond
        if result.find("OK") != -1:
            return True
        raise IridiumError()

    @wrap_errors(IridiumError)
    def functional(self):
        """
        Tests Iridium by loading a message into one buffer, transferring to the other, and reading the message
        :return: (bool) buffers functional
        """
        self.serial_test()
        result = self.request("AT+SBDWT=test")
        if result.find("OK") == -1:
            raise IridiumError(details="Error writing to MO")
        result = self.request("AT+SBDTC", 1)
        if result.find("Outbound SBD Copied to Inbound SBD: size = 4") == -1:
            raise IridiumError(details="Error transferring buffers")
        result = self.request("AT+SBDRT")
        if result.find("test") == -1:
            raise IridiumError(details="Error reading message from MT")
        self.write("AT+SBDD2")  # clear all buffers
        return True

    @wrap_errors(IridiumError)
    def check_signal_active(self):
        """
        Passively check signal strength, for transmit/receive timing
        """
        raw = self.RSSI()
        if raw.find("CSQ:") == -1:
            return 0
        return int(raw[raw.find("CSQ:") + 4: raw.find("CSQ:") + 5])

    @wrap_errors(IridiumError)
    def check_signal_passive(self):
        """
        Passively check signal strength, for transmit/receive timing
        """
        raw = self.LAST_RSSI()
        if raw.find("CSQF:") == -1:
            return 0
        return int(raw[raw.find("CSQF:") + 5: raw.find("CSQF:") + 6])

    @wrap_errors(IridiumError)
    def process(self, data, cmd):
        """
        Clean up data string
        :param data: (str) to format
        :param cmd: (str) command, do not include AT prefix
        """
        return data.split(cmd + ":")[1].split("\r\nOK")[0].strip()

    @wrap_errors(IridiumError)
    def encode(self, packet:TransmissionPacket):
        """
        Encodes string for transmit using numbered codes
        :param packet: (TransmissionPacket) packet to encode
        :return: (list) of bytes
        """
        encoded = [(packet.response << 1) | packet.numerical, packet.index]  # First byte "return code"
        date = (packet.timestamp.day << 11) | (packet.timestamp.hour << 6) | packet.timestamp.minute  # third and fourth bytes date
        encoded.append((date >> 8) & 0xff)
        encoded.append(date & 0xff)
        if packet.response:
            if packet.descriptor in self.ENCODED_REGISTRY:
                encoded.append(self.ENCODED_REGISTRY.index(packet.descriptor)) # Fifth byte descriptor
            else:
                raise LogicalError(details="Invalid descriptor string")
            encoded.append((packet.msn >> 8) & 0xff) # Sixth and Seventh byte msn
            encoded.append(packet.msn & 0xff)
        else:
            if packet.numerical:
                if packet.descriptor in self.ENCODED_REGISTRY:
                    encoded.append(self.ENCODED_REGISTRY.index(packet.descriptor)) # Fifth byte descriptor
                else:
                    raise LogicalError(details="Invalid descriptor string")

        if packet.numerical:
            for n in packet.return_data:
                # Jank way to check for NaN without figuring out where to import it from
                try:
                    n = float(n)
                    int(n)
                except ValueError as e:
                    if "nan" in repr(e) or "NaN" in repr(e):
                        n = 0
                    else:
                        raise ValueError(repr(e))
                #  convert from float or int to twos comp half precision, bytes are MSB FIRST
                flt = 0
                if n != 0:
                    exp = int(math.floor(math.log10(abs(n))))
                else:
                    exp = 0
                if exp < 0:
                    exp = abs(exp)
                    exp &= 0xf  # make sure exp is 4 bits, cut off anything past the 4th
                    signexp = (1 << 4) - exp  # twos comp
                    flt |= signexp << 19
                    flt |= 1 << 23
                else:
                    flt |= (exp & 0xf) << 19  # make sure exp is 4 bits, cut off anything past the 4th, shift left 19
                # num will always have five digits, with trailing zeros if necessary to fill it in
                num = abs(int((n / (10 ** exp)) * 10000))
                if n < 0:
                    num &= 0x3ffff  # make sure num is 18 bits long
                    num = (1 << 18) - num  # twos comp
                    flt |= num
                    flt |= (1 << 18)  # set sign bit
                else:
                    flt |= num & 0x3ffff  # make sure num is 18 bits long
                byte1 = (flt >> 16) & 0xff
                byte2 = (flt >> 8) & 0xff
                byte3 = flt & 0xff
                encoded.append(byte1)  # MSB FIRST
                encoded.append(byte2)
                encoded.append(byte3)  # LSB LAST
        else:
            data = packet.return_data[0].encode("ascii")
            for d in data:
                encoded.append(d)
        return encoded

    @wrap_errors(IridiumError)
    def decode(self, message):
        """
        Decodes received and processed string from SBDRB and converts to string
        Truncates unused bits
        CALL PROCESS BEFORE CALLING DECODE
        :param message: (list) received list of bytes
        :return: (tup) decoded command and args
        """
        length = message[:2]  # check length and checksum against message length and sum
        length = length[1] + (length[0] << 8)
        checksum = message[-2:]
        checksum = checksum[1] + (checksum[0] << 8)
        msg = message[2:-2]
        actual_checksum = sum(msg) & 0xffff

        if checksum != actual_checksum or length != len(msg):
            raise IridiumError(details="Incorrect checksum/length")
        if msg[0] < 0 or msg[0] >= len(self.ENCODED_REGISTRY):
            raise InvalidCommandException(details="Invalid command received")
        decoded = self.ENCODED_REGISTRY[msg[0]]
        args = []

        if decoded in Iridium.ASCII_ARGS:
            args = ["".join([chr(i) for i in msg[1:]])]
        else:
            for i in range(1, len(msg) - 2, 3):
                num = (msg[i] << 16) | (msg[i + 1] << 8) | (msg[i + 2])  # msb first
                exp = num >> 19  # extract exponent
                if exp & (1 << 4) == 1:  # convert twos comp
                    exp &= 0x10  # truncate first bit
                    exp -= (1 << 4)
                coef = num & 0x7ffff  # extract coefficient
                if coef & (1 << 18) == 1:  # convert twos comp
                    coef &= 0x3ffff  # truncate first bit
                    coef -= (1 << 18)
                if coef != 0:
                    coef /= 10 ** int(math.log10(abs(coef)))
                args.append(coef * 10 ** exp)
        if decoded == "ARS":
            if args[0] < 0 or args[0] >= len(self.ENCODED_REGISTRY):
                raise InvalidCommandException(details="Invalid command received")
            args[0] = self.ENCODED_REGISTRY[int(args[0])]
        return (decoded, args)

    @wrap_errors(IridiumError)
    def split_packet(self, packet: TransmissionPacket) -> list:
        """
        Splits the packet into a list of packets which abide by size limits
        """
        if len(packet.return_data) == 0:
            # Special case to avoid losing packets with zero data
            return [packet]

        FLOAT_LEN = 3

        DESCRIPTOR_LEN = 4
        if packet.response:
            DESCRIPTOR_LEN = 7
        elif packet.numerical:
            DESCRIPTOR_LEN = 5

        if packet.numerical:
            data = packet.return_data
            ls = [data[0 + i:(Iridium.MAX_DATASIZE-DESCRIPTOR_LEN)//FLOAT_LEN + i] for i in range(
                0, len(data), (Iridium.MAX_DATASIZE-DESCRIPTOR_LEN)//FLOAT_LEN)]
            result = [copy.deepcopy(packet) for _ in range(len(ls))]
            for _ in range(len(ls)):
                result[_].return_data = ls[_]
                result[_].index = _
        else:
            data = packet.return_data[0]
            if len(data) == 0:
                return [packet]
            ls = [data[0 + i:Iridium.MAX_DATASIZE-DESCRIPTOR_LEN + i] for i in range(0, len(data), Iridium.MAX_DATASIZE-DESCRIPTOR_LEN)]
            result = [copy.deepcopy(packet) for _ in range(len(ls))]
            for _ in range(len(ls)):
                result[_].return_data = [ls[_]]
                result[_].index = _
        return result

    @wrap_errors(IridiumError)
    def transmit(self, packet: TransmissionPacket, discardmtbuf=False) -> bool:
        """
        Loads message into MO buffer, then transmits
        If a message has been received, read it into SFR
        Clear buffers once done
        :param packet: (TransmissionPacket) packet to transmit
        :param discardmtbuf: (bool) if False: Store contents of MO buffer before reading in new messages.
            if True: Discard contents of MO buffer when reading in new messages.
        :return: (bool) transmission successful
        """
        stat = self.SBD_STATUS()
        ls = self.process(stat, "SBDS").split(", ")
        if int(ls[2]) == 1:  # If message in MT, and discardbuf False, save MT to sfr
            if not discardmtbuf:
                self.check_buffer()
        if self.SBD_CLR(2).find("0\r\n\r\nOK") == -1:
            raise IridiumError(details="Error clearing buffers")
        result = self.transmit_raw(raw := self.encode(packet))
        self.sfr.logs["transmission"].write({  # Log transmission
            "ts0": (t := time.time()) // 100000,
            "ts1": int(t % 100000),
            "radio": "Iridium",
            "size": len(raw),
        })
        if result[0] not in [0, 1, 2, 3, 4]:
            match result[0]:
                case 33:
                    raise IridiumError(details="Error transmitting buffer, Antenna fault")
                case 16:
                    raise IridiumError(details="Error transmitting buffer, ISU locked")
                case 15:
                    raise IridiumError(details="Error transmitting buffer, Gateway reports that Access is Denied")
                case 10 | 11| 12 | 13 | 14 | 17 | 18 | 19 | 32 | 35 | 36 | 37 | 38: 
                    # These all vaguely indicate no signal, or at least the issue is not hardware fault
                    raise NoSignalException()
                case 65:
                    raise IridiumError(details="Error transmitting buffer, Hardware Error (PLL Lock failure)")
                case 34:
                    raise IridiumError(details="Error transmitting buffer, Radio is disabled (see AT*Rn)")
                case _:
                    raise IridiumError(details=f"Error transmitting buffer, error code {result[0]}")
        if result[2] == 1:
            self.check_buffer()
        if self.SBD_CLR(2).find("0\r\n\r\nOK") == -1:
            raise IridiumError(details="Error clearing buffers")
        return True

    @wrap_errors(IridiumError)
    def transmit_raw(self, message):
        """
        Transmits raw message using SBDWB, ignore MT buffer
        Use as a helper function for transmit
        :param message: (list) message, of encoded bytes.
        """
        rssi = self.RSSI()
        if rssi.find("CSQ:0") != -1 or rssi.find("OK") == -1:  # check signal strength first
            raise NoSignalException(details="No Signal")
        length = len(message)
        checksum = sum(message) & 0xffff
        message.append(checksum >> 8)  # add checksum bytes
        message.append(checksum & 0xff)
        self.SBD_WB(length)  # Specify bytes to write
        time.sleep(1)  # 1 second to respond
        if self.read().find("READY") == -1:
            raise IridiumError(details="Serial Timeout")
        self.serial.write(message)
        time.sleep(1)  # 1 second to respond
        result = ""
        t = time.perf_counter()
        while result.find("OK") == -1:
            if time.perf_counter() - t > 5:
                raise IridiumError(details="Serial Timeout")
            result += self.read()
        i = int(result.split("\r\n")[1])  # '\r\n0\r\n\r\nOK\r\n' format
        if i == 1:
            raise IridiumError(details="Serial Timeout")
        if i == 2:
            raise IridiumError(details="Incorrect Checksum")
        if i == 3:
            raise IridiumError(details="Message too long")
        self.SBD_TIMEOUT(60)  # 60 second timeout for transmit
        sttime = time.perf_counter()
        result = [int(s) for s in self.process(self.SBD_INITIATE_EX(), "SBDIX").split(",")]
        self.sfr.vars.BATTERY_CAPACITY_INT -= (time.perf_counter() - sttime) * Iridium.AVG_TRANSMISSION_POWER
        return result

    @wrap_errors(IridiumError)
    def check_buffer(self):
        """
        Checks buffer for existing messages
        """
        stat = self.SBD_STATUS()
        ls = self.process(stat, "SBDS").split(", ")
        if int(ls[2]) == 1:  # Save MT to sfr
            try:
                self.SBD_RB()
                raw = self.serial.read(50)
                t = time.perf_counter()
                while raw.find(b'OK') == -1:
                    if time.perf_counter() - t > 5:
                        raise IridiumError(details="Serial Timeout")
                    raw += self.serial.read(50)
                raw = raw[raw.find(b'SBDRB\r\n') + 7:].split(b'\r\nOK')[0]
                self.sfr.vars.command_buffer.append(FullPacket(*self.decode(list(raw)), int(ls[3])))
            except Exception as e:
                self.sfr.vars.command_buffer.append(FullPacket("GRB", [repr(e)], int(ls[3])))
                # Append garbled message indicator and msn, args set to exception string to debug
        if self.SBD_CLR(2).find("0\r\n\r\nOK") == -1:
            raise IridiumError(details="Error clearing buffers")

    @wrap_errors(IridiumError)
    def next_msg(self):
        """
        Stores next received messages in sfr
        """
        self.check_buffer()
        self.SBD_TIMEOUT(60)
        time.sleep(1)
        result = [0, 0, 0, 0, 0, 1]
        lastqueued = []
        while result[5] >= 0:
            result = [int(s) for s in self.process(self.SBD_INITIATE_EX(), "SBDIX").split(",")]
            lastqueued.append(result[5])
            if len(lastqueued) > 3 and sum(lastqueued[-3:]) / 3 == lastqueued[-1]:
                break  # If GSS queue is not changing, don't bother to keep trying, just break
            if result[2] == 1:
                try:
                    self.SBD_RB()
                    raw = self.serial.read(50)
                    t = time.perf_counter()
                    while raw.find(b'OK') == -1:
                        if time.perf_counter() - t > 5:
                            raise IridiumError(details="Serial Timeout")
                        raw += self.serial.read(50)
                    raw = raw[raw.find(b'SBDRB\r\n') + 7:].split(b'\r\nOK')[0]
                    self.sfr.vars.command_buffer.append(FullPacket(*self.decode(list(raw)), int(result[3])))
                except Exception as e:
                    self.sfr.vars.command_buffer.append(FullPacket("GRB", [repr(e)], int(result[3])))
                    # Append garbled message indicator and msn
            elif result[2] == 0:
                break
            elif result[2] == 2:
                break
            time.sleep(2.5)
        if self.SBD_CLR(2).find("0\r\n\r\nOK") == -1:
            raise IridiumError(details="Error clearing buffers")

    @wrap_errors(IridiumError)
    def processed_time(self):
        """
        Requests, reads, processes, and returns current system time retrieved from network
        :return: (datetime) current time (use str() to parse to string if needed)
        """
        raw = self.NETWORK_TIME()
        if raw.find("OK") == -1:
            raise IridiumError()
        if raw.find("no network service") != -1:
            raise NoSignalException()
        raw = raw.split("MSSTM:")[1].split("\n")[0].strip()
        if is_hex(raw):
            processed = int(raw, 16) * 90 / 1000
            return datetime.datetime.fromtimestamp(processed + Iridium.EPOCH)
        return None

    @wrap_errors(IridiumError)
    def processed_geolocation(self):
        """
        Requests, reads, processes, and returns current geolocation
        :return: (tuple) lat, long, altitude (0,0,0 if unable to retrieve)
        """
        raw = self.process(self.GEO_C(), "MSGEO").split(",")  # raw x, y, z, timestamp
        timestamp_time = int(raw[3], 16) * 90 / 1000 + Iridium.EPOCH
        current_time = self.processed_time()
        if current_time is None:
            return (0, 0, 0)
        if current_time.timestamp() - timestamp_time > 60:
            # Checks if time passed since last geolocation update has been more than 60 seconds
            result = [int(s) for s in self.process(self.SBD_INITIATE_EX(), "SBDIX").split(",")]  
            # Use SBDIX to update geolocation
            if result[0] not in [0, 1, 3, 4]:
                return (0, 0, 0)
            raw = self.process(self.GEO_C(), "MSGEO").split(",")  # try again
        lon = math.degrees(math.atan2(float(raw[1]), float(raw[0])))
        lat = math.degrees(math.atan2(float(raw[2]), ((float(raw[1]) ** 2 + float(raw[0]) ** 2) ** 0.5)))
        alt = (float(raw[0]) ** 2 + float(raw[1]) ** 2 + float(raw[2]) ** 2) ** 0.5
        return (lat, lon, alt)

    @wrap_errors(IridiumError)
    def request(self, command: str, timeout=0.5) -> str:
        """
        Requests information from Iridium and returns unprocessed response
        :param command: Command to send
        :param timeout: maximum time to wait for a response
        :return: (str) Response from Iridium
        """
        self.serial.flush()
        self.write(command)
        result = ""
        sttime = time.perf_counter()
        while time.perf_counter() - sttime < timeout:
            time.sleep(.1)
            result += self.read()
            if result.find("ERROR") != -1:
                return command[2:] + "ERROR" + "\n"  # formatted so that process() can still decode properly
            if result.find("OK") != -1:
                return result
        raise IridiumError(details="Incomplete response")

    @wrap_errors(IridiumError)
    def write(self, command: str) -> bool:
        """
        Write a command to the serial port.
        :param command: (str) Command to write
        :return: (bool) if the serial write worked
        """
        self.serial.write((command + "\r\n").encode("utf-8"))
        return True

    @wrap_errors(IridiumError)
    def read(self) -> str:
        """
        Reads in as many available bytes as it can if timeout permits.
        :return: (str) string read from iridium
        """
        output = bytes()
        for _ in range(50):
            try:
                next_byte = self.serial.read(size=1)
            except:
                break
            if next_byte == bytes():
                break
            output += next_byte
        return output.decode("utf-8")
