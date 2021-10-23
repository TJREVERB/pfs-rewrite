from mode import MODE
import gc

class ChargingMode(MODE):
    def __init__(self, eps, aprs, sfr, iridium):
        super().__init__()
        # constants
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode

        # Module Objects
        self.eps = eps
        self.aprs = aprs
        self.sfr = sfr
        self.iridium = iridium

        # init action sequence
        self.eps.commands["Pin Off"]("APRS")  # Powers off APRS
        self.eps.commands["Pin Off"]("SPI-UART")
        self.eps.commands["Pin Off"]("USB-UART")

    def check_conditions(self) -> bool:
        if self.eps.telemetry["VBCROUT"] <= self.UPPER_THRESHOLD:  # if voltage is less than upper limit
            return True
        else:
            return False

    def execute_cycle(self) -> None:
        # Iridium power controls
        if self.eps.sun_detected(): #do we really need to run this every single loop
            self.eps.commands["Pin On"]("Iridium")  # Switches on Iridium if in sunlight
            self.eps.commands["Pin On"]("UART-RS232")
            self.iridium.listen()  # Read and store received message
            # does not implement command interpreter because main control loop does that
        else:
            self.eps.commands["Pin Off"]("Iridium")  # Switches off Iridium if in eclipse
            self.eps.commands["Pin Off"]("UART-RS232")
        self.sfr.dump()  # Log changes

    def switch_modes(self) -> str:  # figure out whether to return string or int
        pass

    def terminate_mode(self) -> bool:
        gc.collect()
        return True


