import pickle
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.gamer_mode.tictactoe.tictactoe_game import TicTacToeGame


class TicTacToe(Mode):
    def __init__(self, sfr):
        super().__init__(sfr)
        self.ai_move_first = False
        self.next_human_move = None
        self.sfr = sfr
        self.board_obj = None
        self.conditions = {
            "Low Battery": False
        }

    def __str__(self):
        return "Gomoku"

    def start(self):
        super().start([self.sfr.vars.PRIMARY_RADIO])
        self.load_save()

    def execute_cycle(self) -> None:
        if self.board_obj.check_winner() == (1, 0):
            self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit("Human is Winner, Switched to Gamer Mode")
            self.board_obj = TicTacToeGame(is_ai_turn_first=False)
            self.terminate_mode()
            self.sfr.MODE = self.sfr.modes_list["Gamer"](self.sfr)
            self.sfr.MODE.start()

        elif self.board_obj.check_winner() == (0, 1):
            self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit("AI is Winner (Big L), Switched to Gamer Mode")
            self.board_obj = TicTacToeGame(is_ai_turn_first=False)
            self.terminate_mode()
            self.sfr.MODE = self.sfr.modes_list["Gamer"](self.sfr)
            self.sfr.MODE.start()
        elif self.board_obj.check_winner() == (1, 1):
            self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit("Game is Draw, Switched to Gamer Mode")
            self.board_obj = TicTacToeGame(is_ai_turn_first=False)
            self.terminate_mode()
            self.sfr.MODE = self.sfr.modes_list["Gamer"](self.sfr)
            self.sfr.MODE.start()
        else:
            if self.board_obj.is_ai_turn:
                ai_move = self.board_obj.get_best_move()
                self.board_obj.push(ai_move)
                self.transmit_board()
            elif not self.board_obj.is_ai_turn and self.next_human_move is not None:  # if there is human move in buffer
                self.board_obj.push(self.next_human_move)  # push move
                ai_move = self.board_obj.get_best_move()  # query ai to get move
                self.board_obj.push(ai_move)
                self.next_human_move = None
                self.transmit_board()
            else:  # human turn but human hasnt moved
                # TODO: figure out how to transmit reminder to move to ground on a clock
                pass

    def transmit_board(self):  # str representation of board


    def suggested_mode(self):
        super().suggested_mode()
        if self.sfr.vars.BATTERY_CAPACITY_INT < self.sfr.vars.LOWER_THRESHOLD:
            return self.sfr.modes_list["Charging"](self.sfr, self)
        else:
            return self

    def erase_save(self):
        with open("tictactoe_file.pkl", "wb") as f:
            pass

    def load_save(self) -> None:
        with open("tictactoe_file.pkl", "rb") as f:
            self.board_obj = pickle.load(f)

    def terminate_mode(self):
        with open("tictactoe_file.pkl", "wb") as f:
            pickle.dump(self.board_obj, f)
        if self.board_obj.check_winner() != (0, 0):
            self.erase_save()

