from lib.exceptions import wrap_errors, LogicalError
import datetime


class TransmissionPacket:
    @wrap_errors(LogicalError)
    def __init__(self, response, numerical):
        self.descriptor = ""
        self.args = []
        self.msn = 0
        self.simulate = False
        self.outreach = False
        self.response = response
        self.numerical = numerical
        self.return_data = []
        self.timestamp = None
        
    def __str__(self):
        return "" # Overridden by subclasses

    @wrap_errors(LogicalError)
    def set_time(self):
        self.timestamp = datetime.datetime.utcnow()

    @wrap_errors(LogicalError)
    def get_packet_age(self) -> float:
        return (datetime.datetime.utcnow() - self.timestamp).total_seconds()


class FullPacket(TransmissionPacket): # Use this for anything that responds to a command sent from ground. If an error message is to be returned, set numerical to False
    @wrap_errors(LogicalError)
    def __init__(self, descriptor: str, args: list, msn: int, simulate=False, outreach=False):
        super().__init__(True, True)
        self.descriptor = descriptor
        self.args = args
        self.msn = msn
        self.simulate = simulate
        self.outreach = outreach

    @wrap_errors(LogicalError)
    def __str__(self):
        if self.response and not self.numerical: # String in response to a received command, will still contain descriptor for clarity's sake
            return f"{(self.response << 1) | self.numerical}:{self.timestamp.day}-\
                {self.timestamp.hour}-{self.timestamp.minute}:{self.descriptor}:{self.msn}:{self.return_data[0]}:"
        return f"{(self.response << 1) | self.numerical}:{self.timestamp.day}-\
            {self.timestamp.hour}-{self.timestamp.minute}:{self.descriptor}:{self.msn}:{':'.join([f'{s:.5}' for s in self.return_data])}:"


class UnsolicitedData(TransmissionPacket): # Use this for unsolicited data returns, such as with Science mode and POL beaconing
    @wrap_errors(LogicalError)
    def __init__(self, descriptor: str, return_data = [], simulate = False, outreach = False): # Return data is optional
        super().__init__(False, True)
        self.descriptor = descriptor
        self.return_data = return_data
        self.simulate = simulate
        self.outreach = outreach
        self.set_time() # Unsolicited will always be instantiated upon command execution, unlike with FullPackets

    @wrap_errors(LogicalError)
    def __str__(self):
        return f"{(self.response << 1) | self.numerical}:{self.timestamp.day}-{self.timestamp.hour}-{self.timestamp.minute}:{self.descriptor}\
            :{':'.join([f'{s:.5}' for s in self.return_data])}:"  # Basically the same as FullPacket but without MSN

class UnsolicitedString(TransmissionPacket): # Use this for unsolicited string messages like error and mode switch notifications, or GAMER MODE UPDATES
    @wrap_errors(LogicalError)
    def __init__(self, return_data = [], simulate = False, outreach = False):
        super().__init__(False, False)
        self.return_data = return_data
        self.simulate = simulate
        self.outreach = outreach
        self.set_time() # Unsolicited will always be instantiated upon command execution, unlike with FullPackets

    @wrap_errors(LogicalError)
    def __str__(self):
        return f"{(self.response << 1) | self.numerical}:{self.timestamp.day}-{self.timestamp.hour}-{self.timestamp.minute}:{self.return_data[0]}:"  
        # No MSN or descriptor
