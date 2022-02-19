import time
from math import sqrt
import numpy as np
import random
from MainControlLoop.Mode.outreach.ultimate_tictactoe.MCTS.node import Node
#from MainControlLoop.Mode.outreach.ultimate_tictactoe.ultimate_game import UltimateTicTacToeGame
import copy


class MCTSSearch:
    def __init__(self, sfr, initial_state):
        self.sfr = sfr
        self.root = Node(initial_state, None)

        self.start_time = time.time()

    def resources_left(self):
        if self.root.times_visited > 400:
            return False
        if time.time() - 10 > self.start_time:#self.sfr.vars.OUTREACH_MAX_CALCULATION_TIME > self.start_time:
            return False
        return True

    def get_best_move(self):
        while self.resources_left():
            leaf = self.traverse(self.root)
            simulation_result = self.rollout(leaf)
            self.backpropogate(leaf, simulation_result)

        return self.best_child_move(self.root)

    def traverse(self, node):
        while not len(node.children) == 0:
            node = self.best_uct(node)

        if len(node.board_state.get_valid_moves()) == 0:
            return node
        else:
            node.children = [Node(node.board_state.push_move_to_copy(move), node)
                             for move in node.board_state.get_valid_moves()]
            return random.choice(node.children)

    def rollout(self, node):
        board_state = copy.deepcopy(node.board_state)
        while True:
            legal_moves = board_state.get_valid_moves()
            if len(legal_moves) == 0:
                break
            board_state.push(random.choice(legal_moves))

        if outcome := board_state.check_winner() == -1:
            return 0
        return outcome

    def backpropogate(self, leaf, simulation_result):
        node = leaf
        while node is not None:
            node.value += simulation_result
            node.times_visited += 1
            node = node.parent

    def best_uct(self, node):
        def _uct(child_node):
            return (child_node.value/child_node.times_visited) \
                   + (sqrt(2)*sqrt(np.log(node.times_visited)/child_node.times_visited))

        children_list = [_uct(i) for i in node.children]
        return node.children[children_list.index(max(children_list))]

    def best_child_move(self, node):
        def _get_visits(child_node):
            return child_node.times_visited

        children_list = [_get_visits(i) for i in node.children]
        max_index = children_list.index(max(children_list))
        legal_moves = node.board_state.get_valid_moves()
        return legal_moves[max_index]
