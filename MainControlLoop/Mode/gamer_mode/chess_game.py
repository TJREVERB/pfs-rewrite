import chess
import chess.engine


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














