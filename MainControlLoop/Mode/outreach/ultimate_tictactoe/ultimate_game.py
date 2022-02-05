import numpy as np
from MainControlLoop.Mode.outreach.ultimate_tictactoe.tictactoe3x3 import TicTacToe


class UltimateTicTacToeGame:
    def __init__(self, sfr, game_id):
        self.sfr = sfr
        self.game_id = game_id
        self.board = [] # must call set_game
        self.is_ai_turn = True
        self.winning_combinations = [0x1C0, 0x38, 0x7, 0x124, 0x92, 0x49, 0x111, 0x54]
        self.draw_combination = 0x1FF

    def __str__(self):
        """
        board is encoded as the nine 3x3 tictactoe boards, flattened then run through 3x3 string encoder
        the 3x3 board strings are seperated as commas
        current turn is encoded at the end by h or a, h is human turn next, a is ai turn next
        i.e. x-ooox--x,o-xxx-oo-, ...(continues),---o-x-o-h
        'UltimateTicTacToe' is then inserted to the front, and turn char is appended at the back, either
        """
        board_string = ",".join([str(board) for board in self.board])
        return f"Ultimate;{board_string};{self.game_id}"

    def set_game(self, board_string):
        lst = board_string.split(";")
        board_str = lst[1]
        self.board = np.array([TicTacToe(self.is_ai_turn).set_game(board) for board in board_str.split(",")])

    def get_valid_moves(self):
        """
        Moves represented as [x, y, z], x: 3x3 board, y: x row on 3x3 board, z: y row on 3x3 board
        """
        move_list = []
        for i, board in enumerate(self.board):
            if board.check_winner() == (0, 0):
                legal_moves = [move.insert[i] for move in board.get_valid_moves()]
                move_list.extend(legal_moves)
        return move_list

    def push(self, location: list):
        """
        Moves represented as [x, y, z], x: 3x3 board, y: x row on 3x3 board, z: y row on 3x3 board
        """
        self.board[location[0]].push([location[1], location[2]])
        for i, board in enumerate(self.board):
            if not i == location[0]:
                board.switch_turn()

    def push_move_to_copy(self, location: list):
        """
        pushes a move to new game object
        :param location:
        :return: new UltimateTicTacToe game object
        """
        game = self.deepcopy()
        game.push(location)
        return game

    def deepcopy(self):
        new_board = np.array([board.deepcopy() for board in self.board])
        game = UltimateTicTacToeGame(self.sfr, self.game_id)
        game.board = new_board
        return game

    def check_winner(self):
        def _check(human_bitboard, ai_bitboard):
            for binary in self.winning_combinations:
                if (binary & human_bitboard) in self.winning_combinations:
                    return 1, 0
                elif (binary & ai_bitboard) in self.winning_combinations:
                    return 0, 1
            if human_bitboard | ai_bitboard == self.draw_combination:
                return 1, 1
            return 0, 0
        human_board = []
        ai_board = []
        for board in self.board:
            if board.check_winner() == (1, 0):  # human won
                human_board.append(1)
                ai_board.append(0)
            elif board.check_winner() == (0, 1):  # ai won
                human_board.append(0)
                ai_board.append(1)
            else:  # draw, append 0 bc doesn't matter whether no one won or draw for overall winner calc
                human_board.append(0)
                ai_board.append(0)

        return _check(self.get_bitboard(np.array(human_board)), self.get_bitboard(np.array(ai_board)))

    def get_bitboard(self, array: np.array) -> int:
        new_list = np.reshape(array, (9,)).tolist()
        new_list = map(int, new_list)
        new_list = list(map(str, new_list))
        bitboard = int("".join(new_list), 2)
        return bitboard

#e = UltimateTicTacToeGame(5, 5)
#e.set_game(f"Ultimate;o-xx-x--x,x--o-o-o-,o-o-----x,o--------,xxx-----o,ox-------,--------o,-x--o--x-,-o--o-xox")
#e.set_game(f"Ultimate;o-xx-x--x,x--o-o-o-,o-o-----x,o--------,xxx-----o,ox-------,--------o,-x--o--x-,-x--x-oxo")
#print(e.board)
#print(e.check_winner())
#e.push([2, 0, 1])
#print(str(e))








