import time
from enum import Enum
from smbus2 import SMBus, i2c_msg
from lib.exceptions import wrap_errors, AntennaError, LogicalError
from Drivers.device import Device


class AntennaDeployerCommand(Enum):
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
    BUS_NUMBER = 1
    PRIMARY_ADDRESS = 0x31
    SECONDARY_ADDRESS = 0x32
    EXPECTED_BYTES = {
        AntennaDeployerCommand.SYSTEM_RESET: 0,
        AntennaDeployerCommand.WATCHDOG_RESET: 0,

        AntennaDeployerCommand.ARM_ANTS: 0,
        AntennaDeployerCommand.DISARM_ANTS: 0,

        AntennaDeployerCommand.DEPLOY_1: 0,
        AntennaDeployerCommand.DEPLOY_2: 0,
        AntennaDeployerCommand.DEPLOY_3: 0,
        AntennaDeployerCommand.DEPLOY_4: 0,

        AntennaDeployerCommand.AUTO_DEPLOY: 0,
        AntennaDeployerCommand.CANCEL_DEPLOY: 0,

        AntennaDeployerCommand.DEPLOY_1_OVERRIDE: 0,
        AntennaDeployerCommand.DEPLOY_2_OVERRIDE: 0,
        AntennaDeployerCommand.DEPLOY_3_OVERRIDE: 0,
        AntennaDeployerCommand.DEPLOY_4_OVERRIDE: 0,

        AntennaDeployerCommand.GET_TEMP: 2,
        AntennaDeployerCommand.GET_STATUS: 2,

        AntennaDeployerCommand.GET_COUNT_1: 1,
        AntennaDeployerCommand.GET_COUNT_2: 1,
        AntennaDeployerCommand.GET_COUNT_3: 1,
        AntennaDeployerCommand.GET_COUNT_4: 1,

        AntennaDeployerCommand.GET_UPTIME_1: 2,
        AntennaDeployerCommand.GET_UPTIME_2: 2,
        AntennaDeployerCommand.GET_UPTIME_3: 2,
        AntennaDeployerCommand.GET_UPTIME_4: 2,
    }

    @wrap_errors(AntennaError)
    def __init__(self, sfr):
        super().__init__(sfr)
        self.bus = SMBus(self.BUS_NUMBER)
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
        self.bus.write_word_data(self.PRIMARY_ADDRESS, command.value, parameter)
        return True

    @wrap_errors(AntennaError)
    def read(self, command: AntennaDeployerCommand) -> bytes:
        """
        Wrapper for SMBus to read from AntennaDeployer
        :param command: (AntennaDeployerCommand) The antenna deployer command to run
        :return: (ctypes.LP_c_char, bool) buffer, success
        """
        if type(command) != AntennaDeployerCommand:
            raise LogicalError(details="Not an AntennaDeployerCommand!")
        self.write(command, 0x00)
        time.sleep(0.5)
        return self.bus.read_i2c_block_data(self.PRIMARY_ADDRESS, 0, self.EXPECTED_BYTES[command]) #TODO: DEBUG THIS. Antenna deployer is only returning 255, 255

    @wrap_errors(AntennaError)
    def functional(self):
        """
        :return: (bool) i2c file opened by SMBus
        """
        try:
            raw_bytes = self.read(AntennaDeployerCommand.GET_TEMP)
        except Exception as e:
            print(e)
            raise AntennaError("Bad Connection")
        raw_count = (raw_bytes[0] << 8) | raw_bytes[1]
        v = raw_count * 3300 / 1023 # mV
        if v > 2616 or v < 769:
            raise AntennaError("Bad data readout")
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
        self.write(AntennaDeployerCommand.DEPLOY_1, 0x0A)
        self.write(AntennaDeployerCommand.DEPLOY_2, 0x0A)
        self.write(AntennaDeployerCommand.DEPLOY_3, 0x0A)
        self.write(AntennaDeployerCommand.DEPLOY_4, 0x0A)
        return True

    @wrap_errors(AntennaError)
    def check_deployment(self):
        raw = self.read(AntennaDeployerCommand.GET_STATUS)
        twobyte = (raw[0] << 8) | raw[1] 
        # bit position 3, 7, 11, 15 are antenna states 4, 3, 2, 1 respectively. 0 means deployed, 1 means not
        self.sfr.vars.ANTENNA_DEPLOYED = ((twobyte >> 3 & 1) + (twobyte >> 7 & 1) + (twobyte >> 11 & 1) + (twobyte >> 15 & 1)) <= 1 
        # Minimum 3 antennas deployed


