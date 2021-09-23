from MainControlLoop.lib.StateFieldRegistry import registry, state_fields
from MainControlLoop.tests.random_number import RandomNumber
import random


class MainControlLoop:
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.state_field_registry: StateFieldRegistry = registry.StateFieldRegistry()
        self.randnumber = RandomNumber(self.state_field_registry)

    def execute(self):
        """READ"""
        self.randnumber.read()

        """CONTROL"""
        self.randnumber.control()

        """ACTUATE"""
        self.randnumber.actuate()

    def run(self):  # continiously run the main control loop
        while True:
            self.execute()
