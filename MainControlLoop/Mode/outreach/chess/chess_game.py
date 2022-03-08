import chess
import chess.engine
import random
from stockfish import Stockfish
from lib.exceptions import wrap_errors, LogicalError


class ChessGame:
    """
    Chess Game Object
    """

    @wrap_errors(LogicalError)
    def __init__(self, sfr, game_id):
        """
        :param sfr: sfr object
        :type sfr: :class: 'lib.registry.StateFieldRegistry'
        :param game_id: unique identifier of this game
        :type game_id: str
        """
        self.sfr = sfr
        self.game_id = game_id
        self.board = chess.Board()

    @wrap_errors(LogicalError)
    def __str__(self) -> str:
        """
        Return a transmittable string representation of the current board state and game id
        :return: board state and game id
        :rtype: str
        """
        return f"Chess;{self.board.fen()};{self.game_id}"

    @wrap_errors(LogicalError)
    def set_game(self, fen: str):
        """
        Set the state of a game based on a given board representation
        :param fen: board representation
        :type fen: str
        """
        self.board.set_fen(fen)

    @wrap_errors(LogicalError)
    def get_best_move(self):
        stockfish = Stockfish(path='MainControlLoop/Mode/outreach/chess/stockfish_exe',
                              parameters={"Minimum Thinking Time": 5})
        stockfish.set_fen_position(self.board.fen())
        move = stockfish.get_best_move_time(self.sfr.vars.OUTREACH_MAX_CALCULATION_TIME)
        move = self.board.parse_san(move)
        return move

    @wrap_errors(LogicalError)
    def push(self, move: chess.Move):
        """
        Update board with a move
        :param move: uci string as move (i.e. d2d4)
        :type move: :class: 'chess.Move'
        """
        self.board.push(move)

    @wrap_errors(LogicalError)
    def random_fen(self):  # simulation only
        """
        DEBUG ONLY
        Generate a random move and return new board state
        """
        while True:
            board = chess.Board()
            for _ in range(random.randint(10, 20)):
                move = list(board.legal_moves)[random.randint(0, len(list(board.legal_moves))-1)]
                board.push(move)
                if chess.Board.outcome(board) is not None:
                    break
            if chess.Board.outcome(board) is not None:
                continue
            else:
                return board.fen()
