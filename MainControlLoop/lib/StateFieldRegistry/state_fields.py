from enum import Enum


class StateField(Enum):
    """
    List of all statefields
    """
    RAND_NUMBER = "RAND_NUMBER"
    ABOVE_50 = "ABOVE_50"
    RECEIVED_COMMAND = "RECEIVED_COMMAND"
    START_TIME = "START_TIME"
    ANTENNA_DEPLOYED = "ANTENNA_DEPLOYED"


STATE_FIELD_DICT = {
    "RAND_NUMBER": StateField.RAND_NUMBER,
    "ABOVE_50": StateField.ABOVE_50,
    "RECEIVED_COMMAND": StateField.RECEIVED_COMMAND,
    "START_TIME": StateField.START_TIME,
    "ANTENNA_DEPLOYED": StateField.ANTENNA_DEPLOYED
}

STATE_FIELD_TYPE_DICT = {
    StateField.RAND_NUMBER: int,
    StateField.ABOVE_50: bool,
    StateField.RECEIVED_COMMAND: str,
    StateField.START_TIME: float,
    StateField.ANTENNA_DEPLOYED: bool
}
