from Drivers.transmission_packet import UnsolicitedString
from MainControlLoop.Mode.outreach.chess.chess_game import ChessGame
from MainControlLoop.Mode.outreach.tictactoe.tictactoe_game import TicTacToeGame
from MainControlLoop.Mode.outreach.ultimate_tictactoe.ultimate_game import UltimateTicTacToeGame
from MainControlLoop.Mode.outreach.jokes.jokes_game import JokesGame
from MainControlLoop.Mode.mode import Mode
from lib.exceptions import wrap_errors, LogicalError
import time


class Outreach(Mode):
    """
    This mode interfaces with a web server on the ground, allowing anyone around the world to play games with REVERB
    Currently available games: chess, jokes, tictactoe, ultimate tictactoe
    """

    @wrap_errors(LogicalError)
    def __init__(self, sfr):
        """
        :param sfr: sfr object
        :type sfr: :class: 'lib.registry.StateFieldRegistry'
        """
        super().__init__(sfr)
        self.sfr = sfr
        self.string_game_queue = []  # string format = game;board_string;game_id
        self.object_game_queue = []
        # games are "TicTacToe", "Chess"

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Returns 'Outreach'
        :return: mode name
        :rtype: str
        """
        return "Outreach"

    @wrap_errors(LogicalError)
    def start(self) -> bool:
        """
        Enables only primary radio for communication with ground
        Returns False if we're not supposed to be in this mode due to locked devices
        """
        self.string_game_queue.extend(self.sfr.vars.outreach_buffer)
        self.sfr.vars.outreach_buffer.clear()
        return super().start([self.sfr.vars.PRIMARY_RADIO])

    @wrap_errors(LogicalError)
    def suggested_mode(self) -> Mode:
        """
        If battery is low, suggest Charging -> Outreach
        Otherwise, suggest self
        :return: mode to switch to
        :rtype: :class: 'MainControlLoop.Mode.mode.Mode'
        """
        super().suggested_mode()
        if self.sfr.check_lower_threshold():
            return self.sfr.modes_list["Charging"](self.sfr, self)
        else:
            return self

    @wrap_errors(LogicalError)
    def decode_game_queue(self):
        """
        Turns encoded strings in game_queue, returns the list of game objects.
        Clears game_queue.
        :return: list of game objects
        :rtype: list
        """
        for encoded_string in self.string_game_queue:
            game, board_string, game_id = encoded_string.split(";")

            if game == "TicTacToe":
                obj = TicTacToeGame(self.sfr, game_id)
                obj.set_game(board_string)
                self.object_game_queue.append(obj)

            elif game == "Chess":
                obj = ChessGame(self.sfr, game_id)
                obj.set_game(board_string)
                self.object_game_queue.append(obj)

            elif game == "Ultimate":
                obj = UltimateTicTacToeGame(self.sfr, game_id)
                obj.set_game(board_string)
                self.object_game_queue.append(obj)

            elif game == "Jokes":
                obj = JokesGame(self.sfr, game_id)
                obj.set_game(board_string)
                self.object_game_queue.append(obj)

    @wrap_errors(LogicalError)
    def execute_cycle(self) -> None:
        """
        Execute a single cycle of Outreach mode
        Decode game queue and get game objects
        For each game in the queue, get best AI move and transmit updated game
        Computing time for executing queue
        """
        self.decode_game_queue()
        time_started = time.time()
        while len(self.object_game_queue) > 0:
            game = self.object_game_queue.pop()
            print(game)
            ai_move = game.get_best_move()
            print(f"AIMOVE: {ai_move}", file = open("pfs-output.txt", "a"))
            game.push(ai_move)
            self.transmit_string(str(game))
            if time.time() - 60 > time_started:  # limit compute time per cycle
                break

    @wrap_errors(LogicalError)
    def transmit_string(self, message: str):
        """
        Transmit a string message to ground
        :param message: message to transmit (usually a game representation)
        :type message: str
        """
        packet = UnsolicitedString(return_data=[message])
        self.sfr.command_executor.transmit(packet)

    @wrap_errors(LogicalError)
    def terminate_mode(self) -> None:
        """
        Make one final move on all games in buffer and transmit results
        """
        self.execute_cycle()  # finish all games in buffer
