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
        self.sfr.turn_on_component("IMU")
        self.sfr.imu.start()
        self.sfr.mode_obj = self.sfr.vars.MODE(self.sfr)
        self.sfr.mode_obj.start()

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
            print("Switching to " + self.sfr.mode_obj.switch_mode().__name__)
            # change the mode to be whatever our current mode wants to switch to
            self.sfr.vars.MODE = self.sfr.mode_obj.switch_mode()

        print("Cycle")
        print(self.sfr.predicted_generation(5))
        self.sfr.mode_obj.execute_cycle()  # Execute single cycle of mode
        self.sfr.command_executor.execute()  # Execute commands
        self.sfr.logger.log()  # Logs data
