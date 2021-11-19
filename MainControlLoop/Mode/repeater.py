from MainControlLoop.Mode.mode import Mode


class Repeater(Mode):  # TODO: IMPLEMENT
    def __init__(self, sfr):
        super().__init__(sfr)
        self.conditions = {
            "Low Battery": False
        }

    def __str__(self):
        return "Repeater"

    def start(self) -> None:
        super(Repeater, self).start()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD
        self.instruct["Pin On"]("Iridium")
        self.instruct["Pin On"]("APRS")
        self.instruct["All Off"](exceptions=["Iridium", "APRS"])
        # TODO: TURN ON DIGIPEATING

    def check_conditions(self) -> bool:
        super(Repeater, self).check_conditions()
        if not self.conditions["Low Battery"]:  # if not low battery
            return True  # keep in current mode
        else:
            self.switch_mode("Charging")
            return False  # switch modes

    def update_conditions(self):
        super(Repeater, self).update_conditions()
        self.conditions["Low Battery"] = self.sfr.eps.telemetry["VBCROUT"]() < self.LOWER_THRESHOLD
        
    def execute_cycle(self) -> None:
        super(Repeater, self).execute_cycle()
        self.sfr.devices[self.sfr.PRIMARY_RADIO].listen()
        self.sfr.dump()  # Log changes

    def terminate_mode(self) -> None:
        # TODO: write to APRS to turn off digipeating
        super(Repeater, self).terminate_mode()
        pass
