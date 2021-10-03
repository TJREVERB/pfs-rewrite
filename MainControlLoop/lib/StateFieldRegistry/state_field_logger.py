from MainControlLoop.lib.StateFieldRegistry import registry, state_fields
import time


class StateFieldLogger:
    """
    Class for StateFieldLogger
    StateFieldLogger stores the current state field into a file
    If this is the first time the program has been ran (i.e. system crashed and reboot), it will load the last values from the state_field_log
    """

    LOG_PATH = "./MainControlLoop/lib/StateFieldRegistry/data/state_field_log.txt"

    # after how many iterations should the state field logger save the state field
    DUMP_ITERATION = 200

    def __init__(self, state_field_registry: registry.StateFieldRegistry):
        self.state_field_registry = state_field_registry
        self.first_time = True
        self.iteration = 0

    def dump_state_field(self):
        f = open(self.LOG_PATH, "w")
        for key, val in self.state_field_registry.registry.items():
            state_field_str = str(key)[11:]  # removes the 'Statefield.'

            # saves the statefield in the log
            if(val == False):
                val = ""  # if val is the boolean false, it needs to be an empty string in the state field log, or else it will be converted to True. Only empty strings are converted to False
            f.write("{0}:{1}\n".format(state_field_str, val))
        f.close()

    def control(self):
        self.iteration += 1  # increments the iteration
        if(self.first_time):  # if it's the first time, load the state field from the log
            self.first_time = False
            f = open(self.LOG_PATH, "r")
            state_field_log_dict = {}
            for line in f.readlines():
                line = line.strip().split(':')
                key = line[0]
                val = line[1]

                # convert the string into Statefield.(whatever statefield)
                cur_state_field = state_fields.STATE_FIELD_DICT[key]
                self.state_field_registry.update(
                    cur_state_field, state_fields.STATE_FIELD_TYPE_DICT[cur_state_field](val))  # update registry with the log's value

            self.state_field_registry.update(
                state_fields.StateField.START_TIME, time.time())  # specifically set the time; it is better if the antenna deploys late than early

        if(self.iteration >= self.DUMP_ITERATION):
            self.iteration = 0
            self.dump_state_field()
