from MainControlLoop.main_control_loop import MainControlLoop
from exceptions import *


class MissionControl():
    SIGNAL_THRESHOLD = 2
    def __init__(self):
        self.mcl = MainControlLoop()
        self.sfr = self.mcl.sfr

    def main(self):
        while True:
            try:
                self.mcl.run()
            except APRSError as e:
                pass  # TODO: IMPLEMENT BASIC TROUBLESHOOTING
            except IridiumError as e:
                pass  # TODO: IMPLEMENT BASIC TROUBLESHOOTING
            except EPSError as e:
                pass  # TODO: IMPLEMENT BASIC TROUBLESHOOTING
            except RTCError as e:
                pass  # TODO: IMPLEMENT BASIC TROUBLESHOOTING
            except IMUError as e:
                pass  # TODO: IMPLEMENT BASIC TROUBLESHOOTING
            except BatteryError as e:
                pass  # TODO: IMPLEMENT BASIC TROUBLESHOOTING
            except SystemError as e:
                pass  # TODO: IMPLEMENT BASIC TROUBLESHOOTING
            except Exception as e:
                self.remote_code_execution(e)

    def remote_code_execution(self, e: Exception):
        """
        Continiously listen for messages from main radio
        if there is message, attempt to exec method
        Should only switch back to mcl from confirmation from ground
        Should we put something to attempt to switch back to mcl if too much time passed?
        """
        troubleshooting_completed = False
        try:
            self.sfr.instruct["Pin On"]("Iridium")
            self.sfr.iridium.transmit(repr(e))
        except Exception:
            print("anoda L")
        while not troubleshooting_completed:
            try:
                if self.sfr.devices["Iridium"].check_signal_passive() >= self.SIGNAL_THRESHOLD:
                    self.sfr.devices["Iridium"].next_msg()
                for messages in self.sfr.command_buffer:
                    if messages.command_string == "":  # idk:
                        troubleshooting_completed = True
                        break
                    elif messages.command_string in self.sfr.command_executor.primary_registry:
                        self.sfr.command_executor.primary_registry[messages.command_string](messages)
                    else:
                        exec(f"{messages.command_string}")
            except:  # add specific errors that would pertain to iridium not working
                print("Pfs team took an L")  # not actually this but 12am humor


if __name__ == "__main__":
    mission_control = MissionControl()
    mission_control.main()
