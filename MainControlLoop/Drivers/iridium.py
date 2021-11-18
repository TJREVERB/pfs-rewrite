import time, datetime
import math
from serial import Serial
from functools import partial

#https://www.beamcommunications.com/document/328-iridium-isu-at-command-reference-v5
#https://docs.rockblock.rock7.com/reference/sbdwt
#https://www.ydoc.biz/download/IRDM_IridiumSBDService.pdf

#MO/Mobile Originated Buffer: Contains messages to be sent from iridium device
#MT/Mobile Terminated Buffer: Contains messages received from the Iridium constellation
#GSS: Iridium SBD Gateway Subsystem: Transfers messages from ISU to Ground
#ISU: Iridium Subscriber Unit: basically our radio
#FA: Field Application: basically our flight-pi

#FA <-UART/RS232 Interface-> ISU - MO buffer -> Iridium Constellation <-> GSS <-> IP Socket/Email
#                                <- MT buffer -

class Iridium:
    PORT = '/dev/serial0'
    BAUDRATE = 19200

    EPOCH = datetime.datetime(2014, 5, 11, 14, 23, 55).timestamp() #Set epoch date to 5 May, 2014, at 14:23:55 GMT

    ENCODED_REGISTRY = [
        #Commands to satellite, also used in specifying return values to ground
        "NOP", #0, NO OP
        "BVT", #1, BATTERY VOLTAGE
        "CHG", #2, CHARGING MODE
        "SCI", #3, SCIENCE MODE
        "OUT", #4, OUTREACH MODE
        "RST", #5, BUS RESET
        "WVE", #6, PROOF OF LIFE
        "PWR", #7, TOTAL POWER
        "SSV", #8, SIGNAL VARIABILITY
        "SVF", #9, FULL SIGNAL VARIABILITY DATA
        "SOL", #10, SOLAR POWER
        "TBL", #11, TUMBLE

        #codes to be sent in response to commands or telemetry, for both ground and satellite
        "0OK", #12, MSG received and executed
        "EXC", #13, MSG received and read, but error executing
        "LEN", #14, MSG received, but length did not match
        "CHK", #15, MSG received, but checksum incorrect
        "LCK", #16, MSG received, but both length and checksum incorrect
        "TMO", #17, Timeout while waiting for response
    ]

    def __init__(self, state_field_registry):
        self.sfr = state_field_registry
        self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        while not self.serial.is_open:
            time.sleep(0.5)
        self.GEO_C = lambda: self.request("AT-MSGEO")  # Current geolocation, xyz cartesian
        # return format: <x>, <y>, <z>, <time_stamp>
        self.GEO_S = lambda: self.request("AT-MSGEOS") # Current geolocation, spherical coordinates
        # return format: <latitude>, <longitude>, <altitude>, <latitude_error>, <longitude_error>, <altitude_error>, <time_stamp>
        # time_stamp uses same 32 bit format as MSSTM

        # Performs a manual registration, consisting of attach and location update. No MO/MT messages transferred
        # Optional param location
        self.REGISTER = lambda location = "": self.request("AT+SBDREG") if len(location)==0 else self.request("AT+SBDREG=" + location)

        self.MODEL = lambda: self.request("AT+CGMM")
        self.PHONE_REV = lambda: self.request("AT+CGMR")
        self.IMEI = lambda: self.request("AT+CSGN")

        self.NETWORK_TIME = lambda: self.request("AT-MSSTM") # System time, GMT, retrieved from satellite network (used as a network check)
        # returns a 32 bit integer formatted in hex, with no leading zeros. Counts number of 90 millisecond intervals that have elapsed since the epoch
        # current epoch is May 11, 2014, at 14:23:55, and will change again around 2026

        self.SHUTDOWN = lambda: self.request("AT*F", 1)
        self.RSSI = lambda: self.request("AT+CSQ", 10)  # Returns strength of satellite connection, may take up to ten seconds if iridium is in satellite handoff
        self.LAST_RSSI = lambda: self.request("AT+CSQF") # Returns last known signal strength, immediately

        # Enable or disable ring indications for SBD Ring Alerts. When ring indication is enabled, ISU asserts RI line and issues the unsolicited result code SBDRING when an SBD ring alert is received
        # Ring alerts can only be sent after the unit is registered
        # :optional param b: set 1/0 enable/disable
        self.RING_ALERT = lambda b="": self.request("AT+SBDMTA") if len(str(b)) == 0 else self.request("AT+SBDMTA" + str(b))
        
        #doesn't seem relevant to us?
        self.BAT_CHECK = lambda: self.request("AT+CBC")

        # Resets settings without power cycle
        self.SOFT_RST = lambda: self.request("ATZn", 1)

        # Load message into mobile originated buffer. SBDWT uses text, SBDWB uses binary
        self.SBD_WT = lambda message: self.request("AT+SBDWT=" + message)
        self.SBD_WB = lambda message: self.request("AT+SBDWB=" + message)
        # Read message from mobile terminated buffer. SBDRT uses text, SBDRB uses binary. Only one message is contained in buffer at a time
        self.SBD_RT = lambda: self.request("AT+SBDRT")
        self.SBD_RB = lambda: self.request("AT+SBDRB")

        # Returns state of mobile originated and mobile terminated buffers
        # SBDS return format: <MO flag>, <MOMSN>, <MT flag>, <MTMSN>
        self.SBD_STATUS = lambda: self.request("AT+SBDS") # beamcommunications 101-102
        # SBDSX return format: <MO flag>, <MOMSN>, <MT Flag>, <MTMSN>, <RA flag>, <msg waiting>
        self.SBD_STATUS_EX = lambda: self.request("AT+SBDSX") # beamcommunications 103
        # MO flag: (1/0) whether message in mobile originated buffer
        # MOMSN: sequence number that will be used in the next mobile originated SBD session
        # MT flag: (1/0) whether message in mobile terminated buffer
        # MTMSN: sequence number in the next mobile terminated SBD session, -1 if nothing in the MT buffer
        # RA flag: (1/0) whether an SBD ring alert has been received and needs to be answered
        # msg waiting: how many SBD mobile terminated messages are queued at the gateway for collection by ISU
        
        # Reads or sets session timeout settings, after which time ISU will stop trying to transmit/receive to GSS, in seconds. 0 means infinite timeout
        self.SBD_TIMEOUT = lambda time = "": self.request("AT+SBDST") if len(str(time)) == 0 else self.request("AT+SBDST=" + str(time))

        # Transfers contents of mobile originated buffer to mobile terminated buffer, to test reading and writing to ISU without initiating SBD sessions with GSS/ESS
        # returns response of the form "SBDTC: Outbound SBD copied to Inbound SBD: size = <size>" followed by "OK", where size is message length in bytes
        self.SBD_TRANSFER_MOMT = lambda: self.request("AT+SBDTC") # beamcommunications 104

        # Transmits contents of mobile originated buffer to GSS, transfer oldest message in GSS queuefrom GSS to ISU
        self.SBD_INITIATE = lambda: self.request("AT+SBDI", 60) # beamcommunications 94-95
        # Like SBDI but it always attempts SBD registration, consisting of attach and location update. 
        # a should be "A" if in response to SBD ring alert, otherwise unspecified. location is an optional param, format =[+|-]DDMM.MMM, [+|-]dddmm.mmm
        self.SBD_INITIATE_EX = lambda a = "", location = "": self.request("AT+SBDIX" + a, 10) if len(location) == 0 else self.request("AT+SBDIX" + a + "=" + location) #beamcommunications 95-96
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
        self.SBD_CLR = lambda type: self.request("AT+SBDD" + str(type)),
    
    def __del__(self):
        self.SHUTDOWN()
        time.sleep(1)
        self.serial.close()

    def __str__(self):
        return "Iridium"

    def serialTest(self) -> bool:
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
            self.write("AT")
            time.sleep(1) #Give Iridium one second to respond
            if self.read().find("OK") != -1:
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
            self.write("AT+SBDWT=test")
            time.sleep(.5)
            if self.read().find("OK") == -1:
                raise RuntimeError("Error writing to MO")
            self.write("AT+SBDTC")
            time.sleep(.5)
            if self.read().find("Outbound SBD Copied to Inbound SBD: size = 4") == -1:
                raise RuntimeError("Error transferring buffers")
            self.write("AT+SBDRT")
            time.sleep(.5)
            if self.read().find("test") == -1:
                raise RuntimeError("Error reading message from MT")
            self.write("AT+SBDD2") #clear all buffers
            return True
        except UnicodeDecodeError:
            return False

    def process(self, data, cmd):
        """
        Clean up data string
        :param data: (str) to format
        :param cmd: (str) command, do not include AT prefix
        """
        return data.split(cmd + ":")[1].split("\r\nOK")[0].strip()

    def encode(self, message):
        """
        Encodes string for transmit using numbered codes
        :param message: (tuple) tup of strings and floats/ints to encode, in order
        :return: (bytes) encoded utf-8 string
        """
        encoded = ""
        for m in message:
            if str(m).isnumeric():
                #convert from float or int to twos comp half precision, bytes are MSB FIRST
                flt = 0
                exp = int(math.log10(abs(m)))
                if exp < 0:
                    exp = abs(exp) + 1
                    exp &= 0xf #make sure exp is 4 bits, cut off anything past the 4th
                    exp = (1 << 4) - exp #twos comp
                    flt |= exp << 11
                    flt |= 1 << 15
                else:
                    flt |= (exp & 0xf) << 11 #make sure exp is 4 bits, cut off anything past the 4th, shift left 11
                num = m/(10**exp)*100 #num will always have three digits, with trailing zeros if necessary to fill it in
                if m < 0:
                    num &= 0x3ff #make sure num is 10 bits long
                    num = (1 << 10) - num #twos comp
                    flt |= num
                    flt |= (1 << 10) #set sign bit
                else:
                    flt |= num & 0x3ff #make sure num is 10 bits long
                byte1 = flt >> 8
                byte2 = flt & 0xff
                encoded += "\x" + hex(byte1).split("x")[1].zfill(2) #MSB FIRST
                encoded += "\x" + hex(byte2).split("x")[1].zfill(2) #LSB LAST
            else:
                for i in range(0, len(m), 3):
                    num = Iridium.ENCODED_REGISTRY.find(m[i:i+3])
                    if num == -1:
                        raise RuntimeError("Incorrect string code")
                    else:
                        encoded += "\x" + hex(num).split("x")[1].zfill(2)
        return encoded.encode("utf-8")


    def decode(self, message):
        """
        Decodes received string from SBDRB and converts to string
        :param message: (str) received
        :return: (str) decoded character string
        """


    def request(self, command: str, timeout=0.5) -> str:
        """
        Requests information from Iridium and returns unprocessed response
        :param command: Command to send
        :param timeout: maximum time to wait for a response
        :return: (str) Response from Iridium
        """
        self.write(command)
        result = ""
        sttime = time.perf_counter()
        while result.find("OK") == -1 and time.perf_counter()-sttime < timeout:
            time.sleep(.1)
            result += self.read()
            if result.find("ERROR") != -1:
                return command[2:] + "ERROR" + "\n" # formatted so that process() can still decode properly
        return result

    def transmit(self, message, discardbuf = True):
        """
        Loads message into MO buffer, then transmits
        If a message has been received, read it into SFR
        Clear buffers once done
        :param message: (str) message to send
        :param discardbuf: (bool) if False: transmit contents, if any, of MO buffer before loading new message in; if True: overwrite MO buffer contents
        :return: (bool) transmission successful
        """ #We should consider using the sequence numbers
        #TODO: SWITCH THIS FROM SBDWT TO SBDWB
        stat = self.SBD_STATUS()
        ls = self.process(stat, "SBDS").split(", ")
        if int(ls[2]) == 1: #Save MT to sfr
            try:
                self.sfr.IRIDIUM_RECEIVED_COMMAND.append((self.process(self.SBD_RT(), "SBDRT"), self.NETWORK_TIME()))
            except:
                pass #whatever, not worth it
        if int(ls[0]) == 1:
            if not discardbuf: #If discardbuf false, transmit MO
                try:
                    self.SBD_INITIATE()
                except:
                    pass #whatever, not worth it
        rssi = self.RSSI()
        if rssi.find("CSQ:0") != -1 or rssi.find("OK") == -1: #check signal strength first
            return False
        self.SBD_TIMEOUT(60) # 60 second timeout for transmit
        self.SBD_WT(message)
        result = self.process(self.SBD_INITIATE(), "SBDI").split(", ")
        if result[0] == 0:
            raise RuntimeError("Error writing to buffer")
        elif result[0] == 2:
            raise RuntimeError("Error transmitting buffer")
        if result[2] == 1:
            try:
                self.sfr.IRIDIUM_RECEIVED_COMMAND.append((self.process(self.SBD_RT(), "SBDRT"), self.NETWORK_TIME()))
            except:
                pass #whatever, not worth it
        if self.SBD_CLR(2).find("0\r\n\r\nOK") == -1:
            raise RuntimeError("Error clearing buffers")
        return True

    def nextMsg(self):
        """
        Stores next received messages in sfr
        """
        #TODO: SWITCH FROM SBDRT TO SBDRB
        stat = self.SBD_STATUS()
        ls = self.process(stat, "SBDS").split(", ")
        if int(ls[2]) == 1: #Save MT to sfr
            try:
                self.sfr.IRIDIUM_RECEIVED_COMMAND.append((self.process(self.SBD_RT(), "SBDRT"), self.NETWORK_TIME))
            except:
                pass #broken serial prolly
        result = [int(s) for s in self.process(self.SBD_INITIATE(), "SBDI").split(", ")]
        lastqueued = [result[5]]
        while result[5] > 0:
            if result[2] == 1:
                try:
                    self.sfr.IRIDIUM_RECEIVED_COMMAND.append((self.process(self.SBD_RT(), "SBDRT"), self.NETWORK_TIME))
                except:
                    pass #broken serial prolly
            elif result[2] == 0:
                pass
            elif result[2] == 2:
                pass #TODO: HANDLE ERROR OR NO MESSAGE RECEIVED
            result = [int(s) for s in self.process(self.SBD_INITIATE(), "SBDI").split(", ")]
            lastqueued.append(result[5])
            if sum(lastqueued[-3:])/3 == lastqueued[-1]:
                pass #TODO: HANDLE GSS QUEUE NOT CHANGING

    def processedTime(self):
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
    
    def wave(self, battery_voltage, solar_generation, power_draw) -> bool:
        """
        Attempts to establish first contact with ground station
        Overwrites any message already in the MO buffer in doing so
        :param battery_voltage: battery voltage, will be truncated to 3 digits
        :param solar_generation: solar panel power generation, will be truncated to 3 digits
        :param power_draw: total power output of EPS, will be truncated to 3 digits
        :param failures: component failures
        :return: (bool) Transmission successful
        """
        msg = f"BVT:{battery_voltage:.2f},SOL:{solar_generation:.2f},PWR:{power_draw:.2f},FAI:{chr(59).join(self.sfr.FAILURES)}"# Component failures, sep by ;
        self.SBD_WT(msg)
        result = self.SBD_INITIATE()
        #format needs verification:
        processed = result.split("\n")[0].split("SBDI")[1].strip()
        try:
            ls = [int(s) for s in processed.split(", ")]
            if ls[0] == 0:
                raise RuntimeError("Error writing to buffer")
            if ls[0] == 2:
                raise RuntimeError("Unable to transmit")
        except:
            raise RuntimeError("Serial Port malfunction")
        return True 

    def write(self, command: str) -> bool:
        """
        Write a command to the serial port.
        :param command: (str) Command to write
        :return: (bool) if the serial write worked
        """
        command = command + "\r\n" 
        try:
            self.serial.write(command.encode("UTF-8"))
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
        return output.decode("utf-8")
