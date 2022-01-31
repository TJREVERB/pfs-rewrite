from Drivers.transmission_packet import UnsolicitedString
from MainControlLoop.Mode.outreach.chess_game import ChessGame
from MainControlLoop.Mode.outreach.tictactoe_game import TicTacToeGame
from MainControlLoop.Mode.mode import Mode
import random
import chess
from lib.exceptions import wrap_errors, LogicalError


class Outreach(Mode):
    def __init__(self, sfr):
        super().__init__(sfr)
        self.sfr = sfr
        self.game_queue = []  # string format = game;board_string;game_id
        # games are "TicTacToe", "Chess"

    def __str__(self):
        return "Gamer"

    def start(self):
        super().start([self.sfr.vars.PRIMARY_RADIO])

    def suggested_mode(self):
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:
            return self.sfr.modes_list["Charging"](self.sfr, self)
        else:
            return self

    def decode_game_queue(self):
        """Turns encoded strings in game_queue, returns the list of game objects. Clears game_queue."""
        game_objects = []
        for encoded_string in self.game_queue:
            encoded_list = encoded_string.split(";")
            game, board_string, game_id = encoded_list[0], encoded_list[1], encoded_list[2]

            if game == "TicTacToe":
                obj = TicTacToeGame(self.sfr, game_id)
                obj.set_game(board_string)
                game_objects.append(obj)

            elif game == "Chess":
                obj = ChessGame(self.sfr, game_id)
                obj.set_game(board_string)
                game_objects.append(obj)

        return game_objects

    def simulate_games(self):  # debug
        for _ in range(10):
            obj = ChessGame(self.sfr, 1)
            game = f"Chess;{obj.random_fen()};{str(random.randint(1000000000, 9999999999))}"
            self.game_queue.append(game)

    def execute_cycle(self) -> None:
        self.simulate_games()
        game_queue = self.decode_game_queue()
        for game in game_queue:
            ai_move = game.get_best_move()
            print(f"AIMOVE: {ai_move}")
            game.push(ai_move)
            #self.transmit_string(str(game))
        self.game_queue.clear()

    def transmit_string(self, message: str):
        packet = UnsolicitedString(return_data=[message])
        self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit(packet)

    def terminate_mode(self) -> None:
        self.execute_cycle()  # finish all games in buffer



