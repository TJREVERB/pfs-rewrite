import random


class JokesGame:
    def __init__(self, sfr, game_id):
        self.sfr = sfr
        self.game_id = game_id
        self.joke = "No Joke Generated Yet :("

    def __str__(self):
        return f"Jokes;{self.joke};{self.game_id}"

    def get_joke(self):
        with open("MainControlLoop/Mode/outreach/jokes/jokes.txt", "r") as f:
            lines = f.readlines()
            return random.choice(lines).strip()

    def set_joke(self, joke_type):  # so that it works with outreach.py
        pass

    def get_best_move(self):  # so that it works with outreach.py
        self.joke = self.get_joke()
        return self.joke

    def push(self, move):  # so that it works with outreach.py
        pass



