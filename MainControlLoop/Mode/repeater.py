from MainControlLoop.Mode.mode import Mode
import gc


class Repeater(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)


    def __str__(self):
        return "Repeater"

    def start(self) -> None:
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")

    def check_conditions(self) -> bool:
        current_voltage = self.sfr.eps.telemetry["VBCROUT"]()
        if current_voltage > self.LOWER_THRESHOLD:  # if voltage is less than upper limit
            return True
        else:
            return False

    def execute_cycle(self) -> None:

        self.sfr.devices[self.sfr.defaults["PRIMARY_RADIO"]].listen()
        self.sfr.dump()  # Log changes

    def switch_modes(self) -> None:
        pass

    def terminate_mode(self) -> None:
        # TODO: write to APRS to turn off digipeating
        self.instruct["Pin Off"]("Iridium")
        self.instruct["Pin Off"]("APRS")


