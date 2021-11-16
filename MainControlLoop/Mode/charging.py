from MainControlLoop.Mode.mode import Mode


class Charging(Mode):
    def __init__(self, sfr):
        super(Charging, self).__init__(sfr)

    def __str__(self):
        return "Charging"

    def start(self) -> None:
        super(Charging, self).start()
        self.instruct["Pin On"](self.sfr.defaults["PRIMARY_RADIO"])  # turn on primary radio

    def check_conditions(self) -> bool:
        if self.sfr.eps.telemetry["VBCROUT"]() <= self.UPPER_THRESHOLD:  # if voltage is less than upper limit
            return True
        else:
            return False

    def execute_cycle(self) -> None:
        super(Charging, self).execute_cycle()
        self.sfr.devices[self.sfr.defaults["PRIMARY_RADIO"]].listen()  # Read and store execute received message
        self.sfr.dump()  # Log changes

    def switch_modes(self) -> None:
        pass

    def terminate_mode(self):
        super(Charging, self).terminate_mode()
        self.instruct["Pin Off"](self.sfr.defaults["PRIMARY_RADIO"])


