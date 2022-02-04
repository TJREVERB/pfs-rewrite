import random

class JokesGame:
    def __init__(self, sfr, game_id):
        self.sfr = sfr
        self.game_id = game_id
        self.type = "Dad Joke"

    def get_joke(self):
        with open("MainControlLoop/Mode/outreach/jokes/jokes.txt", "f") as f:
            txt = f.read()
            lines = list(map(str, txt.split()))
            return random.choice(lines)

    def get_best_move(self):  # so that it works with outreach.py
        return self.get_joke()

    def push(self):  # so that it works with outreach.py
        pass
