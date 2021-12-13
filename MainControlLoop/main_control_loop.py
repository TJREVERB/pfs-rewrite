import time
from MainControlLoop.lib.registry import StateFieldRegistry
from MainControlLoop.lib.exceptions import wrap_errors, LogicalError


class MainControlLoop:
    @wrap_errors(LogicalError)
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.sfr = StateFieldRegistry()
        self.current_time = time.time()
        self.current_time = time.time()

    @wrap_errors(LogicalError)
    def start(self):
        print("MCL Start")
        self.current_time = time.time()
        self.sfr.mode_obj = self.sfr.vars.MODE(self.sfr)
        self.sfr.mode_obj.start()
<<<<<<< HEAD
        start_time = time.time()
        while True:  # Iterate forever
=======
>>>>>>> 2c6e61e0cc8b65b9ff7d9bc7f8f7440395eba2db

    @wrap_errors(LogicalError)
    def iterate(self):  # Repeat main control loop forever
        if not isinstance(self.sfr.mode_obj, self.sfr.vars.MODE):
            self.sfr.mode_obj.terminate_mode()  # terminates current old mode
            self.sfr.mode_obj = self.sfr.vars.MODE(self.sfr)
            self.sfr.mode_obj.start()

        # Update the conditions dictionary periodically for this mode:
        self.sfr.mode_obj.update_conditions()

        # If the conditions of this mode aren't met and we are allowed to switch:
        if not self.sfr.mode_obj.check_conditions() and not self.sfr.vars.MODE_LOCK:
            # change the mode to be whatever our current mode wants to switch to
            self.sfr.vars.MODE = self.sfr.mode_obj.switch_mode()

<<<<<<< HEAD
            print("Cycle")
            self.sfr.mode_obj.execute_cycle()  # Execute single cycle of mode
            self.sfr.command_executor.execute()  # Execute commands
            self.sfr.logger.log()  # Logs data
            print(f"Mode: {self.sfr.mode_obj}")
            print(f"Time: {current_time-start_time}\n")



=======
        print("Cycle")
        self.sfr.mode_obj.execute_cycle()  # Execute single cycle of mode
        self.sfr.command_executor.execute()  # Execute commands
        self.sfr.logger.log()  # Logs data
>>>>>>> 2c6e61e0cc8b65b9ff7d9bc7f8f7440395eba2db
