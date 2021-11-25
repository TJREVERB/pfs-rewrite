class TransmissionPacket:
    def __init__(self, command_string: str, args: list, msn: int):
        self.command_string = command_string
        self.args = args
        self.msn = msn
        self.error = False
        self.return_message = ""

