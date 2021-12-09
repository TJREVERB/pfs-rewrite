

class RCE:
    def __init__(self, sfr) -> None:
        self.sfr = sfr

    def start(self):
        """
        FIX THIS METHOD
        """
        msg = self.sfr.devices["Iridium"].next_msg()
        exec(msg)
