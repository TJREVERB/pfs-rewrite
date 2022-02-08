<<<<<<< HEAD
from Drivers.transmission_packet import UnsolicitedString
from MainControlLoop.Mode.outreach.chess.chess_game import ChessGame
from MainControlLoop.Mode.outreach.tictactoe.tictactoe_game import TicTacToeGame
from MainControlLoop.Mode.mode import Mode
import random
import time


class Outreach(Mode):
    """
    This mode interfaces with a web server on the ground, allowing anyone around the world to play games with REVERB
    Currently available games: chess, jokes, tictactoe, ultimate tictactoe
    """
    def __init__(self, sfr):
        """
        :param sfr: sfr object
        :type sfr: :class: 'lib.registry.StateFieldRegistry'
        """
        super().__init__(sfr)
        self.sfr = sfr
        self.string_game_queue = []  # string format = game;board_string;game_id
        self.decoded_game_queue = []  # game objects
        # games are "TicTacToe", "Chess"

    def __str__(self) -> str:
        """
        Returns 'Outreach'
        :return: mode name
        :rtype: str
        """
        return "Outreach"

    def start(self) -> bool:
        """
        Enables only primary radio for communication with ground
        Returns False if we're not supposed to be in this mode due to locked devices
        """
        return super().start([self.sfr.vars.PRIMARY_RADIO])

    def suggested_mode(self) -> Mode:
        """
        If battery is low, suggest Charging -> Outreach
        Otherwise, suggest self
        :return: mode to switch to
        :rtype: :class: 'MainControlLoop.Mode.mode.Mode'
        """
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:
            return self.sfr.modes_list["Charging"](self.sfr, self)
        else:
            return self

    def decode_game_queue(self) -> None:
        """
        Turns encoded strings in string_game_queue, appends game objects to self.decoded_game_queue.
        Clears game_queue.
        """
        while len(self.string_game_queue) > 0:
            encoded_string = self.string_game_queue.pop()
            encoded_list = encoded_string.split(";")
            game, board_string, game_id = encoded_list[0], encoded_list[1], encoded_list[2]

            if game == "TicTacToe":
                obj = TicTacToeGame(self.sfr, game_id)
                obj.set_game(board_string)
                self.decoded_game_queue.append(obj)

            elif game == "Chess":
                obj = ChessGame(self.sfr, game_id)
                obj.set_game(board_string)
                self.decoded_game_queue.append(obj)



    def simulate_games(self) -> None:  # debug
        """
        Debug only
        """
        for _ in range(1):
            obj = ChessGame(self.sfr, 1)
            game = f"Chess;{obj.random_fen()};{str(random.randint(1000000000, 9999999999))}"
            self.string_game_queue.append(game)

    def execute_cycle(self) -> None:
        """
        Execute a single cycle of Outreach mode
        Decode game queue and get game objects
        For each game in the queue, get best AI move and transmit updated game
        Computing time for executing queue
        """
        self.simulate_games()  # DEBUG
        self.decode_game_queue()
        time_started = time.time()
        while len(self.decoded_game_queue) > 0:
            game = self.decoded_game_queue.pop()
            ai_move = game.get_best_move()
            print(f"AIMOVE: {ai_move}")
            game.push(ai_move)
            # self.transmit_string(str(game))
            if time.time() - 60 > time_started:  # limit compute time per cycle
                break

    def transmit_string(self, message: str):
        """
        Transmit a string message to ground
        :param message: message to transmit (usually a game representation)
        :type message: str
        """
        packet = UnsolicitedString(return_data=[message])
        self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit(packet)

    def terminate_mode(self) -> None:
        """
        Make one final move on all games in buffer and transmit results
        """
        self.execute_cycle()  # finish all games in buffer
=======
>>>>>>> parent of db47368 (Merge branch 'master' into dev)
