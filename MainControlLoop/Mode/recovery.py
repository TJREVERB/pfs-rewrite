from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError


class Recovery(Mode):

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        Sets up constants
        """
        super().__init__(sfr)
        self.last_contact_attempt = 0

    @wrap_errors(LogicalError)
    def __str__(self):
        return "Recovery"

    @wrap_errors(LogicalError)  # TODO: IMPLEMENT
    def start(self) -> None:
        pass

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:  # TODO: IMPLEMENT
        super().execute_cycle()

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:  # TODO: IMPLEMENT
        super().suggested_mode()
