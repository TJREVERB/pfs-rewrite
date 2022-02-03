import time
from lib.registry import StateFieldRegistry
from lib.exceptions import wrap_errors, LogicalError
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.recovery import Recovery
from MainControlLoop.Mode.startup import Startup


class MainControlLoop:
    @wrap_errors(LogicalError)
    def __init__(self, sfr: StateFieldRegistry):
        self.sfr = sfr

    @wrap_errors(LogicalError)
    def start(self):
        print("MCL Start")
        self.sfr.vars.LAST_STARTUP = time.time()
        self.sfr.power_on("IMU")
        for device in self.sfr.vars.LOCKED_ON_DEVICES:  # power on all devices that are locked on
            self.sfr.power_on(device)
        # Set mode to Recovery if (antenna deployed) or (aprs or ad are locked off), Startup otherwise
        # self.sfr.MODE = Recovery(self.sfr) if self.sfr.vars.ANTENNA_DEPLOYED or \
        #     ("APRS" in self.sfr.vars.LOCKED_OFF_DEVICES or "Antenna Deployer" in
        #     self.sfr.vars.LOCKED_OFF_DEVICES) else Startup(self.sfr)
        self.sfr.MODE = Science(self.sfr)  # TODO: REMOVE THIS DEBUG LINE
        self.sfr.MODE.start()

    @wrap_errors(LogicalError)
    def iterate(self):  # Repeat main control loop forever
        self.sfr.MODE.execute_cycle()  # Execute single cycle of mode
        if not self.sfr.vars.MODE_LOCK:
            if not isinstance(self.sfr.MODE, type(new_mode := self.sfr.MODE.suggested_mode())):
                self.sfr.MODE.terminate_mode()
                self.sfr.MODE = new_mode
                self.sfr.MODE.start()

        self.sfr.command_executor.execute_buffers()  # Execute commands
        self.sfr.logger.log()  # Logs data
