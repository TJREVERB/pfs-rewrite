from MainControlLoop.main_control_loop import MainControlLoop
from MainControlLoop.lib.exceptions import *


class MissionControl:
    SIGNAL_THRESHOLD = 2

    def __init__(self):
        self.mcl = MainControlLoop()
        self.sfr = self.mcl.sfr

    def main(self):
        while True:  # Run forever
            try:
                try:
                    self.mcl.iterate()  # Run a single iteration of MCL
                except CustomException as e:  # If a problem happens (entire pfs is wrapped to raise CustomExceptions)
                    if type(e.exception) == KeyboardInterrupt:  # If we ended the program
                        raise e.exception  # Raise up to next try-except block
                    elif type(e) == APRSError:
                        self.aprs_troubleshoot(e)
                    elif type(e) == IridiumError:
                        self.iridium_troubleshoot(e)
                    elif type(e) == EPSError:
                        self.eps_troubleshoot(e)
                    elif type(e) == RTCError:
                        self.rtc_troubleshoot(e)
                    elif type(e) == IMUError:
                        self.imu_troubleshoot(e)
                    elif type(e) == BatteryError:
                        self.battery_troubleshoot(e)
                    elif type(e) == LogicalError:
                        raise e  # We shouldn't troubleshoot a problem with high level code
                    continue  # Move on with MCL if troubleshooting solved problem (no additional exception)
                # If a leak happens (impossible), exception will travel up to next try-except block (safe mode)
            except Exception as e:  # If another exception happens during troubleshooting (troubleshooting fails)
                if type(e) == KeyboardInterrupt:  # If we ended the program
                    self.sfr.clear_logs()  # Reset sfr
                    exit(0)  # Cleanly exit
                else:  # If error is genuine
                    # self.safe_mode(e)  # Safe mode to allow ground to solve the problem
                    self.testing_mode(e)  # DEBUG

    def aprs_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def iridium_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def eps_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def rtc_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def imu_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def battery_troubleshoot(self, e: CustomException):
        raise e  # TODO: IMPLEMENT BASIC TROUBLESHOOTING

    def turn_on(self, component):
        pass

    def turn_off(self, component):
        pass

    def testing_mode(self, e: Exception):
        """
        DEBUG ONLY!!!
        Print current mode, values of sfr, exception's repr
        Then cleanly exit
        """
        print("ERROR!!!")
        print(f"Currently in {self.sfr.vars.MODE}")
        print("State field registry fields:")
        print(self.sfr.vars.to_dict())
        print("Exception:")
        print(repr(e))
        exit(1)

    def safe_mode(self, e: Exception):
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
        except:
            print("pfs team took the L")
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

    def charge(self):
        pass


if __name__ == "__main__":
    mission_control = MissionControl()
    mission_control.main()
