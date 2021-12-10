class RCE():
    def __init__(self, sfr) -> None:
        self.sfr = sfr

    def execute(self):
        """
        FIX THIS METHOD
        """
        while True:
            """
            Continiously listen for messages from main radio
            if there is message, attempt to exec method
            Should only switch back to mcl from confirmation from ground
            Should we put something to attempt to switch back to mcl if too much time passed?
            """
            pass
