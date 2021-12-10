import time
from MainControlLoop.lib.registry import StateFieldRegistry
from MainControlLoop.lib.log import Logger
from exceptions import decorate_all_callables, wrap_errors, SystemError


class MainControlLoop:
    @wrap_errors(SystemError)
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.sfr = StateFieldRegistry()
        decorate_all_callables(SystemError)
    
    def start(self):
        print("MCL Start")
        self.current_time = time.time()
        self.sfr.mode_obj = self.sfr.vars.MODE(self.sfr)
        self.sfr.mode_obj.start()

    def loop(self):  # Repeat main control loop forever
        if not isinstance(self.sfr.mode_obj, self.sfr.vars.MODE):
            self.sfr.mode_obj.terminate_mode()  # terminates current old mode
            self.sfr.mode_obj = self.sfr.vars.MODE(self.sfr)
            self.sfr.mode_obj.start()

        # Update the conditions dictionary periodically for this mode:
        if self.current_time + 1 <= time.time():  # if waited 1 second or more, update conditions dict in mode
            self.sfr.mode_obj.update_conditions()
            self.current_time = time.time()

        # If the conditions of this mode aren't met and we are allowed to switch:
        if not self.sfr.mode_obj.check_conditions() and not self.sfr.vars.MODE_LOCK:
            # change the mode to be whatever our current mode wants to switch to
            self.sfr.vars.MODE = self.sfr.mode_obj.switch_mode()

        print("Cycle")
        self.sfr.mode_obj.execute_cycle()  # Execute single cycle of mode
        self.sfr.command_executor.execute()  # Execute commands
        self.sfr.logger.log()  # Logs data
