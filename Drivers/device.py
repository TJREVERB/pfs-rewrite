class Device:
    def __init__(self, sfr):
        self.sfr = sfr

    # general check of the device, returns True if the device is confirmed to be (somewhat) working
    def functional(self):
        return True
