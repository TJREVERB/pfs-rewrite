import numpy as np
from MainControlLoop.Mode.outreach.ultimate_tictactoe.MCTS.mcts_search import MCTSSearch
from MainControlLoop.Mode.outreach.ultimate_tictactoe.tictactoe3x3 import TicTacToe
import random
import copy


class UltimateTicTacToeGame:
    """
    Wrapper of TicTacToe for Ultimate TicTacToe
    """
    def __init__(self, sfr, game_id: int):
        """
        Create a new game
        :param sfr: sfr object
        :type sfr: lib.registry.StateFieldRegistry
        :param game_id: unique identifier for this game
        :type game_id: int
        """
        self.sfr = sfr
        self.game_id = game_id
        self.board = [TicTacToe(True).set_game("---------") for _ in range(9)]  # must call set_game
        self.previous_move = None
        self.is_ai_turn = True

    def __str__(self):
        """
        board is encoded as the nine 3x3 tictactoe boards, flattened then run through 3x3 string encoder
        the 3x3 board strings are seperated as commas
        current turn is encoded at the end by h or a, h is human turn next, a is ai turn next
        the previous move is
        i.e. x-ooox--x,o-xxx-oo-, ...(continues),---o-x-o-h
        'UltimateTicTacToe' is then inserted to the front, and turn char is appended at the back, either
        """
        board_string = ",".join([str(board) for board in self.board])  # TODO: FIX
        if self.previous_move is None:
            board_string += ",-1,-1,-1,"  # set as -1 if no previous move
        else:
            for axis in self.previous_move:
                board_string += f",{axis}"
            board_string += ","
        if self.is_ai_turn:
            board_string += "a"
        else:
            board_string += "h"

        return f"Ultimate;{board_string};{self.game_id}"

    def print_board(self):
        """
        Test method, prints board for human
        """
        string = ""
        for row in range(9):
            if row < 3:
                board_index = 0
            elif row < 6:
                board_index = 3
            else:
                board_index = 6
            for board in range(board_index, board_index + 3):
                string += "|"
                string += self.board[board].board_string(row)
                string += "   "
            string += "     "
            string += "\n"
            if row == 2 or row == 5:
                string += "\n\n"
        print(string)

    def set_game(self, board_string: str):
        """
        Load game from given board string
        :param board_string: string to load from
        :type board_string: str
        """
        self.board = [TicTacToe(self.is_ai_turn).set_game(board) for board in board_string.split(",")]

    def get_valid_moves(self) -> [int]:
        """
        Get a list of all valid moves (list of integers)
        :return: Moves represented as bits [xxxxxxxxx](3x3 board location)[xxxxxxxxx](location on board)
        :rtype: list
        """
        if self.previous_move is None:  # If this is the first move
            return [(1 << i // 9) + (1 << i % 9) for i in range(81)]  # Return all possible moves
        section_index = np.log2(self.previous_move & ~(~0 << 9))  # Set 3x3 board index to last move within inner board
        if self.board[section_index].check_winner() == -1:  # If the board we were sent to is incomplete
            # Return all legal moves + first 9 bits saying we're on this board
            return [(1 << section_index) + i for i in self.board[section_index].get_valid_moves()]
        else:  # If the board we were sent to is already complete
            move_list = []  # Initialize empty list of possible moves
            for idx, board in enumerate(self.board):  # Iterate over all boards
                if board.check_winner() == -1:  # If this board is incomplete
                    # Extend possible moves list with valid moves of this board
                    # + first 9 bits saying we're on this board
                    move_list.extend([(1 << idx + 9) + i for i in board.get_valid_moves()])
            return move_list  # Return complete move_list after checking all boards

    def push(self, move: int):
        """
        Push a move to this game object (update board)
        :param move: Moves represented as bits [xxxxxxxxx](3x3 board location)[xxxxxxxxx](location on board)
        :type move: int
        """
        self.board[section := int(np.log2(move >> 9), 2)].push(move & ~(~0 << 9))
        for i, board in enumerate(self.board):
            if i != section:
                board.switch_turn()
        self.previous_move = move

    def push_move_to_copy(self, move: int):
        """
        Push a move to a new game object
        :param move: Moves represented as bits [xxxxxxxxx](3x3 board location)[xxxxxxxxx](location on board)
        :type move: int
        :return: new UltimateTicTacToe game object
        :rtype: UltimateTicTacToeGame
        """
        game = copy.deepcopy(self)
        game.push(move)
        return game

    def check_winner(self) -> int:
        """
        Checks for a winner of the current game
        :return: 0 = human win, 1 = draw, 2 = ai win, -1 = game incomplete
        :rtype: int
        """
        human_board, ai_board = 0, 0  # Initialize bitboards
        game_complete = True  # Initialize as true because it's easier to check if incomplete than complete
        for i in range(9):  # Iterate over boards
            if winner := self.board[i].check_winner() == 0:  # If the human won this board
                human_board += 1 << i  # Toggle this bit in human_board
            elif winner == 2:  # If the ai won this board
                ai_board += 1 << i  # Toggle this bit in the ai_board
            elif winner == -1:  # If this board is incomplete
                game_complete = False  # Update game_complete
        # If check_winner thinks the game is incomplete,
        # Either the game is actually complete and there are too many draws to detect a winner
        # Or there are still some possible moves which could theoretically result in a victory
        if (result := TicTacToe.check_winner_board(human_board, ai_board)) == -1:
            if game_complete:  # If the game is complete, return a draw
                return 1
            return result  # Otherwise return that the game is in fact incomplete
        return result  # If check_winner detected a game result, return the game result

    def get_best_move(self):
        return MCTSSearch(self.sfr, self).get_best_move()

    def random(self) -> str:
        """
        Simulate an entirely random game, from start to finish
        :return: board string representation
        :rtype: str
        """
        while True:
            board = UltimateTicTacToeGame(self.sfr, self.game_id)
            for _ in range(random.randint(0, 81)):
                move = random.choice(board.get_valid_moves())
                board.push(move)
                if board.check_winner() != -1:
                    break
            if board.check_winner() == -1:
                break
        return str(board).split(";")[1]

    def generate_random_draw(self):
        """
        Simulate a draw (NOT WORKING) TODO: FIX
        """
        board = UltimateTicTacToeGame(self.sfr, 5)
        string = TicTacToe(True).random()

        board.board = [TicTacToe(True).set_game(string) for i in range(9)]
        if board.check_winner() == (1, 0):
            return True


if __name__ == "__main__":
    e = UltimateTicTacToeGame(5, 5)
    # for _ in range(10000):
    #    if e.generate_random_draw():
    #        continue
    #    else:
    #        print("ERROR")

    e.print_board()
    ai_move = e.get_best_move()
    print(ai_move)
    e.push(ai_move)
    e.print_board()
    sec = input("Input section: ")
    row = input("Input row: ")
    col = input("Input col: ")
    e.print_board()
    while e.check_winner() == (0, 0):
        e.push(list(map(int, [sec, row, col])))
        e.print_board()
        ai_move = e.get_best_move()
        e.push(ai_move)
        print(ai_move)
        e.print_board()
        while True:
            print("Section: " + str(e.get_valid_moves()[0][0]))
            print(e.get_valid_moves())
            sec = int(input("Input section: "))
            row = int(input("Input row: "))
            col = int(input("Input col: "))
            if [sec, row, col] in e.get_valid_moves():
                break
            else:
                print("INVALID MOVE")
    e.print_board()
    if e.check_winner() == (1, 0):
        print("HUMAN WON")
    elif e.check_winner() == (0, 1):
        print("AI WON L")
    else:
        print("DRAW")

# e = UltimateTicTacToeGame(5, 5)
# e.set_game(f"Ultimate;o-xx-x--x,x--o-o-o-,o-o-----x,o--------,xxx-----o,ox-------,--------o,-x--o--x-,-o--o-xox")
# e.set_game(f"Ultimate;o-xx-x--x,x--o-o-o-,o-o-----x,o--------,xxx-----o,ox-------,--------o,-x--o--x-,-x--x-oxo")
# print(e.board)
# print(e.check_winner())
# e.push([2, 0, 1])
# print(str(e))
