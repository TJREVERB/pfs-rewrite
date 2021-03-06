import time
from math import sqrt
import numpy as np
import random
import copy
from MainControlLoop.Mode.outreach.ultimate_tictactoe.MCTS.node import Node
from lib.exceptions import wrap_errors, LogicalError


class MCTSSearch:
    @wrap_errors(LogicalError)
    def __init__(self, sfr, initial_state):
        self.sfr = sfr
        self.root = Node(initial_state, None)

        self.start_time = time.time()

    @wrap_errors(LogicalError)
    def resources_left(self):
        if self.root.times_visited > 400:
            return False
        if time.time() - self.sfr.vars.OUTREACH_MAX_CALCULATION_TIME > self.start_time:
            return False
        else:
            return True

    @wrap_errors(LogicalError)
    def get_best_move(self):
        while self.resources_left():
            leaf = self.traverse(self.root)
            simulation_result = self.rollout(leaf)
            self.backpropogate(leaf, simulation_result)

        return self.best_child_move(self.root)

    @wrap_errors(LogicalError)
    def traverse(self, node):
        while not len(node.children) == 0:
            node = self.best_uct(node)

        if len(node.board_state.get_valid_moves()) == 0:
            return node
        else:
            node.children = [Node(node.board_state.push_move_to_copy(move), node)
                             for move in node.board_state.get_valid_moves()]
            return random.choice(node.children)

    @wrap_errors(LogicalError)
    def rollout(self, node):
        board_state = copy.deepcopy(node.board_state)
        while True:
            legal_moves = board_state.get_valid_moves()
            if len(legal_moves) == 0:
                break
            board_state.push(random.choice(legal_moves))

        outcomes = {
            (0, 1): 2,
            (1, 1): 1,
            (1, 0): 0,
        }
        return outcomes[board_state.check_winner()]

    @wrap_errors(LogicalError)
    def backpropogate(self, leaf, simulation_result):
        node = leaf
        while node is not None:
            node.value += simulation_result
            node.times_visited += 1
            node = node.parent

    @wrap_errors(LogicalError)
    def best_uct(self, node):
        def _uct(child_node):
            return (child_node.value/child_node.times_visited) \
                   + (sqrt(2)*sqrt(np.log(node.times_visited)/child_node.times_visited))

        children_list = list(map(_uct, node.children))
        return node.children[children_list.index(max(children_list))]

    @wrap_errors(LogicalError)
    def best_child_move(self, node):
        def _get_visits(child_node):
            return child_node.times_visited

        children_list = list(map(_get_visits, node.children))
        max_index = children_list.index(max(children_list))
        legal_moves = node.board_state.get_valid_moves()
        return legal_moves[max_index]








