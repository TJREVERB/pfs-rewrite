from MainControlLoop.Mode.mode import Mode
import gc


class Repeater(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr, conditions={

        })
        self.voltage = None

    def start(self) -> None:
        # turn off all devices
        Mode.turn_devices_off()

        self.eps.commands["Pin On"]("Iridium")  # Switches on Iridium
        self.eps.commands["Pin On"]("UART-RS232")
        self.eps.commands["Pin On"]("APRS")  # Switches on APRS
        self.eps.commands["Pin On"]("USB-UART")
        self.eps.commands["Pin On"]("SPI-UART")

    def check_conditions(self) -> bool:
        current_voltage = self.eps.telemetry["VBCROUT"]()
        if current_voltage > self.LOWER_THRESHOLD:  # if voltage is less than upper limit
            return True
        else:
            self.voltage = current_voltage
            return False

    def execute_cycle(self) -> None:
        self.iridium.listen()  # Read and store execute received message
        self.sfr.dump()  # Log changes

    def switch_modes(self) -> None:
        pass

    def terminate_mode(self) -> None:
        # TODO: write to APRS to turn off digipeating
        gc.collect()
        Mode.turn_devices_off()


