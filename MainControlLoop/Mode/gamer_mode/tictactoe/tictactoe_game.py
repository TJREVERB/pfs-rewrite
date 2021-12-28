import numpy as np
import random
import time
import copy


class InvalidMoveError(Exception):
    pass


class TicTacToeGame:
    def __init__(self, is_ai_turn_first=False):
        self.is_ai_turn_first=is_ai_turn_first
        self.human_board = np.zeros((3, 3))  # X
        self.ai_board = np.zeros((3, 3))  # O
        self.is_ai_turn = is_ai_turn_first

    def check_winner(self) -> tuple:  # (x_status, o_status) 0 = no winner, 1 = won, 1, 1 if draw
        def _check_draw() -> bool:
            x_bitboard = self.get_bitboard(self.human_board)
            o_bitboard = self.get_bitboard(self.ai_board)
            combined_bitboard = x_bitboard + o_bitboard
            if _check(combined_bitboard, 1, iterations=3**2-1):
                return True
            else:
                return False

        def _check(bitboard: int, constant, iterations = 3-1) -> bool:
            print(bin(bitboard))
            current = bitboard
            for _ in range(iterations):
                current = current & (current >> constant)
                print(_)
                print(bin(current))
            if current:
                return True
            else:
                return False

        # X (human)
        if _check(self.get_bitboard(self.human_board), 3):  # horizontal
            return 1, 0
        if _check(self.get_bitboard(self.human_board), 1):  # vertical
            return 1, 0
        if _check(self.get_bitboard(self.human_board), 3+1):  # left_diagonal
            return 1, 0
        if _check(self.get_bitboard(self.human_board), 3-1):  # right_diagonal
            return 1, 0

        # O (ai)
        if _check(self.get_bitboard(self.ai_board), 3):  # horizontal
            return 0, 1
        if _check(self.get_bitboard(self.ai_board), 1):  # vertical
            return 0, 1
        if _check(self.get_bitboard(self.ai_board), 3+1):  # left_diagonal
            return 0, 1
        if _check(self.get_bitboard(self.ai_board), 3-1):  # right_diagonal
            return 0, 1

        if _check_draw():  # check draw
            return 1, 1

        return 0, 0

    def switch_turn(self):
        self.is_ai_turn = not self.is_ai_turn

    def is_valid_move(self, location: list) -> bool:
        x, y = location[0], location[1]
        if self.human_board[x][y] == 0 and self.ai_board[x][y] == 0:
            return True
        else:
            return False

    def push(self, location: list) -> None:  # Takes coords as [row, column] i.e. [x, y]
        location = list(map(int, location))
        x, y = location[0], location[1]
        if not self.is_valid_move(location):
            raise InvalidMoveError()
        if not self.is_ai_turn:
            self.human_board[x][y] = 1.0
        else:
            self.ai_board[x][y] = 1.0
        self.switch_turn()

    def push_move_to_copy(self, location: list):
        """returns new game object with pushed move"""
        new_board = copy.deepcopy(self)
        location = list(map(int, location))
        x, y = location[0], location[1]
        if not new_board.is_valid_move(location):
            raise InvalidMoveError()
        if not new_board.is_ai_turn:
            new_board.human_board[x][y] = 1.0
        else:
            new_board.ai_board[x][y] = 1.0
        new_board.switch_turn()
        return new_board
    def get_valid_moves(self) -> list:
        """
        returns all valid moves as list of lists
        """
        def _is_valid_move(move: list):
            if self.is_valid_move(move):
                return move
            else:
                return None

        possible_moves = [[x, y] for y in range(3) for x in range(3)]
        possible_moves = list(map(_is_valid_move, possible_moves))
        valid_moves = [move for move in possible_moves if move is not None]
        return valid_moves

    def minimax(self, board, is_maximizing_player, time_started):
        if board.check_winner() == (1, 0):
            return -10
        elif board.check_winner() == (0, 1):
            return 10
        elif time.time() - 10 > time_started:
            # timeout
        if is_maximizing_player:
            score = -9999
            for move in board.get_valid_moves():
                self.minimax(self.push_move_to_copy(move), not is_maximizing_player, time_started)


    def get_best_move(self):  # TODO: implement


    def get_bitboard(self, array: np.array) -> int:
        new_list = [0 for _ in range(3)]
        new_list.extend(np.reshape(array, (3**2,)).tolist())
        new_list = map(int, new_list)
        new_list = list(map(str, new_list))
        bitboard = int("".join(new_list), 2)
        return bitboard

    def get_board_array(self) -> np.array:  # human piece = 1, ai = -1
        return np.add(self.human_board, self.ai_board*-1)

    def __str__(self):  # returns encoded board
        """ board representation for testing.
        board = np.empty((3, 3)).tolist()
        for x in range(3):
            for y in range(3):
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
        """
        encoded_string = ""
        human_board = self.human_board.reshape((9,))
        ai_board = self.ai_board.reshape((9,))
        for c in human_board:
            if c == 0:
                encoded_string += "-"
            else:
                encoded_string += c.lower()
        for c in ai_board:
            if c == 0:
                encoded_string += "-"
            else:
                encoded_string += c.lower()
        if self.is_ai_turn:
            encoded_string += "a"
        else:
            encoded_string += "h"
        return encoded_string






game = TicTacToeGame()
while True:
    if game.check_winner() == (1, 0):
        print("Human Wins")
        break
    elif game.check_winner() == (0, 1):
        print("AI Wins")
        break
    elif game.check_winner() == (1, 1):
        print("Draw")
        break

    print(game)
    while True:
        x = int(input("Move Row"))
        y = int(input("Move Col"))
        try:
            game.push_move([x, y])
            break
        except InvalidMoveError:
            pass
