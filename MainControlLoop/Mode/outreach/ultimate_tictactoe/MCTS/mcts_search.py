import time
from math import sqrt
import numpy as np
import random
from MainControlLoop.Mode.outreach.ultimate_tictactoe.MCTS.node import Node


class MCTSSearch:
    def __init__(self, sfr, initial_state):
        self.sfr = sfr
        self.root = Node(initial_state, None)

        self.start_time = time.time()

    def resources_left(self):
        if self.root.times_visited > 2000:
            return False
        if time.time() - self.sfr.vars.OUTREACH_MAX_CALCULATION_TIME > self.start_time:
            return False
        else:
            return True

    def get_best_move(self):
        while self.resources_left():
            leaf = self.traverse(self.root)
            simulation_result = self.rollout(leaf)
            self.backpropogate(leaf, simulation_result)

        e = self.best_child_move(self.root)
        print(e)
        return e
    def traverse(self, node):
        while not len(node.children) == 0:
            node = self.best_uct(node)

    def rollout(self, node):
        board_state = node.board_state.deepcopy()
        while True:
            legal_moves = board_state.get_valid_moves()
            if len(legal_moves) == 0:
                break
            board_state.push(random.choice(legal_moves))

        outcome = board_state.check_winner()
        if outcome == (0, 1):  # ai won
            return 2
        elif outcome == (1, 1):  # draw
            return 1
        else:
            return 0

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

        children_list = list(map(_uct, node.children))
        return node.children[children_list.index(max(children_list))]

    def best_child_move(self, node):
        def _get_visits(child_node):
            return child_node.times_visited

        children_list = list(map(_get_visits, node.children))
        max_index = children_list.index(max(children_list))
        legal_moves = node.board_state.get_valid_moves()
        return legal_moves[max_index]








