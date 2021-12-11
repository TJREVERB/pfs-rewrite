from MainControlLoop.lib.exceptions import decorate_all_callables, wrap_errors, LogicalError


class TransmissionPacket:
    @wrap_errors(LogicalError)
    def __init__(self, command_string: str, args: list, msn: int, simulate=False):
        self.command_string = command_string
        self.args = args
        self.msn = msn
        self.simulate = simulate
        self.timestamp = ()
        self.return_code = ""
        self.return_data = []
        decorate_all_callables(self, LogicalError)

    def __str__(self):
        return f"{self.command_string}:{self.return_code}:{self.msn}:{self.timestamp[0]}- \
            {self.timestamp[1]}-{self.timestamp[2]}:{':'.join(self.return_data)}:"
