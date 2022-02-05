import time
from math import sqrt
import numpy as np
import random
from MainControlLoop.Mode.outreach.ultimate_tictactoe.MCTS.node import Node


class MCTSSearch:
    def __init__(self, initial_state):
        self.root = Node(initial_state, None)

        self.start_time = time.time()

    def resources_left(self):
        if time.time() - 30 > self.start_time:
            return False
        else:
            return True

    def get_best_move(self):
        while self.resources_left():
            leaf = self.traverse(self.root)
            simulation_result = self.rollout(leaf)
            self.backpropogate(leaf, simulation_result)

        return self.best_child(self.root)

    def traverse(self, node):
        while not len(node.children) == 0:
            node = self.best_uct(node)

        legal_moves = node.board_state.get_valid_moves()
        if len(legal_moves) == 0:  # already winner
            return node

        node.children = [Node(node.board_state.push_move_to_copy(move), node)
                         for move in legal_moves]

        return random.choice(node.children)

    def rollout(self, node):
        board_state = node.board_state.deepcopy()
        while board_state.check_winner() == (0, 0):
            legal_moves = board_state.get_valid_moves()
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
        while node.parent is not None:
            node.value += simulation_result
            node.times_visited += 1
            node = node.parent

    def best_uct(self, node):
        def _uct(child_node):
            return (child_node.wins/child_node.times_visited) \
                   + (sqrt(2)*sqrt(np.log(node.times_visited)/child_node.times_visited))

        children_list = list(map(_uct, node.children))
        return node.children[children_list.index(max(children_list))]

    def best_child(self, node):
        def _get_visits(child_node):
            return child_node.times_visited

        visited_list = list(map(_get_visits, node.children))
        return node[visited_list.index(max(visited_list))]