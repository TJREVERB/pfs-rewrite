import time, datetime
import math
import pandas as pd
from serial import Serial
from MainControlLoop.Drivers.transmission_packet import TransmissionPacket

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

class Iridium:
    PORT = '/dev/serial0'
    BAUDRATE = 19200

    EPOCH = datetime.datetime(2014, 5, 11, 14, 23, 55).timestamp()  # Set epoch date to 5 May, 2014, at 14:23:55 GMT

    ENCODED_REGISTRY = [  # Maps each 3 character string to a number code
            "MCH",
            "MSC",
            "MOU",
            "MRP",
            "MLK",
            "MDF",
            "DLK",
            "DDF",
            "GCR",
            "GVT",
            "GPL",
            "GCD",
            "GPW",
            "GOP",
            "GCS",
            "GSV",
            "GSG",
            "GTB",
            "GMT",
            "GST",
            "GTS",
            "AAP",
            "APW",
            "ASV",
            "ASG",
            "ATB",
            "AMS",
            "SUV",
            "SLV",
            "USM",
            "ULG",
            "ITM",
            "IPC",
        ]

    RETURN_CODES = [
        "0OK", # 0, MSG received and executed
        "ERR"  # 1, MSG received and read, but error executing or reading
    ]

    def __init__(self, state_field_registry):
        self.sfr = state_field_registry
        self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        while not self.serial.is_open:
            time.sleep(0.5)
        self.GEO_C = lambda: self.request("AT-MSGEO")  # Current geolocation, xyz cartesian
        # return format: <x>, <y>, <z>, <time_stamp>
        # time_stamp uses same 32 bit format as MSSTM

        # Performs a manual registration, consisting of attach and location update. No MO/MT messages transferred
        # Optional param location
        self.REGISTER = lambda location="": self.request("AT+SBDREG") if len(location) == 0 \
                                            else self.request("AT+SBDREG=" + location)

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

        self.CIER = lambda ls: self.request("AT+CIER=" + ",".join([str(s) for s in ls])) #Sets unsolicited notifications of signal strength on or off

        # Enable or disable ring indications for SBD Ring Alerts. When ring indication is enabled, ISU asserts RI
        # line and issues the unsolicited result code SBDRING when an SBD ring alert is received Ring alerts can only
        # be sent after the unit is registered :optional param b: set 1/0 enable/disable
        self.RING_ALERT = lambda b="": self.request("AT+SBDMTA") if len(str(b)) == 0 \
                                        else self.request("AT+SBDMTA" + str(b))

        # doesn't seem relevant to us?
        self.BAT_CHECK = lambda: self.request("AT+CBC")

        # Resets settings without power cycle
        self.SOFT_RST = lambda: self.request("ATZn", 1)

        # Load message into mobile originated buffer. SBDWT uses text, SBDWB uses binary. 
        self.SBD_WT = lambda message: self.request("AT+SBDWT=" + message)
        # For SBDWB, input message byte length
        # Once "READY" is read in, write each byte, then the two least significant checksum bytes, MSB first
        # Final response: 0: success, 1: timeout (insufficient number of bytes transferred in 60 seconds)
        # 2: Checksum does not match calculated checksum, 3: message length too long or short
        # Keep messages 340 bytes or shorter
        self.SBD_WB = lambda length: self.write("AT+SBDWB=" + str(length))
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
        self.SBD_TIMEOUT = lambda time="": self.request("AT+SBDST") if len(str(time)) == 0 \
                                            else self.request("AT+SBDST=" + str(time))

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

    def __del__(self):
        self.write("AT*F")  # SHUTDOWN
        time.sleep(1)
        self.serial.close()

    def __str__(self):
        return "Iridium"

    def serial_test(self) -> bool:
        """
        Checks the state of the serial port (initializing it if needed) and verifies that AT returns OK
        :return: (bool) serial connection is working
        """
        if self.serial is None:
            try:
                self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
            except:
                return False
        if not self.serial.is_open:
            try:
                self.serial.open()
            except:
                return False
        self.serial.flush()
        try:
            result = self.request("AT", 1) # Give Iridium one second to respond
            if result.find("OK") != -1:
                return True
            return False
        except UnicodeDecodeError:
            return False

    def functional(self):
        """
        Tests Iridium by loading a message into one buffer, transferring to the other, and reading the message
        :return: (bool) buffers functional
        """
        if self.serial is None:
            try:
                self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
            except:
                return False
        if not self.serial.is_open:
            try:
                self.serial.open()
            except:
                return False
        self.serial.flush()
        try:
            result = self.request("AT+SBDWT=test")
            if result.find("OK") == -1:
                raise RuntimeError("Error writing to MO")
            result = self.request("AT+SBDTC", 1)
            if result.find("Outbound SBD Copied to Inbound SBD: size = 4") == -1:
                raise RuntimeError("Error transferring buffers")
            result = self.request("AT+SBDRT")
            if result.find("test") == -1:
                raise RuntimeError("Error reading message from MT")
            self.write("AT+SBDD2")  # clear all buffers
            return True
        except UnicodeDecodeError:
            return False

    def enable_notif(self):
        """
        Enable RSSI and service notifications
        """
        return self.CIER([1,1,1]).find("OK") != -1
    
    def disable_notif(self):
        """
        Disable RSSI and service notifications
        """
        return self.CIER([0,0,0]).find("OK") != -1

    def check_notif(self, threshold=2):
        """
        Checks if any notification has been received
        :return: (int) code: 0: signal status unchanged, 1: signal not present, 2: signal present
        """
        b = self.read()
        if b.find("+CIEV:") == -1:
            return 0
        b = b[b.find("+CIEV:") + 6:].strip().split(",")
        if int(b[0]) == 0:
            if int(b[1]) >= threshold:
                return 2
            else:
                return 1
        if int(b[0]) == 1:
            if int(b[1]) == 1:
                return 2
            else:
                return 1

    def process(self, data, cmd):
        """
        Clean up data string
        :param data: (str) to format
        :param cmd: (str) command, do not include AT prefix
        """
        return data.split(cmd + ":")[1].split("\r\nOK")[0].strip()

    def encode(self, descriptor, return_code, msn, time, data):
        """
        Encodes string for transmit using numbered codes
        :param descriptor: (str) 3 character string code
        :param msn: (int) message sequence number of command response
        :param time: (tuple) time of command execution, in (days, hours, minutes)
        :param data: (list) of data values to encode, in order.
        :param err: (bool) if True, encode data as string error message (single length list containing error string). 
        if False (default), encode data as float values
        :return: (list) of bytes
        """

        if descriptor in Iridium.ENCODED_REGISTRY: #First byte descriptor
            encoded = [Iridium.ENCODED_REGISTRY.index(descriptor)]
        else:
            raise RuntimeError("Invalid descriptor string")

        if return_code in Iridium.RETURN_CODES: #Second byte return code
            encoded.append(Iridium.RETURN_CODES.index(return_code))
        else:
            raise RuntimeError("Invalid return code")
        
        encoded.append((msn >> 8) & 0xff) # third and fourth bytes msn, msb first
        encoded.append(msn & 0xff)

        date = (time[0] << 11) | (time[1] << 6) | time[2] # fifth and sixth bytes date, msb first

        encoded.append((date >> 8) & 0xff)
        encoded.append(date & 0xff)

        if return_code == "ERR":
            data = data[0].encode("ascii")
            for d in data:
                encoded.append(d)
        else:
            for n in data:
                # convert from float or int to twos comp half precision, bytes are MSB FIRST
                flt = 0
                exp = int(math.log10(abs(n)))
                if exp < 0:
                    exp = abs(exp) + 1
                    exp &= 0xf  # make sure exp is 4 bits, cut off anything past the 4th
                    exp = (1 << 4) - exp  # twos comp
                    flt |= exp << 11
                    flt |= 1 << 15
                else:
                    flt |= (exp & 0xf) << 11  # make sure exp is 4 bits, cut off anything past the 4th, shift left 11
                num = int((n / (10 ** exp)) * 100)  # num will always have three digits, with trailing zeros if necessary to fill it in
                if n < 0:
                    num &= 0x3ff  # make sure num is 10 bits long
                    num = (1 << 10) - num  # twos comp
                    flt |= num
                    flt |= (1 << 10)  # set sign bit
                else:
                    flt |= num & 0x3ff  # make sure num is 10 bits long
                byte1 = flt >> 8
                byte2 = flt & 0xff
                encoded.append(byte1)  # MSB FIRST
                encoded.append(byte2)  # LSB LAST
        return encoded

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

        if checksum != actual_checksum and length != len(msg):
            raise RuntimeError("Incorrect checksum and length")
        elif checksum != actual_checksum:
            raise RuntimeError("Incorrect checksum")
        elif length != len(msg):
            raise RuntimeError("Incorrect length")
        if msg[0] < 0 or msg[0] >= len(Iridium.ENCODED_REGISTRY):
            raise RuntimeError("Invalid command received")
        decoded = Iridium.ENCODED_REGISTRY[msg[0]]
        args = []

        for i in range(1, len(msg) - 1):
            num = msg[i] << 8 | msg[i+1]  # msb first
            exp = num >> 11  # extract exponent
            if exp & (1 << 4) == 1:  # convert twos comp
                exp &= 0x10  # truncate first bit
                exp -= (1 << 4)
            coef = num & 0x7ff  # extract coefficient
            if coef & (1 << 10) == 1:  # convert twos comp
                coef &= 0x3ff  # truncate first bit
                coef -= (1 << 10)
            if abs(coef) > 999:
                coef /= 1000
            elif abs(coef) > 99:  # Ideally, only this if condition should be used
                coef /= 100
            elif abs(coef) > 9:
                coef /= 10
            args.append(coef * 10 ** exp)
        return (decoded, args)

    def transmit(self, packet: TransmissionPacket, discardmtbuf = False) -> bool:
        """
        Loads message into MO buffer, then transmits
        If a message has been received, read it into SFR
        Clear buffers once done
        :param packet: (TransmissionPacket) packet to transmit
        :param discardmtbuf: (bool) if False: Store contents of MO buffer before reading in new messages.
            if True: Discard contents of MO buffer when reading in new messages.
        :return: (bool) transmission successful
        """
        pd.DataFrame([  # Log transmission
            {"timestamp": time.time()},
            {"radio": "Iridium"},
            {"data": f"{packet.command_string}:{packet.return_code}:{packet.msn}:{packet.timestamp[0]} \
                -{packet.timestamp[1]}-{packet.timestamp[2]}:{':'.join(packet.return_data)}:"},
            {"simulate": packet.simulate}
        ]).to_csv(self.sfr.transmission_log_path, mode="a", header=False)
        if packet.simulate:
            return True
        stat = self.SBD_STATUS()
        ls = self.process(stat, "SBDS").split(", ")
        if int(ls[2]) == 1:  # If message in MT, and discardbuf False, save MT to sfr
            if not discardmtbuf: 
                try:
                    self.sfr.vars.command_buffer.append(( *self.decode(self.process(self.SBD_RB(), "SBDRB").strip()) , int(ls[3]) )) #append message, args, msn number
                except:
                    self.sfr.vars.command_buffer.append(("GRB", [], int(ls[3]))) # Append garbled message indicator and msn
        if self.SBD_CLR(2).find("0\r\n\r\nOK") == -1:
            raise RuntimeError("Error clearing buffers")
        result = self.transmit_raw(self.encode(packet.command_string, packet.return_code, packet.msn, packet.timestamp, packet.return_data))
        if result[0] not in [0, 1, 2, 3, 4]:
            raise RuntimeError("Error transmitting buffer")
        if result[2] == 1:
            try:
                self.sfr.vars.command_buffer.append((*self.decode(self.process(self.SBD_RB(), "SBDRB").strip()) , int(result[3])))
            except:
                pass  # serial broken probably
        if self.SBD_CLR(2).find("0\r\n\r\nOK") == -1:
            raise RuntimeError("Error clearing buffers")
        return True

    def transmit_raw(self, message):
        """
        Transmits raw message using SBDWB, ignore MT buffer
        Use as a helper function for transmit
        :param message: (list) message, of encoded bytes.
        """
        rssi = self.RSSI()
        if rssi.find("CSQ:0") != -1 or rssi.find("OK") == -1:  # check signal strength first
            raise RuntimeError("No Signal")
        length = len(message)
        checksum = sum(message) & 0xffff
        print(checksum, length, message)
        message.append(checksum >> 8) # add checksum bytes
        message.append(checksum & 0xff)
        self.SBD_WB(length) #Specify bytes to write
        time.sleep(1) # 1 second to respond
        if self.read().find("READY") == -1:
            raise RuntimeError("Serial Timeout")
        self.serial.write(message)
        time.sleep(1) # 1 second to respond
        result = ""
        t = time.perf_counter()
        while result.find("OK") == -1:
            if time.perf_counter() - t> 5:
                raise RuntimeError("Serial Timeout")
            result += self.read()
        print(result)
        i = int(result.split("\r\n")[1]) #'\r\n0\r\n\r\nOK\r\n' format
        if i == 1:
            raise RuntimeError("Serial Timeout")
        if i == 2:
            raise RuntimeError("Incorrect Checksum")
        if i == 3:
            raise RuntimeError("Message too long")
        self.SBD_TIMEOUT(60)  # 60 second timeout for transmit
        result = [int(s) for s in self.process(self.SBD_INITIATE_EX(), "SBDIX").split(",")]
        return result

    def next_msg(self):
        """
        Stores next received messages in sfr
        """
        stat = self.SBD_STATUS()
        ls = self.process(stat, "SBDS").split(", ")
        if int(ls[2]) == 1:  # Save MT to sfr
            try:
                self.SBD_RB()
                raw = self.serial.read(50)
                t = time.perf_counter()
                while raw.decode("utf-8").find("OK") == -1:
                    if time.perf_counter() - t > 5:
                        raise RuntimeError("Serial Timeout")
                    raw += self.serial.read(50)
                print(raw)
                raw = raw[raw.find(b'SBDRB:') + 6:].split(b'\r\nOK')[0].strip()
                self.sfr.vars.command_buffer.append(TransmissionPacket( *self.decode(list(raw)) , int(ls[3])))
            except Exception as e:
                self.sfr.vars.command_buffer.append(TransmissionPacket("GRB", [repr(e)], int(ls[3]))) # Append garbled message indicator and msn, args set to exception string to debug
        self.SBD_TIMEOUT(60)
        time.sleep(1)
        result = [0, 0, 0, 0, 0, 1]
        lastqueued = []
        while result[5] >= 0:
            result = [int(s) for s in self.process(self.SBD_INITIATE_EX(), "SBDIX").split(",")]
            lastqueued.append(result[5])
            if sum(lastqueued[-3:]) / 3 == lastqueued[-1]:
                break # If GSS queue is not changing, don't bother to keep trying, just break
            if result[2] == 1:
                try:
                    self.SBD_RB()
                    raw = self.serial.read(50)
                    t = time.perf_counter()
                    while raw.find(b'OK') == -1:
                        if time.perf_counter() - t > 5:
                            raise RuntimeError("Serial Timeout")
                        raw += self.serial.read(50)
                    print(raw)
                    raw = raw[raw.find(b'SBDRB\r\n') + 7:].split(b'\r\nOK')[0]
                    self.sfr.vars.command_buffer.append(TransmissionPacket( *self.decode(list(raw)) , int(result[3]) ))
                except Exception as e:
                    self.sfr.vars.command_buffer.append(TransmissionPacket("GRB", [repr(e)], int(ls[3]))) # Append garbled message indicator and msn
            elif result[2] == 0:
                break
            elif result[2] == 2:
                break
            time.sleep(2.5)
        if self.SBD_CLR(2).find("0\r\n\r\nOK") == -1:
            raise RuntimeError("Error clearing buffers")

    def processed_time(self):
        """
        Requests, reads, processes, and returns current system time retrieved from network
        :return: (datetime) current time (use str() to parse to string if needed)
        """
        raw = self.NETWORK_TIME()
        if raw.find("OK") != -1:
            return None
        if raw.find("no network service") != -1:
            return None
        processed = int(raw.split("MSSTM:")[1].split("\n")[0].strip(), 16) * 90 / 1000
        return datetime.datetime.fromtimestamp(processed + Iridium.EPOCH)

    def processed_geolocation(self):
        """
        Requests, reads, processes, and returns current geolocation
        :return: (tuple) lat, long, altitude (0,0,0 if unable to retrieve)
        """
        raw = self.process(self.GEO_C(), "MSGEO").split(",") # raw x, y, z, timestamp
        try:
            if self.processed_time() - (int(raw[3], 16) * 90 / 1000 + Iridium.EPOCH) > 60: # Checks if time passed since last geolocation update has been more than 60 seconds
                result = [int(s) for s in self.process(self.SBD_INITIATE_EX(), "SBDIX").split(",")] # Use SBDIX to update geolocation
                if result[0] not in [0, 1, 3, 4]:
                    return (0, 0, 0) # Return 0, 0, 0 if SBDIX fails
                raw = self.process(self.GEO_C(), "MSGEO").split(",") # try again
        except TypeError:
            return (0, 0, 0) # Return 0, 0, 0 if network time cannot be retrieved
        lon = math.atan2(float(raw[1]), float(raw[0]))
        lat = math.atan2(float(raw[2]), ((float(raw[1])**2 + float(raw[0])**2)**0.5))
        alt = (float(raw[0])**2 + float(raw[1])**2 + float(raw[2])**2)**0.5
        return (lat, lon, alt)

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
                print(result)
                return result
        print(result)
        raise RuntimeError("Incomplete response")

    def write(self, command: str) -> bool:
        """
        Write a command to the serial port.
        :param command: (str) Command to write
        :return: (bool) if the serial write worked
        """
        command = command + "\r\n"
        print(command)
        try:
            self.serial.write(command.encode("utf-8"))
        except:
            return False
        return True

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
        print(output)
        return output.decode("utf-8")
