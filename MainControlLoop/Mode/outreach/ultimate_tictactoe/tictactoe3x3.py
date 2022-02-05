import numpy as np
import time
import copy


class TicTacToe:
    def __init__(self, is_ai_turn):
        self.is_ai_turn = is_ai_turn
        self.human_board = np.zeros((3, 3))  # X
        self.ai_board = np.zeros((3, 3))  # O
        self.winning_combinations = [0x1C0, 0x38, 0x7, 0x124, 0x92, 0x49, 0x111, 0x54]
        self.draw_combination = 0x1FF

    def __str__(self):  # returns encoded board
        """
        Encoding: flattened array turned into string, with x as human and o as ai.
        Nothing is encoded as -
        X - O
        O O X
        - - X
        x-ooox--x
        """
        encoded_string = ""
        human_board = self.human_board.reshape((9,))
        ai_board = self.ai_board.reshape((9,))
        for i in range(9):
            if int(human_board[i]) == 1:
                encoded_string += "x"
            elif int(ai_board[i]) == 1:
                encoded_string += "o"
            else:
                encoded_string += "-"
        return f"{encoded_string}"

    def set_game(self, board_string: str):
        """Sets board to proper board according to string"""
        human_board = np.zeros((9,))
        ai_board = np.zeros((9,))
        for i in range(9):
            if board_string[i] == "x":
                human_board[i] = 1.0
            elif board_string[i] == "o":
                ai_board[i] = 1.0
        self.human_board = human_board.reshape((3, 3))
        self.ai_board = ai_board.reshape((3, 3))
        return self

    def check_winner(self) -> tuple:  # (x_status, o_status) 0 = no winner, 1 = won, (1, 1) if draw
        human_bitboard = self.get_bitboard(self.human_board)
        ai_bitboard = self.get_bitboard(self.ai_board)
        for binary in self.winning_combinations:
            if (binary & human_bitboard) in self.winning_combinations:
                return 1, 0
            elif (binary & ai_bitboard) in self.winning_combinations:
                return 0, 1
        if human_bitboard | ai_bitboard == self.draw_combination:
            return 1, 1
        return 0, 0

    def switch_turn(self):
        if self.is_ai_turn:
            self.is_ai_turn = False
        else:
            self.is_ai_turn = True

    def is_valid_move(self, location: list) -> bool:
        x, y = location[0], location[1]
        if type(x) != int or type(y) != int:
            return False
        if x > 2 or x < 0 or y > 2 or y < 0:
            return False
        if self.human_board[x][y] == 0 and self.ai_board[x][y] == 0:
            return True
        else:
            return False

    def get_valid_moves(self) -> list:
        """
        returns all valid moves as list of lists
        """

        possible_moves = [[x, y] for y in range(3) for x in range(3)]
        possible_moves = list(map(self.is_valid_move, possible_moves))
        valid_moves = [move for move in possible_moves if move is not None]
        return valid_moves

    def push(self, location: list) -> None:  # Takes coords as [row, column] i.e. [x, y]
        location = list(map(int, location))
        x, y = location[0], location[1]
        if self.is_ai_turn:
            self.ai_board[x][y] = 1.0
        else:
            self.human_board[x][y] = 1.0
        self.switch_turn()

    def push_move_to_copy(self, location: list):
        """returns new game object with pushed move"""
        new_board = self.deepcopy()
        new_board.push(location)
        return new_board

    def get_bitboard(self, array: np.array) -> int:
        new_list = np.reshape(array, (9,)).tolist()
        new_list = map(int, new_list)
        new_list = list(map(str, new_list))
        bitboard = int("".join(new_list), 2)
        return bitboard

    def get_board_array(self) -> np.array:  # human piece = 1, ai = -1
        return np.add(self.human_board, self.ai_board * -1)

    def deepcopy(self):
        new_object = TicTacToe(self.is_ai_turn)
        new_object.is_ai_turn = self.is_ai_turn
        new_object.human_board = self.human_board.copy()
        new_object.ai_board = self.ai_board.copy()
        return new_object






