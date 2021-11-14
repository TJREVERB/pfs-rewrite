import time
from serial import Serial
from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
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

    def __init__(self, state_field_registry: StateFieldRegistry):
        self.sfr = state_field_registry
        self.serial = Serial(port=self.PORT, baudrate=self.BAUDRATE, timeout=1)  # connect serial
        while not self.serial.is_open:
            time.sleep(0.5)
        self.commands = {
            "Basic Test": self.serialTest(),  # Tests connection to Iridium
            "Buffer Test": self.functional(), # Tests ability to use buffers

            "GeolocationC": lambda: self.request("AT-MSGEO"),  # Current geolocation, xyz cartesian
            # return format: <x>, <y>, <z>, <time_stamp>
            "GeolocationS": lambda: self.request("AT-MSGEOS"), # Current geolocation, spherical coordinates
            # return format: <latitude>, <longitude>, <altitude>, <latitude_error>, <longitude_error>, <altitude_error>, <time_stamp>
            # time_stamp uses same 32 bit format as MSSTM

            # Performs a manual registration, consisting of attach and location update. No MO/MT messages transferred
            # Optional param location
            "Registration": lambda: self.request("AT+SBDREG"), 
            "Registration Location": lambda location: self.request("AT+SBDREG=" + location),

            "Phone Model": lambda: self.request("AT+CGMM"),
            "Phone Revision": lambda: self.request("AT+CGMR"),
            "IMEI": lambda: self.request("AT+CSGN"),

            "Network Time": lambda: self.request("AT-MSSTM"), # System time, GMT, retrieved from satellite network (used as a network check)
            # returns a 32 bit integer formatted in hex, with no leading zeros. Counts number of 90 millisecond intervals that have elapsed since the epoch
            # current epoch is May 11, 2014, at 14:23:55, and will change again around 2026

            "Shut Down": lambda: self.write("AT*F"),
            "RSSI": lambda: self.request("AT+CSQ", 10),  # Returns strength of satellite connection, may take up to ten seconds if iridium is in satellite handoff
            "Last Known Signal Quality": lambda: self.request("AT+CSQF"), # Returns last known signal strength, immediately

            # Enable or disable ring indications for SBD Ring Alerts. When ring indication is enabled, ISU asserts RI line and issues the unsolicited result code SBDRING when an SBD ring alert is received
            # Ring alerts can only be sent after the unit is registered
            "Get SBD Ring Alert": lambda: self.request("AT+SBDMTA"),
            "Set SBD Ring Alert": lambda b: self.request("AT+SBDMTA=" + b), #:param b: 1/0 enable/disable
            
            #doesn't seem relevant to us?
            "Battery Check": lambda: self.request("AT+CBC=?"), 
            "Call Status": lambda: self.request("AT+CLCC=?"), 

            # Resets settings without power cycle
            "Soft Reset": lambda: self.write("ATZn"),

            # Load message into mobile originated buffer. SBDWT uses text, SBDWB uses binary
            "Transmit Text": lambda message: self.request("AT+SBDWT=" + message),
            "Transmit Binary": lambda message: self.request("AT+SBDWB=" + message),
            # Read message from mobile terminated buffer. SBDRT uses text, SBDRB uses binary. Only one message is contained in buffer at a time
            "Receive Text": lambda: self.request("AT+SBDRT"),
            "Receive Binary": lambda: self.request("AT+SBDRT"),

            # Returns state of mobile originated and mobile terminated buffers
            # SBDS return format: <MO flag>, <MOMSN>, <MT flag>, <MTMSN>
            "SBD Status": lambda: self.request("AT+SBDS"), # beamcommunications 101-102
            # SBDSX return format: <MO flag>, <MOMSN>, <MT Flag>, <MTMSN>, <RA flag>, <msg waiting>
            "SBD Status Extended": lambda: self.request("AT+SBDSX"), # beamcommunications 103
            # MO flag: (1/0) whether message in mobile originated buffer
            # MOMSN: sequence number that will be used in the next mobile originated SBD session
            # MT flag: (1/0) whether message in mobile terminated buffer
            # MTMSN: sequence number in the next mobile terminated SBD session, -1 if nothing in the MT buffer
            # RA flag: (1/0) whether an SBD ring alert has been received and needs to be answered
            # msg waiting: how many SBD mobile terminated messages are queued at the gateway for collection by ISU
            
            # Reads or sets session timeout settings, after which time ISU will stop trying to transmit/receive to GSS
            "Get SBD Session Timeout": lambda: self.request("AT+SBDST"),
            "Set SBD Session Timeout": lambda time: self.request("AT+SBDST=" + time),

            # Transfers contents of mobile originated buffer to mobile terminated buffer, to test reading and writing to ISU without initiating SBD sessions with GSS/ESS
            # returns response of the form "SBDTC: Outbound SBD copied to Inbound SBD: size = <size>" followed by "OK", where size is message length in bytes
            "Buffer Transfer": lambda: self.request("AT+SBDTC"), # beamcommunications 104

            # Transmits contents of mobile originated buffer to GSS, transfer oldest message in GSS queuefrom GSS to ISU
            "Initiate SBD Session": lambda: self.request("AT+SBDI", 10), # beamcommunications 94-95
            # Like SBDI but it always attempts SBD registration, consisting of attach and location update. 
            # a should be "A" if in response to SBD ring alert, otherwise a = "". location is an optional param, format =[+|-]DDMM.MMM, [+|-]dddmm.mmm
            "Initiate Extended SBD Session": lambda a, location: self.request("AT+SBDIX" + a + location, 10), #beamcommunications 95-96

            # Clear one or both buffers.
            # param type: buffers to clear. 0 = mobile originated, 1 = mobile terminated, 2 = both
            "Clear buffers": lambda type: self.request("AT+SBDD=" + type),
        }
    
    def __del__(self):
        self.serial.close()

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
            return True
        except UnicodeDecodeError:
            return False

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
        return result

    def pollRI(self):
        """Polls RI pin to see if a ring alert message is available"""
        pass #TODO: IMPLEMENT
    
    def wave(self, battery_voltage, solar_generation, power_draw) -> bool:
        """
        Attempts to establish first contact with ground station
        Overwrites any message already in the MO buffer in doing so
        :param battery_voltage: battery voltage, will be truncated to 3 digits
        :param solar_generation: solar panel power generation, will be truncated to 3 digits
        :param power_draw: total power output of EPS, will be truncated to 3 digits
        :param failures: component failures
        :return: (bool) Whether write worked
        """
        msg = f"TJ;Hello from space! BVT:{battery_voltage},SOL:{solar_generation},PWR:{power_draw},FAI:{chr(59).join(self.sfr.FAILURES)}"# Component failures, sep by ;
        self.commands["Transmit Text"](msg)
        result = self.commands["Initiate SBD Session"]()
        #format needs verification:
        processed = result.split("\n")[0].split("+SBDI ")[1].strip()
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
        command = command + "\r\n" #may need to be replaced with \x0d
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
        for loop in range(50):
            try:
                next_byte = self.serial.read(size=1)
            except:
                break
            if next_byte == bytes():
                break
            output += next_byte
        return output.decode("utf-8")
