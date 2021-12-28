import numpy as np
import random
import time
import copy


class InvalidMoveError(Exception):
    pass


class TicTacToeGame:

    def __init__(self, sfr, is_ai_turn_first=False):
        self.sfr = sfr
        self.human_board = np.zeros((3, 3))  # X
        self.ai_board = np.zeros((3, 3))  # O
        self.is_ai_turn = is_ai_turn_first
        self.winning_combinations = [0x1C0, 0x38, 0x7, 0x124, 0x92, 0x49, 0x111, 0x54]
        self.draw_combination = 0x1FF

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

    def push(self, location: list) -> None:  # Takes coords as [row, column] i.e. [x, y]
        location = list(map(int, location))
        x, y = location[0], location[1]
        if not self.is_valid_move(location):
            raise InvalidMoveError()
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

    def get_valid_moves(self) -> list:
        """
        returns all valid moves as list of lists
        """

        possible_moves = [[x, y] for y in range(3) for x in range(3)]
        possible_moves = list(map(self.is_valid_move, possible_moves))
        valid_moves = [move for move in possible_moves if move is not None]
        return valid_moves

    def minimax(self, board, alpha, beta):
        state = board.check_winner()
        if state == (1, 0):
            return -10
        elif state == (0, 1):
            return 10
        elif state == (1, 1):
            return 0
        if board.is_ai_turn:
            best_max = -10000
            possible_moves = board.get_valid_moves()
            for move in possible_moves:
                score = board.minimax(board.push_move_to_copy(move), alpha, beta)
                best_max = max(best_max, score)
                alpha = max(alpha, score)
                if beta <= alpha:
                    break
            return best_max
        else:
            best_min = 10000
            possible_moves = board.get_valid_moves()
            for move in possible_moves:
                score = board.minimax(board.push_move_to_copy(move), alpha, beta)
                best_min = min(best_min, score)
                beta = min(beta, score)
                if beta <= alpha:
                    break
            return best_min

    def get_best_move(self):
        possible_moves = self.get_valid_moves()
        best = -10000
        best_move = []
        time_started = time.time()
        for move in possible_moves:
            if time.time() - 10 >= time_started:
                break
            score = self.minimax(self.push_move_to_copy(move), -10000, 10000)
            print(move, score)
            if score > best:
                best_move = move
                best = score
        return best_move

    def get_bitboard(self, array: np.array) -> int:
        new_list = np.reshape(array, (3**2,)).tolist()
        new_list = map(int, new_list)
        new_list = list(map(str, new_list))
        bitboard = int("".join(new_list), 2)
        return bitboard

    def get_board_array(self) -> np.array:  # human piece = 1, ai = -1
        return np.add(self.human_board, self.ai_board*-1)

    def __str__(self):  # returns encoded board
        #board representation for testing.
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
            """

    def deepcopy(self):
        new_object = TicTacToeGame(self.sfr)
        new_object.is_ai_turn = self.is_ai_turn
        new_object.human_board = self.human_board.copy()
        new_object.ai_board = self.ai_board.copy()
        return new_object







class SFR:
    def __init__(self):
        self.MINIMAX_TIMEOUT = 10
game = TicTacToeGame(SFR())
while True:
    if game.check_winner() == (1, 0):
        print(game)
        print("Human Wins")
        break
    elif game.check_winner() == (0, 1):
        print(game)
        print("AI Wins")
        break
    elif game.check_winner() == (1, 1):
        print(game)
        print("Draw")
        break
    if game.is_ai_turn:
        move = game.get_best_move()
        game.push(move)
    else:
        while True:
            x = int(input("Move Row "))
            y = int(input("Move Col "))
            try:
                game.push([x, y])
                break
            except InvalidMoveError:
                pass
    print(game)


