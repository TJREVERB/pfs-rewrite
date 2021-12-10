#Error means non-critical error (i.e. wrong input for commands)
#Exception means critical error (i.e. antenna not working, failures, etc)

class CommandExecutorRuntimeException(Exception):
    def __init__(self, message: str):
        self.message = message


class RedundantCommandInputError(Exception):
    def __init__(self, message: str):
        self.message = message
