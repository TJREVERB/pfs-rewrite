#Error means non-critical error (i.e. wrong input for commands)
#Exception means critical error (i.e. antenna not working, failures, etc)

class InvalidCommandInputError(Exception):
    pass

class RedundantCommandInputError(Exception):
    pass