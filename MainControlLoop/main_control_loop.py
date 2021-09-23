from MainControlLoop.lib.StateFieldRegistry import registry, state_fields
from MainControlLoop.tests.random_number import RandomNumber
from MainControlLoop.tasks.APRS.aprs import APRS
import random


class MainControlLoop:
    def __init__(self):
        """
        Create all the objects
        Each object should take in the state field registry
        """
        self.state_field_registry: StateFieldRegistry = registry.StateFieldRegistry()
        self.randnumber = RandomNumber(self.state_field_registry)
        self.aprs = APRS(self.state_field_registry)

    def execute(self):
        """READ"""
        self.randnumber.read()
        self.aprs.read()

        """CONTROL"""
        self.randnumber.control()
        self.aprs.control()

        """ACTUATE"""
        self.randnumber.actuate()

    def run(self):  # continiously run the main control loop
        while True:
            self.execute()
