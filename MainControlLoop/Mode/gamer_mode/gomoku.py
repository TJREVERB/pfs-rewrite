import numpy as np


class GomokuGame:
    def __init__(self, size: int, is_ai_turn_first: bool, winning_in_a_row: int):
        self.size = size
        self.winning_in_a_row = winning_in_a_row
        self.human_board = np.zeros((size, size))  # X
        self.ai_board = np.zeros((size, size))  # O
        self.is_ai_turn = is_ai_turn_first

    def check_winner(self) -> tuple:  # (x_status, o_status) 0 = no winner, 1 = won, 1, 1 if draw
        def _check_draw() -> bool:
            x_bitboard = self.get_bitboard(self.human_board)
            o_bitboard = self.get_bitboard(self.ai_board)
            combined_bitboard = x_bitboard + o_bitboard
            if _check(combined_bitboard, 1, iterations=self.size**2+self.size-1):
                return True
            else:
                return False

        def _check(bitboard: int, constant: int, iterations: int = self.winning_in_a_row) -> bool:
            current = bitboard
            for _ in range(iterations):
                new = current & (current >> constant)
                current = new
            if current:
                return True
            else:
                return False

        # X
        if _check(self.get_bitboard(self.human_board), self.size):  # horizontal
            return 1, 0
        if _check(self.get_bitboard(self.human_board), 1):  # vertical
            return 1, 0
        if _check(self.get_bitboard(self.human_board), self.size+1):  # left_diagonal
            return 1, 0
        if _check(self.get_bitboard(self.human_board), self.size-1):  # right_diagonal
            return 1, 0

        # O
        if _check(self.get_bitboard(self.ai_board), self.size):  # horizontal
            return 0, 1
        if _check(self.get_bitboard(self.ai_board), 1):  # vertical
            return 0, 1
        if _check(self.get_bitboard(self.ai_board), self.size+1):  # left_diagonal
            return 0, 1
        if _check(self.get_bitboard(self.ai_board), self.size-1):  # right_diagonal
            return 0, 1

        if _check_draw():  # check draw
            return 1, 1

        return 0, 0

    def is_valid_move(self, location: list) -> bool:
        x, y = location[0], location[1]
        if self.human_board[x][y] == 0 and self.ai_board[x][y] == 0:
            return True
        else:
            return False

    def push_move(self, location: list) -> None:  # Takes coords as [row, column] i.e. [x, y]
        x, y = location[0], location[1]
        if not self.is_valid_move(location):
            raise InvalidMoveError()
        if self.turn == 1:
            self.human_board[x][y] = 1.0
        else:
            self.ai_board[x][y] = 1.0
        self.turn = self.turn * -1

    def get_valid_moves(self) -> list:
        def _is_valid_move(move: list):
            if self.is_valid_move(move):
                return move
            else:
                return None

        possible_moves = [[x, y] for y in range(self.size) for x in range(self.size)]
        possible_moves = list(map(_is_valid_move, possible_moves))
        valid_moves = [move for move in possible_moves if move is not None]
        return valid_moves

    def __str__(self):
        board = np.empty((19, 19)).tolist()
        for x in range(19):
            for y in range(19):
                if self.human_board[x][y] == 1:
                    board[x][y] = "X"
                elif self.ai_board[x][y] == 1:
                    board[x][y] = "O"
                else:
                    board[x][y] = "."
        final_string = ""
        for row in board:
            final_string += str(row) + "\n"
        return final_string

    def get_bitboard(self, array: np.array) -> int:
        new_list = [0 for _ in range(self.size)]
        new_list.extend(np.reshape(array, (self.size**2,)).tolist())
        new_list = map(int, new_list)
        new_list = list(map(str, new_list))
        bitboard = int("".join(new_list), 2)
        return bitboard

    def get_bit_array(self, board_list: list) -> list:
        x_bit_list = [board.human_board for board in board_list]
        o_bit_list = [board.ai_board for board in board_list]
        x_bit_list.extend(o_bit_list)
        return x_bit_list


