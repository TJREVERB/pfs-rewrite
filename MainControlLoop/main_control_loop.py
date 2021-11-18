import time
from MainControlLoop.lib.registry import StateFieldRegistry


class MainControlLoop:
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.sfr = StateFieldRegistry()
        # If orbital data is default, set based on current position
        if self.sfr.LAST_DAYLIGHT_ENTRY is None:
            if self.sfr.eps.sun_detected():  # If we're in sunlight
                self.sfr.LAST_DAYLIGHT_ENTRY = time.time()  # Pretend we just entered sunlight
                self.sfr.LAST_ECLIPSE_ENTRY = time.time() - 45 * 60
            else:  # If we're in eclipse
                self.sfr.LAST_DAYLIGHT_ENTRY = time.time() - 45 * 60  # Pretend we just entered eclipse
                self.sfr.LAST_ECLIPSE_ENTRY = time.time()

    def run(self):  # Repeat main control loop forever
        current_time = time.time()
        while True:  # Iterate forever
            mode = self.sfr.MODE(self.sfr)
            mode.start()
            while mode.check_conditions():  # Iterate while we're supposed to be in this mode
                if current_time + 1 <= time.time():  # if waited 1 second or more, update conditions dict in mode
                    mode.update_conditions()
                    current_time = time.time()
                mode.execute_cycle()  # Execute single cycle of mode
                if self.sfr.MODE is not type(mode):  # if mode was changed via manual command
                    break
            self.sfr.mode.terminate_mode()  # terminates current old mode
