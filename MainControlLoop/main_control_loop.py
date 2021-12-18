import time
from lib.registry import StateFieldRegistry
from lib.exceptions import wrap_errors, LogicalError


class MainControlLoop:
    @wrap_errors(LogicalError)
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.sfr = StateFieldRegistry()
        self.current_time = time.time()

    @wrap_errors(LogicalError)
    def start(self):
        print("MCL Start")
        self.sfr.MODE.start()

    @wrap_errors(LogicalError)
    def iterate(self):  # Repeat main control loop forever
        self.sfr.MODE.execute_cycle()  # Execute single cycle of mode
        if not self.sfr.vars.MODE_LOCK:
            if not isinstance(self.sfr.MODE, type(new_mode := self.sfr.MODE.suggested_mode())):
                self.sfr.MODE.terminate_mode()
                self.sfr.MODE = new_mode
                self.sfr.MODE.start()

        print("Cycle")
        self.sfr.command_executor.execute()  # Execute commands
        self.sfr.logger.log()  # Logs data
