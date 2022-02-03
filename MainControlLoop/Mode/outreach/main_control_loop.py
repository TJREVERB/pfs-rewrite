import time
from lib.registry import StateFieldRegistry
from lib.exceptions import wrap_errors, LogicalError
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.recovery import Recovery
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.outreach.outreach import Outreach


class MainControlLoop:
    @wrap_errors(LogicalError)
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.sfr = StateFieldRegistry()

    @wrap_errors(LogicalError)
    def start(self):
        print("MCL Start")
        self.sfr.vars.LAST_STARTUP = time.time()
        self.sfr.power_on("IMU")  # TODO: is this necessary?
        for device in self.sfr.vars.LOCKED_ON_DEVICES:  # power on all devices that are locked on
            self.sfr.power_on(device)
        # Set mode to Recovery if (antenna deployed) or (aprs or ad are locked off), Startup otherwise
        # self.sfr.MODE = Recovery(self.sfr) if self.sfr.vars.ANTENNA_DEPLOYED or \
        #     ("APRS" in self.sfr.vars.LOCKED_OFF_DEVICES or "Antenna Deployer" in
        #     self.sfr.vars.LOCKED_OFF_DEVICES) else Startup(self.sfr)
        self.sfr.MODE = Outreach(self.sfr)  # TODO: REMOVE THIS DEBUG LINE
        self.sfr.MODE.start()

    @wrap_errors(LogicalError)
    def iterate(self):  # Repeat main control loop forever
        # If we haven't received a message for a very long time
        if time.time() - self.sfr.vars.LAST_IRIDIUM_RECEIVED > self.sfr.UNSUCCESSFUL_RECEIVE_TIME_CUTOFF:
            self.sfr.set_primary_radio("APRS")

        self.sfr.MODE.execute_cycle()  # Execute single cycle of mode
        if not self.sfr.vars.MODE_LOCK:
            if not isinstance(self.sfr.MODE, type(new_mode := self.sfr.MODE.suggested_mode())):
                self.sfr.MODE.terminate_mode()
                self.sfr.MODE = new_mode
                self.sfr.MODE.start()

        print("Cycle")
        self.sfr.command_executor.execute_buffers()  # Execute commands
        self.sfr.logger.log()  # Logs data
