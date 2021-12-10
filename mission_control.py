from MainControlLoop.main_control_loop import MainControlLoop
import time


class MissionControl():
    def __init__(self):
        self.mcl = MainControlLoop()
    
    def main(self):
        self.mcl.run()


if __name__ == "__main__":
    mission_control = MissionControl()
    mission_control.main()
