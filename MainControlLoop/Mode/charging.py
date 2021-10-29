from MainControlLoop.Mode.mode import Mode
import gc


class Charging(Mode):
    def __init__(self, sfr):

        super().__init__(sfr, conditions={

        })
        self.voltage = None

    def start(self) -> None:
        # turn off all devices
        Mode.turn_devices_off()

        self.eps.commands["Pin On"]("Iridium")  # Switches on Iridium
        self.eps.commands["Pin On"]("UART-RS232")
        self.devices["Iridium"] = True

    def check_conditions(self) -> bool:
        current_voltage = self.eps.telemetry["VBCROUT"]()
        if current_voltage <= self.UPPER_THRESHOLD:  # if voltage is less than upper limit
            return True
        else:
            self.voltage = current_voltage
            return False

    def execute_cycle(self) -> None:
        self.iridium.listen()  # Read and store execute received message
        self.sfr.dump()  # Log changes

    def switch_modes(self) -> None:
        pass

    def terminate_mode(self) -> bool:
        gc.collect()  # calls garbage collector
        del self.voltage
        self.eps.commands["Pin Off"]("Iridium") # turn off Iridium
        self.eps.commands["Pin Off"]("UART-RS232")
        return True
