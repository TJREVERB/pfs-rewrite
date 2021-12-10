class APRSError(Exception):
    def __init__(self, stack):
        self.stack = stack


class IridiumError(Exception):
    def __init__(self, stack):
        self.stack = stack
