import pickle

from Drivers.transmission_packet import TransmissionPacket
from MainControlLoop.Mode.mode import Mode
from MainControlLoop.Mode.gamer_mode.tictactoe.tictactoe_game import TicTacToeGame


class TicTacToe(Mode):
    def __init__(self, sfr):
        super().__init__(sfr)
        self.next_human_move = None
        self.sfr = sfr
        self.board_obj = None
        self.conditions = {
            "Low Battery": False
        }

    def __str__(self):
        return "TicTacToe"

    def start(self):
        super().start([self.sfr.vars.PRIMARY_RADIO])
        self.load_save()

    def execute_cycle(self) -> None:
        if self.board_obj.check_winner() == (1, 0):
            self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit("Human is Winner, Switched to Gamer Mode")
            self.board_obj = TicTacToeGame(is_ai_turn_first=False)
            self.switch_to_gamer_mode()

        elif self.board_obj.check_winner() == (0, 1):
            self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit("AI is Winner (Big L), Switched to Gamer Mode")
            self.board_obj = TicTacToeGame(is_ai_turn_first=False)
            self.switch_to_gamer_mode()

        elif self.board_obj.check_winner() == (1, 1):
            self.sfr.devices[self.sfr.vars.PRIMARY_RADIO].transmit("Game is Draw, Switched to Gamer Mode")
            self.board_obj = TicTacToeGame(is_ai_turn_first=False)
            self.switch_to_gamer_mode()

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

    def switch_to_gamer_mode(self):
        self.terminate_mode()
        self.sfr.MODE = self.sfr.modes_list["Gamer"](self.sfr)
        self.sfr.MODE.start()

    def transmit_board(self):  # str representation of board
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
        """
        encoded_board = str(self.board_obj)
        packet = TransmissionPacket("ZTB", args=[], msn=0)
        packet.return_code = "GME"
        packet.return_data = [encoded_board]
        self.sfr.command_executor.ZTB(packet)

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

