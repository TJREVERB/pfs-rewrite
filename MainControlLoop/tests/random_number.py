from random import randint

from MainControlLoop.lib.StateFieldRegistry import registry, state_fields


class RandomNumber:
    """
    Example class RandomNumber
    Read generates a random number between 0 and 100 and updates the statefield
    Control determines whether it is above or below 50
    Actuate prints the value based on whether it is above or below 50
    """

    def __init__(self, state_field_registry: registry.StateFieldRegistry):
        self.state_field_registry = state_field_registry

    def read(self):
        num = randint(0, 100)
        self.state_field_registry.update(
            state_fields.StateField.RAND_NUMBER, num)

    def control(self):
        if(self.state_field_registry.get(state_fields.StateField.RAND_NUMBER) > 50):
            self.state_field_registry.update(
                state_fields.StateField.ABOVE_50, True)
        else:
            self.state_field_registry.update(
                state_fields.StateField.ABOVE_50, False)

    def actuate(self):
        if(self.state_field_registry.get(state_fields.StateField.ABOVE_50)):
            print("Above 50:", self.state_field_registry.get(
                state_fields.StateField.RAND_NUMBER))
        else:
            print("Below 50:", self.state_field_registry.get(
                state_fields.StateField.RAND_NUMBER))
