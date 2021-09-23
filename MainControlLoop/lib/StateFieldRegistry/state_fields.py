from enum import Enum


class StateField(Enum):
    """
    List of all statefields
    """
    RAND_NUMBER = "RAND_NUMBER"
    ABOVE_50 = "ABOVE_50"
    RECEIVED_COMMAND = "RECEIVED_COMMAND"
