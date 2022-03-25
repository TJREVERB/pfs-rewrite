import numpy as np
import copy
from MainControlLoop.Mode.outreach.tictactoe.table import get_table
from lib.exceptions import wrap_errors, LogicalError


class TicTacToeGame:
    @wrap_errors(LogicalError)
    def __init__(self, sfr, game_id):
        self.sfr = sfr
        self.game_id = game_id
        self.human_board = np.zeros((3, 3))  # X
        self.ai_board = np.zeros((3, 3))  # O
        self.is_ai_turn = True
        self.winning_combinations = [0x1C0, 0x38, 0x7, 0x124, 0x92, 0x49, 0x111, 0x54]
        self.draw_combination = 0x1FF

    @wrap_errors(LogicalError)
    def __str__(self):  # returns encoded board
        """
        Encoding: flattened array turned into string, with x as human and o as ai.
        Nothing is encoded as -
        Turn is represented as either h for human turn or a for ai turn.
        Turn char is added at the end of the board encoding.
        X - O
        O O X
        - - X  with human to move would be encoded as:
        x-ooox--xh
        Note: all encodings are with lowercase chars

        Game ID: string of 10 random numbers
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
        if self.is_ai_turn:
            encoded_string += "a"
        else:
            encoded_string += "h"
        return f"TicTacToe;{encoded_string};{self.game_id}"

    @wrap_errors(LogicalError)
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
        if board_string[9] == "h":
            self.is_ai_turn = False
        else:
            self.is_ai_turn = True
        #  always be ai turn

    @wrap_errors(LogicalError)
    def get_best_move(self):
        table = get_table()
        game_string = str(self).split(';')[1]
        if game_string in table:  # always should be in table
            return list(table[game_string])
        else:  # TODO: figure out what happens
            raise RuntimeError

    @wrap_errors(LogicalError)
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

    @wrap_errors(LogicalError)
    def switch_turn(self):
        self.is_ai_turn = not self.is_ai_turn

    @wrap_errors(LogicalError)
    def is_valid_move(self, location: [int, int]) -> bool:
        idx = tuple(location)
        x, y = idx
        if x > 2 or x < 0 or y > 2 or y < 0:
            return False
        if self.human_board[idx] == 0 and self.ai_board[idx] == 0:
            return True
        else:
            return False

    @wrap_errors(LogicalError)
    def get_valid_moves(self) -> list:
        """
        returns all valid moves as list of lists
        """
        return [[x, y] for y in range(3) for x in range(3) if self.is_valid_move([x, y])]

    @wrap_errors(LogicalError)
    def push(self, location: list) -> None:  # Takes coords as [row, column] i.e. [x, y]
        idx = (int(location[0]), int(location[1]))
        if self.is_ai_turn:
            self.ai_board[idx] = 1.0
        else:
            self.human_board[idx] = 1.0
        self.switch_turn()

    @wrap_errors(LogicalError)
    def push_move_to_copy(self, location: list):
        """returns new game object with pushed move"""
        new_board = self.deepcopy()
        new_board.push(location)
        return new_board

    @wrap_errors(LogicalError)
    def get_bitboard(self, array: np.array) -> int:
        new_list = list(np.reshape(array, (9,)))
        new_list = map(int, new_list)
        new_list = list(map(str, new_list))
        bitboard = int("".join(new_list), 2)
        return bitboard

    @wrap_errors(LogicalError)
    def get_board_array(self) -> np.array:  # human piece = 1, ai = -1
        return np.add(self.human_board, self.ai_board * -1)

    @wrap_errors(LogicalError)
    def deepcopy(self):
        return copy.deepcopy(self)
