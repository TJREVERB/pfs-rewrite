from copy import deepcopy
from .state_fields import StateField


class StateFieldRegistry:

    def __init__(self):
        """
        Defines all the StateFields present in the state registry
        """
        self.registry = {
            StateField.RAND_NUMBER: 0,
            StateField.ABOVE_50: False
        }

    def update(self, field: StateField, value):
        """
        Update a StateField in the registry.
        :param field: (StateField) StateField type to update in registry
        :param value: (Any) Value to put in the registry,
        :return: (bool) If the value was updated in the registry
        """
        if field not in self.registry:
            return False

        self.registry[field] = value

        return True

    def get(self, field: StateField):
        """
        Returns a StateField from the registry
        :param field: (StateField) StateField type to get from registry
        :return: (Any) The value found in the registry.
        """
        if field in self.registry:
            return deepcopy(self.registry[field])
        return None
