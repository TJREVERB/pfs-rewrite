import numpy as np
import copy
import random


class TicTacToe:
    """
    TicTacToe game (used in Ultimate TicTacToe and MCTS)
    """
    winning_combinations = [0x1C0, 0x38, 0x7, 0x124, 0x92, 0x49, 0x111, 0x54]  # Hardcoded winning combinations
    draw_combination = 0x1FF  # Only possible draw combination in tictactoe

    def __init__(self, is_ai_turn: bool):
        """
        Create a new game
        :param is_ai_turn: whether we're starting this game as AI or human
        :type is_ai_turn: bool
        """
        self.is_ai_turn = is_ai_turn  # Whether this is currently the ai turn (used for testing)
        # Initialize boards as 0
        self.human_board = 0
        self.ai_board = 0

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
        for i in range(9):  # Iterate over bits
            if self.human_board >> i & 1:
                encoded_string += "x"
            elif self.ai_board >> i & 1:
                encoded_string += "o"
            else:
                encoded_string += "-"
        return encoded_string

    def board_string(self, row: int):  # for testing, human only
        """
        Returns printable version of board row
        :param row: row to convert to string
        :type row: int
        """
        row = row % 3
        string = ""
        for col in range(3):
            if self.human_board >> row * 3 + col:  # if human piece
                string += 'x'
            elif self.ai_board >> row * 3 + col:  # if ai piece
                string += 'o'
            else:  # if no piece
                string += '.'
            string += " | "
        return string.strip()

    def set_game(self, board_string: str):
        """
        Loads board from string
        :param board_string: string to load from
        :type board_string: str
        """
        for i in range(9):
            if board_string[i] == "x":
                self.human_board |= 1 << i
            elif board_string[i] == "o":
                self.ai_board |= 1 << i

    def check_winner(self) -> int:
        """
        Checks the winner of the current board
        :return: 0 = human win, 1 = draw, 2 = ai win, -1 = game incomplete
        :rtype: int
        """
        return self.check_winner_board(self.human_board, self.ai_board)

    @staticmethod
    def check_winner_board(human_board: int, ai_board: int) -> int:
        """
        Checks the winner of the given boards
        :param human_board: human board state
        :type human_board: int
        :param ai_board: ai board state
        :type ai_board: int
        :return: 0 = human win, 1 = draw, 2 = ai win, -1 = game incomplete
        :rtype: int
        """
        for i in TicTacToe.winning_combinations:
            if human_board & i == i:
                return 0
            elif ai_board & i == i:
                return 2
        if human_board | ai_board == TicTacToe.draw_combination:
            return 1
        return -1

    def switch_turn(self):
        """
        Switches current player (ai to human and vice versa)
        """
        self.is_ai_turn = not self.is_ai_turn

    def is_valid_move(self, location: int) -> bool:
        """
        Check if a given move is valid
        :param location: move to test
        :type location: int
        :return: whether this move is valid
        :rtype: bool (0 or 1)
        """
        return bool(~(self.human_board | self.ai_board) >> location & 1)

    def get_valid_moves(self) -> [int]:
        """
        Get all valid moves on this board
        :return: list of integer moves
        :rtype: list
        """
        return [1 << i for i in range(9) if self.is_valid_move(i)]

    def push(self, move: int) -> None:  # Takes integer move
        """
        Update board state with a given move
        :param move: move to update with
        :type move: int
        """
        if self.is_ai_turn:
            self.ai_board += move
        else:
            self.human_board += move
        self.switch_turn()

    def push_move_to_copy(self, move: int):
        """
        Copies game object, applies move, and returns
        :param move: move to make
        :type move: int
        :return: new game object
        :rtype: TicTacToe
        """
        new_board = copy.deepcopy(self)
        new_board.push(move)
        return new_board

    @staticmethod
    def random() -> str:
        """
        Generate a random board (TESTING ONLY)
        """
        board = TicTacToe(True)
        for _ in range(4):
            board.push(random.choice(board.get_valid_moves()))
            if random.random() < 1 / 4:
                break
        return str(board)
