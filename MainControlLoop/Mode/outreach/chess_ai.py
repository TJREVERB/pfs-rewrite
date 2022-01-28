import chess
import copy
import time

def play(board, ponder_time):
    return get_best_move(board, ponder_time)

def get_valid_moves(board) -> list:
    return list(board.legal_moves)

def check_winner(board) -> tuple:
    """
    chess.Board.outcome(board) will return an outcome object if game is over,
    (whether draw, or win)
    to find the winner, you first query chess.Board.outcome(board)
    if it returns None and not an outcome object, the game is not over
    else if it returns an outcome object it is over, with the following return states
    (refers to outcome object as the object returned from chess.Board.outcome(board))
    outcome.winner = None: Draw
    outcome.winner = True: white win
    outcome.winner = False: black win
    """
    if chess.Board.outcome(board) is None:  # no winner and no draw
        return 0, 0
    elif chess.Board.outcome(board).winner:  # if this is true, white won
        return 1, 0
    elif not chess.Board.outcome(board).winner:  # if false, black won
        return 0, 1
    else:  # draw
        return 1, 1

def push_move_to_copy(board, move: chess.Move) -> chess.Board:
    new_board = copy.deepcopy(board)
    new_board.push(move)
    return new_board

def static_evaluation(board, is_maximizing_player: bool) -> int:
    fen = board.fen()
    white_total = 0
    black_total = 0
    white_total += fen.count("P")
    white_total += fen.count("B")*3
    white_total += fen.count("N")*3
    white_total += fen.count("R")*5
    white_total += fen.count("Q")*8
    white_total += fen.count("K")*3
    black_total += fen.count("P")
    black_total += fen.count("B") * 3
    black_total += fen.count("N") * 3
    black_total += fen.count("R") * 5
    black_total += fen.count("Q") * 8
    black_total += fen.count("K") * 3
    if is_maximizing_player:
        ai_turn = board.turn  # ai_turn: true = white, false = black
    elif not is_maximizing_player:
        ai_turn = not board.turn
    else:
        ai_turn = not board.turn

    if ai_turn:  # if ai is white
        return white_total-black_total
    else:
        return black_total-white_total

def get_best_move(board, ponder_time):
    print(board)
    legal_moves = get_valid_moves(board)
    best_score = -9999
    best_move = None  #best_move is Move object, not uci string
    time_started = time.time()
    for move in legal_moves:
        if time.time() - ponder_time >= time_started:
            if best_move is None:
                best_move = legal_moves[0]
            break
        score = minimax(push_move_to_copy(board, move), -10000, 10000, False, 0)
        if score > best_score:
            best_score = score
            best_move = move
    return best_move


def minimax(board, alpha, beta, is_maximizing_player: bool, depth: int):
    state = check_winner(board)
    if state == (1, 0):
        return -1000
    elif state == (0, 1):
        return 1000
    elif state == (1, 1):
        return 0
    if depth >= 10:  # TODO: figure out dynamic way to set depth
        return static_evaluation(board, is_maximizing_player)

    if is_maximizing_player:
        best_score = -9999
        legal_moves = get_valid_moves(board)
        for move in legal_moves:
            score = minimax(push_move_to_copy(board, move), alpha, beta, not is_maximizing_player, depth+1)
            best_score = max(best_score, score)
            alpha = max(alpha, score)
            if beta <= alpha:
                break
        return best_score
    elif not is_maximizing_player:
        best_score = 9999
        legal_moves = get_valid_moves(board)
        for move in legal_moves:
            score = minimax(push_move_to_copy(board, move), alpha, beta, not is_maximizing_player, depth+1)
            best_score = min(best_score, score)
            beta = min(beta, score)
            if beta <= alpha:
                break
        return best_score





