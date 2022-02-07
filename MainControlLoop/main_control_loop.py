import time
from Drivers.transmission_packet import UnsolicitedData
from lib.registry import StateFieldRegistry
from lib.exceptions import wrap_errors, LogicalError
from MainControlLoop.Mode.science import Science
from MainControlLoop.Mode.recovery import Recovery
from MainControlLoop.Mode.startup import Startup
from MainControlLoop.Mode.charging import Charging
from MainControlLoop.Mode.outreach.outreach import Outreach


class MainControlLoop:
    @wrap_errors(LogicalError)
    def __init__(self, sfr: StateFieldRegistry):
        self.sfr = sfr

    @wrap_errors(LogicalError)
    def start(self):
        """
        Logs startup time in sfr and powers on all locked on devices and IMU.
        Instantiates correct startup mode and starts it.
        """
        print("MCL Start")
        self.sfr.vars.LAST_STARTUP = time.time()
        self.sfr.power_on("IMU")
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
        """
        Iterates mode and checks if the mode should change if there isn't a mode lock and there isn't low power.
        Executes command buffers and logs data.
        """
        self.sfr.MODE.execute_cycle()  # Execute single cycle of mode
        if not self.sfr.vars.MODE_LOCK or self.sfr.check_lower_threshold(): # Change modes while there isn't a mode lock or there is low battery 
            if not isinstance(self.sfr.MODE, type(new_mode := self.sfr.MODE.suggested_mode())):
                print(f"Debug Print: switching modes, {self.sfr.MODE} to {new_mode}")
                # self.sfr.switch_mode(new_mode)  # TODO: UNCOMMENT AFTER TESTING
                if not self.sfr.switch_mode(new_mode):
                    print(f"Switch failed because of locked components! Staying in {self.sfr.MODE}")

        print(f"Commands {[p.descriptor for p in self.sfr.vars.command_buffer]}")
        self.sfr.command_executor.execute_buffers()  # Execute commands
        self.sfr.logger.log()  # Logs data
