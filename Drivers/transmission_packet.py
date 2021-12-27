from lib.exceptions import wrap_errors, LogicalError
import datetime


class TransmissionPacket:
    def __init__(self):
        self.timestamp = datetime.datetime.utcnow()

    def __str__(self):
        return ""

    def get_packet_age(self) -> float:
        return datetime.datetime.utcnow().timestamp() - self.timestamp.timestamp()

    def split_packet(self, max_data_size):
        return []


class ResponsePacket(TransmissionPacket):
    @wrap_errors(LogicalError)
    def __init__(self, command_string: str, args: list, msn: int, simulate=False, outreach=False):
        super().__init__()
        self.command_string = command_string
        self.args = args
        self.msn = msn
        self.simulate = simulate
        self.outreach = outreach
        self.return_code = ""
        self.return_data = []

    @wrap_errors(LogicalError)
    def __str__(self):
        if self.return_code == "ERR":
            return f"{self.command_string}:{self.return_code}:{self.msn}:{self.timestamp.day}-\
                {self.timestamp.hour}-{self.timestamp.minute}:{self.return_data[0]}:"
        return f"{self.command_string}:{self.return_code}:{self.msn}:{self.timestamp.day}-\
            {self.timestamp.hour}-{self.timestamp.minute}:{':'.join([f'{s:.5}' for s in self.return_data])}"


class UnsolicitedPacket(TransmissionPacket):
    def __init__(self, message):
        super().__init__()
        self.raw_data = message

    def __str__(self):
        return f"{self.timestamp.day}-{self.timestamp.hour}-{self.timestamp.minute}:{self.raw_data}"  # timestamp info followed by the raw message


class RawPacket:
    def __init__(self, raw_string):
        super().__init__()
        self.message = raw_string

    def __str__(self):
        return self.message
