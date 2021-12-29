import chess
import chess.engine
import random

class ChessGame:
    def __init__(self, sfr, game_id):
        self.sfr = sfr
        self.game_id = game_id
        self.board = chess.Board()

    def __str__(self):
        return f"Chess;{self.board.fen()};{self.game_id}"

    def set_game(self, fen: str):
        self.board.set_fen(fen)

    def get_best_move(self) -> chess.Move:
        engine = chess.engine.SimpleEngine.popen_uci(r"C:\Users\hi2kh\OneDrive\Documents\GitHub\pfs-rewrite\MainControlLoop\Mode\gamer_mode\stockfish_14_win_x64_popcnt\stockfish_14_x64_popcnt.exe")
        # TODO: test file path on pi
        result = engine.play(self.board, chess.engine.Limit(time=0.1))
        engine.quit()
        return result.move

    def push(self, move: chess.Move):  # uci string as move (i.e. d2d4)
        self.board.push(move)

    def random_fen(self):  # simulate purposes
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














