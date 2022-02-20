class Node:
    def __init__(self, board_state, parent):
        self.board_state = board_state
        self.parent = parent
        self.children = []

        self.times_visited = 1
        self.value = 1
