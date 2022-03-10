import time
from enum import Enum, IntEnum
from smbus2 import SMBus
from lib.exceptions import wrap_errors, AntennaError, LogicalError
from Drivers.device import Device
import RPi.GPIO as GPIO

class AntennaDeployerCommand(IntEnum):
    SYSTEM_RESET = 0xAA
    WATCHDOG_RESET = 0xCC

    ARM_ANTS = 0xAD
    DISARM_ANTS = 0xAC

    DEPLOY_1 = 0xA1
    DEPLOY_2 = 0xA2
    DEPLOY_3 = 0xA3
    DEPLOY_4 = 0xA4

    AUTO_DEPLOY = 0xA5
    CANCEL_DEPLOY = 0xA9

    DEPLOY_1_OVERRIDE = 0xBA
    DEPLOY_2_OVERRIDE = 0xBB
    DEPLOY_3_OVERRIDE = 0xBC
    DEPLOY_4_OVERRIDE = 0xBD

    GET_TEMP = 0xC0
    GET_STATUS = 0xC3

    GET_COUNT_1 = 0xB0
    GET_COUNT_2 = 0xB1
    GET_COUNT_3 = 0xB2
    GET_COUNT_4 = 0xB3

    GET_UPTIME_1 = 0xB4
    GET_UPTIME_2 = 0xB5
    GET_UPTIME_3 = 0xB6
    GET_UPTIME_4 = 0xB7

class AntennaDeployer(Device):
    PRIMARY_ADDRESS = 0x31
    SECONDARY_ADDRESS = 0x32
    @wrap_errors(AntennaError)
    def __init__(self, sfr):
        super().__init__(sfr)
        self.bus = SMBus(1)
        self.addr = self.PRIMARY_ADDRESS
        self.channels = [26, 13, 6, 5]
        for i in self.channels:
            GPIO.setup(i, GPIO.IN, pull_up_down = GPIO.PUD_UP) #TODO: This is set up for stress test, but must be changed for flight
        self.check_deployment()

    @wrap_errors(AntennaError)
    def write(self, command: AntennaDeployerCommand, parameter: int) -> bool or None:
        """
        Wrapper for SMBus write word data
        :param command: (AntennaDeployerCommand) The antenna deployer command to run
        :param parameter: (int) The parameter to pass in to the command (usually 0x00)
        :return: (bool or None) success
        """
        if type(command) != AntennaDeployerCommand:
            raise LogicalError(details="Not an AntennaDeployerCommand!")
        try:
            self.bus.write_byte_data(self.addr, command.value, parameter)
        except OSError as e:
            print(e)
            self.addr = self.SECONDARY_ADDRESS
            self.bus.write_byte_data(self.addr, command.value, parameter)
        return True

    @wrap_errors(AntennaError)
    def functional(self):
        """
        :return: (bool) i2c file opened by SMBus
        """
        try:
            self.write(AntennaDeployerCommand.GET_TEMP, 0)
        except Exception as e:
            print(e)
            raise AntennaError(details = "Bad Connection")

        return True


    @wrap_errors(AntennaError)
    def reset(self):
        """
        Resets the Microcontroller on the ISIS Antenna Deployer
        :return: (bool) no error
        """
        self.write(AntennaDeployerCommand.SYSTEM_RESET, 0x00)
        return True

    @wrap_errors(AntennaError)
    def disable(self):
        """
        Disarms the ISIS Antenna Deployer
        """
        self.write(AntennaDeployerCommand.DISARM_ANTS, 0x00)
        return True

    @wrap_errors(AntennaError)
    def enable(self):
        """
        Arms the ISIS Antenna Deployer
        """
        self.write(AntennaDeployerCommand.ARM_ANTS, 0x00)
        return True

    @wrap_errors(AntennaError)
    def deploy(self) -> bool:
        self.enable()
        self.write(AntennaDeployerCommand.AUTO_DEPLOY, 0x0A)
        time.sleep(40) # Wait for deployment to finish
        return True

    @wrap_errors(AntennaError)
    def check_deployment(self):
        #raw = self.read(AntennaDeployerCommand.GET_STATUS)
        #twobyte = raw
        # bit position 3, 7, 11, 15 are antenna states 4, 3, 2, 1 respectively. 0 means deployed, 1 means not
        #self.sfr.vars.ANTENNA_DEPLOYED = ((twobyte >> 3 & 1) + (twobyte >> 7 & 1) + (twobyte >> 11 & 1) + (twobyte >> 15 & 1)) <= 1 
        # Minimum 3 antennas deployed
        if self.sfr.devices["Antenna Deployer"] is None:
            raise AntennaError(details = "Antenna not powered on")
        result = sum([GPIO.input(i) for i in self.channels])
        self.sfr.vars.ANTENNA_DEPLOYED = (result <= 1)
        return result