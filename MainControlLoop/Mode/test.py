class Cat:
    def __init__(self, sfr):
        self.sfr = sfr


class Dog:
    def __init__(self):
        self.n = 5

    def modify(self):
        self.n = 3

sfr = Dog()
e = Cat(sfr)
e.sfr.modify()
print(sfr.n)
print(e.sfr.n)
