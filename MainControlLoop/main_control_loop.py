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

    # def run(self):  # Repeat main control loop forever
    #     print("Execution Start")
    #     current_time = time.time()
    #     while True:  # Iterate forever
    #         self.sfr.mode_obj = self.sfr.MODE(self.sfr)
    #         self.sfr.mode_obj.start()
    #         # Iterate while we're supposed to be in this mode
    #         while self.sfr.mode_obj.check_conditions() and isinstance(self.sfr.mode_obj, self.sfr.MODE):
    #             print("Cycle")
    #             self.sfr.mode_obj.execute_cycle()  # Execute single cycle of mode
    #             if current_time + 1 <= time.time():  # if waited 1 second or more, update conditions dict in mode
    #                 self.sfr.mode_obj.update_conditions()
    #                 current_time = time.time()
    #         self.sfr.mode_obj.terminate_mode()  # terminates current old mode

    def run(self):  # Repeat main control loop forever
        print("MCL Start")
        current_time = time.time()
        while True:  # Iterate forever
            self.sfr.mode_obj = self.sfr.MODE(self.sfr)
            self.sfr.mode_obj.start()
            # Iterate while we're supposed to be in this mode
            while isinstance(self.sfr.mode_obj, self.sfr.MODE):

                if current_time + 1 <= time.time():  # if waited 1 second or more, update conditions dict in mode
                    self.sfr.mode_obj.update_conditions()
                    current_time = time.time()

                if self.sfr.mode_obj.check_conditions() and self.sfr.MODE_LOCK == False:
                    self.sfr.MODE = self.sfr.mode_obj.switch_mode()  # change the mode to be whatever our current mode wants to switch to
                    break
                print("Cycle")
                self.sfr.mode_obj.execute_cycle()  # Execute single cycle of mode

            self.sfr.mode_obj.terminate_mode()  # terminates current old mode
