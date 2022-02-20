import random


class JokesGame:
    def __init__(self, sfr, game_id):
        self.sfr = sfr
        self.game_id = game_id
        self.joke_type = None
        self.joke_dict = {
            "Joke": "MainControlLoop/Mode/outreach/jokes/jokes.txt",  # dad joke
            "Pickup": "MainControlLoop/Mode/outreach/jokes/pickup.txt",  # pickup line
            "Inside": "MainControlLoop/Mode/outreach/jokes/inside.txt"  # insider joke
        }
        self.joke = "No Joke Generated Yet :("

    def __str__(self):
        return f"Jokes;{self.joke};{self.game_id}"

    def get_joke(self):
        with open(self.joke_dict[self.joke_type], "r") as f:
            lines = f.readlines()
            return random.choice(lines).strip()

    def set_game(self, joke_type):
        if joke_type == "Random":
            self.joke_type = random.choice(list(self.joke_dict.keys()))
        else:
            self.joke_type = joke_type

    def get_best_move(self):  # so that it works with outreach.py
        self.joke = self.get_joke()
        return self.joke

    def push(self, move):  # so that it works with outreach.py
        pass

    def random(self):
        rand = random.randint(0, 3)
        if rand == 0:
            return "Joke"
        elif rand == 1:
            return "Pickup"
        elif rand == 2:
            return "Inside"
        elif rand == 3:
            return "Random"
