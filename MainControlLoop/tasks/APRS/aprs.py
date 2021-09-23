from MainControlLoop.lib.StateFieldRegistry import registry, state_fields


class Aprs:
    """
    Class for APRS
    """

    def __init__(self, state_field_registry: registry.StateFieldRegistry):
        self.state_field_registry = state_field_registry
