import time
from MainControlLoop.main_control_loop import MainControlLoop

class MissionControl:
    def __init__(self):
        self.mcl = MainControlLoop()
        self.sfr = self.mcl.sfr

        self.SIGNAL_THRESHOLD = 2

    def main(self):
        while True:
            try:
                self.mcl.run()
            except Exception as e:
                self.remote_code_execution(e)

    def remote_code_execution(self, e: Exception):
        troubleshooting_completed = False
        try:
            self.sfr.instruct["Pin On"]("Iridium")
            self.sfr.iridium.transmit(repr(e))  # doesnt work
        except:
            print("anoda L")
        while not troubleshooting_completed:
                if self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
                    self.sfr.devices["Iridium"].next_msg()
                for messages in self.sfr.command_buffer:
                    if messages.command_string == "STOPREMOTEEXEC":  # idk:
                        troubleshooting_completed = True
                    elif messages.command_string in self.sfr.command_executor.primary_registry:
                        self.sfr.command_executor.primary_registry[messages.command_string](messages)
                    else:
                        exec(f"{messages.command_string}")
            except:  # add specific errors that would pertain to iridium not working
                print("Pfs team took an L")  # not actually this but 12am humor




