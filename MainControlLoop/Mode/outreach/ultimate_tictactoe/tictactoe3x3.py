import numpy as np
import copy
import random


def binary_scale(n):
    for i in range(n, 0, -1):
        yield 2 ** n


class TicTacToe:
    def __init__(self, is_ai_turn):
        self.is_ai_turn = is_ai_turn
        self.human_board = 0
        self.ai_board = 0
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
        for i in binary_scale(9):
            if self.human_board >> i & 1:
                encoded_string += "x"
            elif self.ai_board >> i & 1:
                encoded_string += "o"
            else:
                encoded_string += "-"
        return encoded_string

    def board_string(self, row):  # for testing, human only
        row = row % 3
        string = ""
        for col in range(3):
            if self.human_board >> row * 3 + col:  # if human piece
                string += 'x'
            elif self.ai_board >> row * 3 + col:
                string += 'o'
            else:
                string += '.'
            string += " | "
        return string.strip()

    def set_game(self, board_string: str):
        """Sets board to proper board according to string"""
        for i in binary_scale(9):
            if board_string[i] == "x":
                self.human_board += i
            elif board_string[i] == "o":
                self.ai_board += i

    def check_winner(self) -> int:  # (x_status, o_status) 0 = human win, 1 = draw, 2 = ai win, -1 = game incomplete
        if self.human_board in self.winning_combinations:
            return 0
        elif self.ai_board in self.winning_combinations:
            return 2
        elif self.human_board == self.draw_combination:  # Split to two if statements for efficiency
            return 1
        elif self.ai_board == self.draw_combination:
            return 1
        return -1

    def switch_turn(self):
        self.is_ai_turn = not self.is_ai_turn

    def is_valid_move(self, location: int) -> int:
        return ~(self.human_board & self.ai_board) >> location & 1

    def get_valid_moves(self) -> [int]:
        """
        returns all valid moves as list of integer moves
        """
        return [i for i in binary_scale(9) if self.is_valid_move(i)]

    def push(self, move: int) -> None:  # Takes integer move
        if self.is_ai_turn:
            self.ai_board += move
        else:
            self.human_board += move
        self.switch_turn()

    def push_move_to_copy(self, move: int):
        """returns new game object with pushed move"""
        new_board = copy.deepcopy(self)
        new_board.push(move)
        return new_board

    def random(self):
        board = TicTacToe(True)
        for _ in range(4):
            board.push(random.choice(board.get_valid_moves()))
            if random.random() < 1 / 4:
                break
        return str(board)
