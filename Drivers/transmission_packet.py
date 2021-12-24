from lib.exceptions import wrap_errors, LogicalError
import datetime


class TransmissionPacket:
    @wrap_errors(LogicalError)
    def __init__(self, command_string: str, args: list, msn: int, simulate=False, outreach=False):
        self.command_string = command_string
        self.args = args
        self.msn = msn
        self.simulate = simulate
        self.outreach = outreach
        self.timestamp = ()
        self.return_code = ""
        self.return_data = []

    @wrap_errors(LogicalError)
    def __str__(self):
        if self.return_code == "ERR":
            return f"{self.command_string}:{self.return_code}:{self.msn}:{self.timestamp[0]}-\
                {self.timestamp[1]}-{self.timestamp[2]}:{self.return_data[0]}:"
        return f"{self.command_string}:{self.return_code}:{self.msn}:{self.timestamp[0]}-\
            {self.timestamp[1]}-{self.timestamp[2]}:{':'.join([f'{s:.5}' for s in self.return_data])}"

    def get_packet_age(self) -> float:
        current_datetime = datetime.datetime.utcnow()
        month = current_datetime.month
        year = current_datetime.year
        if self.timestamp[0] > current_datetime.day: # Step month
            if month > 1:
                month -= 1
            else: # prevent y2k
                month = 12
                year -= 1
        dif = current_datetime - datetime.datetime(year, month, self.timestamp[0], self.timestamp[1], self.timestamp[2], 0)
        return dif.total_seconds()
