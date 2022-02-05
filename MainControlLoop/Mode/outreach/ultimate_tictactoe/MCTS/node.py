class Node:
    def __init__(self, board_state, parent):
        self.board_state = board_state
        self.parent = parent
        self.children = []

        self.times_visited = 0
        self.wins = 0

    def add_children(self, children: list):
        self.children.extend(children)
