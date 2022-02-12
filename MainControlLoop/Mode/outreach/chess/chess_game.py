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
        #print(self.board.is_game_over())
        transport, engine = await chess.engine.popen_uci(r'MainControlLoop/Mode/outreach/chess/stockfish_exe')
        result = await engine.play(self.board, chess.engine.Limit(time=float(self.sfr.vars.OUTREACH_MAX_CALCULATION_TIME)))
        await engine.quit()
        return result.move
        #return 22
    def __get_best_move(self):
        engine = chess.engine.SimpleEngine.popen_uci(r'MainControlLoop/Mode/outreach/chess/stockfish_exe')
        result = engine.play(self.board, chess.engine.Limit(time=float(self.sfr.vars.OUTREACH_MAX_CALCULATION_TIME)))
        engine.quit()
        return result.move
    #rnbqk2r/pp1pnpp1/2p1p3/b6p/P1P1N1P1/3P4/3BPP1P/RN1QKB1R b KQkq - 2 10
    def get_best_move(self):
        asyncio.set_event_loop_policy(chess.engine.EventLoopPolicy())
        result = asyncio.run(self._get_best_move())
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
