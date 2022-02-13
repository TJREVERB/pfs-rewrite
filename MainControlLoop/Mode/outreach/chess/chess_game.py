import chess
import chess.engine
import random
import asyncio


class ChessGame:
    """
    Chess Game Object
    """
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

    def __str__(self) -> str:
        """
        Return a transmittable string representation of the current board state and game id
        :return: board state and game id
        :rtype: str
        """
        return f"Chess;{self.board.fen()};{self.game_id}"

    def set_game(self, fen: str):
        """
        Set the state of a game based on a given board representation
        :param fen: board representation
        :type fen: str
        """
        self.board.set_fen(fen)

    async def _get_best_move(self) -> chess.Move:
        """
        Get best move by using Stockfish
        :return: best move
        :rtype: :class: 'chess.Move'
        """
        if not self.board.is_valid():
            print("INVALID BOARD")
            raise Exception
        transport, engine = await chess.engine.popen_uci(r'MainControlLoop/Mode/outreach/chess/stockfish_exe')
        result = await engine.play(
            self.board, chess.engine.Limit(time=float(self.sfr.vars.OUTREACH_MAX_CALCULATION_TIME)))
        result = result.move
        await engine.quit()
        return result

    def __get_best_move(self):
        engine = chess.engine.SimpleEngine.popen_uci(r'MainControlLoop/Mode/outreach/chess/stockfish_exe', timeout=None)
        result = engine.play(self.board, chess.engine.Limit(time=float(self.sfr.vars.OUTREACH_MAX_CALCULATION_TIME)))
        #result.move

    def get_best_move(self):
        while True:
            try:
                asyncio.set_event_loop_policy(chess.engine.EventLoopPolicy())
                result = asyncio.run(self._get_best_move())
            except:
                print("CHESS EXCEPTION: "+ str(self.board))
                continue
            else:
                return result

    def push(self, move: chess.Move):
        """
        Update board with a move
        :param move: uci string as move (i.e. d2d4)
        :type move: :class: 'chess.Move'
        """
        self.board.push(move)

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
