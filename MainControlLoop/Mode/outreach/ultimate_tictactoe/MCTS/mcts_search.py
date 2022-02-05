import time
from math import sqrt
import numpy as np
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

    def traverse(self, node):
        while not len(node.children) == 0:
            node = self.best_uct(node)


    def best_uct(self, node):
        def _uct(child_node):
            return (child_node.wins/child_node.times_visited) \
                   + (sqrt(2)*sqrt(np.log(node.times_visited)/child_node.times_visited))

        children_list = list(map(_uct, node.children))
        return node.children[children_list.index(max(children_list))]