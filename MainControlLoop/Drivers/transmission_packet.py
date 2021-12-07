class TransmissionPacket:
    def __init__(self, command_string: str, args: list, msn: int):
        self.command_string = command_string
        self.args = args
        self.msn = msn
        self.timestamp = ()
        self.return_code = ""
        self.return_data = []

    def __str__(self):
        return f"{self.command_string}, ARGS: {self.args}, MSN: {self.msn}, EXECUTED AT {self.timestamp}, RETURN {self.return_code}, {self.return_data}"
