import chess


class ChessGame:
    def __init__(self, sfr, ai_is_white=False):
        self.sfr = sfr
        self.ai_is_white = ai_is_white
        self.is_ai_turn = ai_is_white
        self.board_obj =

    def check_winner(self):
        winner = chess.Board.outcome(self.board_obj)







