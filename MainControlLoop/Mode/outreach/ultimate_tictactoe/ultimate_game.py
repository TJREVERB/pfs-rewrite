import numpy as np
from MainControlLoop.Mode.outreach.ultimate_tictactoe.MCTS.mcts_search import MCTSSearch
from MainControlLoop.Mode.outreach.ultimate_tictactoe.tictactoe3x3 import TicTacToe
import random
import copy
from lib.exceptions import wrap_errors, LogicalError


class UltimateTicTacToeGame:
    @wrap_errors(LogicalError)
    def __init__(self, sfr, game_id):
        self.sfr = sfr
        self.game_id = game_id
        self.board = [TicTacToe(True).set_game("---------") for _ in range(9)]  # must call set_game
        self.previous_move = None
        self.is_ai_turn = True
        self.winning_combinations = [0x1C0, 0x38, 0x7, 0x124, 0x92, 0x49, 0x111, 0x54]
        self.draw_combination = 0x1FF

    @wrap_errors(LogicalError)
    def __str__(self):
        """
        board is encoded as the nine 3x3 tictactoe boards, flattened then run through 3x3 string encoder
        the 3x3 board strings are seperated as commas
        the previous move is appended to the end
        current turn is encoded at the end by h or a, h is human turn next, a is ai turn next

        previous move = [0, 1, 2]. If previous move is None, format is (board_string),-1,-1,-1,a
        is_ai_turn = True
        i.e. x-ooox--x,o-xxx-oo-, ...(continues),---o-x-o-,0,1,2,a
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

    @wrap_errors(LogicalError)
    def print_board(self):  # testing, prints board for human
        string = ""
        for row in range(9):
            if row < 3:
                board_index = 0
            elif row < 6:
                board_index = 3
            else:
                board_index = 6
            for board in range(board_index, board_index+3):
                string += "|"
                string += self.board[board].board_string(row)
                string += "   "
            string += "     "
            string += "\n"
            if row == 2 or row == 5:
                string += "\n\n"
        print(string)

    @wrap_errors(LogicalError)
    def set_game(self, board_string):
        encoded_list = board_string.split(",")
        self.board = [TicTacToe(self.is_ai_turn).set_game(board) for board in encoded_list[:9]]
        self.previous_move = list(map(int, encoded_list[9:12]))
        if self.previous_move[0] == -1:
            self.previous_move = None
        if encoded_list[12] == "a":
            self.is_ai_turn = True
        else:
            self.is_ai_turn = False

    @wrap_errors(LogicalError)
    def get_valid_moves(self):
        """
        Moves represented as [x, y, z], x: 3x3 board, y: x row on 3x3 board, z: y row on 3x3 board
        """
        move_list = []

        if self.previous_move is None:
            for i, board in enumerate(self.board):  # Generate legal moves
                if board.check_winner() == (0, 0):
                    legal_moves = []
                    for move in board.get_valid_moves():
                        move.insert(0, i)
                        legal_moves.append(move)
                    move_list.extend(legal_moves)
            return move_list
        section_index = self.previous_move[1]*3 + self.previous_move[2]
        board = self.board[section_index]
        if board.check_winner() == (0, 0):
            legal_moves = []
            for move in board.get_valid_moves():
                move.insert(0, section_index)
                legal_moves.append(move)
            move_list.extend(legal_moves)
        else:
            for i, board in enumerate(self.board):
                if board.check_winner() == (0, 0):
                    legal_moves = []
                    for move in board.get_valid_moves():
                        move.insert(0, i)
                        legal_moves.append(move)
                    move_list.extend(legal_moves)
        return move_list

    @wrap_errors(LogicalError)
    def push(self, location: list):
        """
        Moves represented as [x, y, z], x: 3x3 board, y: x row on 3x3 board, z: y row on 3x3 board
        """
        self.board[location[0]].push([location[1], location[2]])
        for i, board in enumerate(self.board):
            if not i == location[0]:
                board.switch_turn()
        self.previous_move = location

    @wrap_errors(LogicalError)
    def push_move_to_copy(self, location: list):
        """
        pushes a move to new game object
        :param location:
        :return: new UltimateTicTacToe game object
        """
        game = self.deepcopy()
        game.push(location)
        return game

    @wrap_errors(LogicalError)
    def deepcopy(self):
        return copy.deepcopy(self)

    @wrap_errors(LogicalError)
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

        # 1 for result (1,0) -> human won
        human_board = [1 if board.check_winner() == (1, 0) else 0 for board in self.board]
        ai_board = [1 if board.check_winner() == (0, 1) else 0 for board in self.board]
        # 1 for result (0,1) -> ai won
        # 0 for draw bc doesn't affect winner, check draw later
        check_result = _check(self.get_bitboard(np.array(human_board)), self.get_bitboard(np.array(ai_board)))
        if check_result == (0, 0):  # if no one has won, must check draw
            for board in self.board:
                if board.check_winner() == (0, 0):
                    return 0, 0
            return 1, 1
        else:
            return check_result

    @wrap_errors(LogicalError)
    def get_bitboard(self, array: np.array) -> int:
        new_list = list(np.reshape(array, (9,)))
        new_list = map(int, new_list)
        new_list = list(map(str, new_list))
        bitboard = int("".join(new_list), 2)
        return bitboard

    @wrap_errors(LogicalError)
    def get_best_move(self):
        search = MCTSSearch(self.sfr, self)
        return search.get_best_move()

    @wrap_errors(LogicalError)
    def random(self):
        while True:
            board = UltimateTicTacToeGame(self.sfr, self.game_id)
            for _ in range(random.randint(0, 81)):
                move = list(board.get_valid_moves())[random.randint(0, len(list(board.get_valid_moves())) - 1)]
                board.push(move)
                if not board.check_winner() == (0, 0):
                    break
            if not board.check_winner() == (0, 0):
                continue
            else:
                return str(board).split(";")[1]

    @wrap_errors(LogicalError)
    def generate_random_draw(self):
        board = UltimateTicTacToeGame(self.sfr, 5)
        string = TicTacToe(True).random()

        board.board = [TicTacToe(True).set_game(string) for i in range(9)]
        if (board.check_winner() == (1, 0)):
            return True


if __name__ == "__main__":
    e = UltimateTicTacToeGame(5, 5)
    #for _ in range(10000):
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

#e = UltimateTicTacToeGame(5, 5)
#e.set_game(f"Ultimate;o-xx-x--x,x--o-o-o-,o-o-----x,o--------,xxx-----o,ox-------,--------o,-x--o--x-,-o--o-xox")
#e.set_game(f"Ultimate;o-xx-x--x,x--o-o-o-,o-o-----x,o--------,xxx-----o,ox-------,--------o,-x--o--x-,-x--x-oxo")
#print(e.board)
#print(e.check_winner())
#e.push([2, 0, 1])
#print(str(e))








