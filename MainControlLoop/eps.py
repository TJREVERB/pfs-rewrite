from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from smbus2 import SMBusWrapper
from smbus2 import SMBus
import time


class EPS:
    """
    Class for EPS
    """
    def __init__(self, state_field_registry):
        self.EPS_ADDRESS: hex = 0x2b
        self.sfr = state_field_registry
        self.components = {  # List of components and their associated pins
            "APRS": [0x04],
            "Iridium": [0x03],
            "Antenna Deployer": [0x06],
            "Iridium Serial Converter": [0x08],
        }
        # Refer to EPS manual pages 40-50 for info on EPS commands
        # Format: self.eps.commands["COMMAND"](ARGS)
        self.commands = {
            # Board info commands: Basic board info
            "Board Status": lambda: self.request(0x01, [0x00], 2),  # Reads and returns board status
            "Last Error": lambda: self.request(0x03, [0x00], 2),  # Reads and returns last error
            "Firmware Version": lambda: self.request(0x04, [0x00], 2),  # Reads and returns firmware version
            "Checksum": lambda: self.request(0x05, [0x00], 2),  # Reads and returns generated checksum of ROM contents
            "Firmware Revision": lambda: self.request(0x06, [0x00], 2),  # Reads and returns firmware revision number

            # Watchdog commands: Watchdog will reset the EPS after a period of time (default 4 minutes)
            # with no commands received.
            "Watchdog Period": lambda: self.request(0x20, [0x00], 2),  # Reads and returns current watchdog period
            "Reset Watchdog": lambda: self.command(0x22, [0x00]),  # Resets communications watchdog timer
            # Any command will reset the timer, this command can be used if no action from the EPS is needed
            "Set Watchdog Period": lambda period: self.command(0x21, period),
            # Sets communications timeout watchdog period, minimum 1 minute maximum 90 minutes

            # Reset count commands: EPS will be reset under various conditions,
            # these functions check how many times have been caused by each condition.
            # Counts roll over from 255 to 0.
            "Brownout Resets": lambda: self.request(0x31, [0x00], 2),  # Reads and returns number of brownout resets
            "Software Resets": lambda: self.request(0x32, [0x00], 2),  # Reads and returns number of software resets
            "Manual Resets": lambda: self.request(0x33, [0x00], 2),  # Reads and returns number of manual resets
            "Watchdog Resets": lambda: self.request(0x34, [0x00], 2),  # Reads and returns number of watchdog resets

            # PDM Control: Get information about PDMs and switch PDMs on and off to power on or off components
            "All Actual States": lambda: self.request(0x42, [0x00], 4),
            # Reads and returns actual state of all PDMs in byte form
            # PDMs may be shut off due to protections, and this command shows the actual state of all PDMs
            "All Expected States": lambda: self.request(0x43, [0x00], 4),
            # Reads and returns expected state of all PDMs in byte form
            # These depend on whether they have been commanded on or off, regardless of protection trips
            "All Initial States": lambda: self.request(0x44, [0x00], 4),
            # Reads and returns initial states of all PDMs in byte form
            # These are the states the PDMs will be in after a reset
            "Pin Actual State": lambda component: self.request(0x54, self.components[component], 2),
            # Reads and returns actual state of one PDM
            "All On": lambda: self.command(0x40, [0x00]),  # Turn all PDMs on
            "All Off": lambda: self.command(0x41, [0x00]),  # Turn all PDMs off
            "Set All Initial": lambda: self.command(0x45, [0x00]),  # Set all PDMs to their initial state
            "Pin On": lambda component: self.command(0x50, self.components[component]),  # Enable component
            "Pin Off": lambda component: self.command(0x51, self.components[component]),  # Disable component
            "Pin Init On": lambda component: self.command(0x52, self.components[component]),
            # Set initial state of component to "on"
            "Pin Init Off": lambda component: self.command(0x53, self.components[component]),
            # Set initial state of component to "off"

            # PDM Timers: When enabled with timer restrictions, a PDM will remain on for only a set period of time.
            # By default each PDM does not have restrictions
            "PDM Timer Limit": lambda component: self.request(0x61, self.components[component], 2),
            # Reads and returns timer limit for given PDM
            "PDM Timer Value": lambda component: self.request(0x62, self.components[component], 2),
            # Reads and returns passed time since PDM timer was enabled
            "Set Timer Limit": lambda period, component: self.command(0x60, [period[0], self.components[component][0]]),
            # Sets timer limit for given PDM

            # PCM bus control
            "Bus Reset": lambda pcm: self.command(0x70, [sum([self.pcm_busses[i][0] for i in pcm])]),

            # Manual reset
            "Manual Reset": lambda: self.command(0x80, [0x00]),
            # Manually resets EPS to initial state, and increments manual reset counter
        }
        # Format: self.eps.telemetry["REQUESTED TELEMETRY"]()
        # Refer to EPS Manual Table 11.8-10
        self.telemetry = {
            "IBCROUT": lambda: self.telemetry_request([0xE2, 0x84], 14.662757),  # BCR Output current in mA
            "VBCROUT": lambda: self.telemetry_request([0xE2, 0x80], 0.008993157),  # BCR Output voltage in V
            "I3V3DRW": lambda: self.telemetry_request([0xE2, 0x05], 0.001327547),  # 3V3 Current draw of EPS in A
            "I5VDRW": lambda: self.telemetry_request([0xE2, 0x15], 0.001327547),  # 5V Current draw of EPS in A
            "I12VBUS": lambda: self.telemetry_request([0xE2, 0x34], 0.00207),   # 12V Bus output current in A
            "V12VBUS": lambda: self.telemetry_request([0xE2, 0x30], 0.01349),  # 12V Bus output voltage in V
            "IBATBUS": lambda: self.telemetry_request([0xE2, 0x24], 0.005237),  # Batt Bus output current in A
            "VBATBUS": lambda: self.telemetry_request([0xE2, 0x20], 0.008978),  # Batt Bus output voltage in V
            "I5VBUS": lambda: self.telemetry_request([0xE2, 0x14], 0.005237),  # 5V Bus output current in A
            "V5VBUS": lambda: self.telemetry_request([0xE2, 0x10], 0.005865),  # 5V Bus output voltage in V
            "I3V3BUS": lambda: self.telemetry_request([0xE2, 0x04], 0.005237),  # 3V3 Bus output current in A
            "V3V3BUS": lambda: self.telemetry_request([0xE2, 0x00], 0.004311),  # 3V3 Bus output voltage in V
            "VSW1": lambda: self.telemetry_request([0xE4, 0x10], 0.01349),   # SW1 output voltage in V
            "ISW1": lambda: self.telemetry_request([0xE4, 0x14], 0.001328),  # SW1 output current in A
            "VSW2": lambda: self.telemetry_request([0xE4, 0x20], 0.01349),   # SW2 output voltage in V
            "ISW2": lambda: self.telemetry_request([0xE4, 0x24], 0.001328),  # SW2 output current in A
            "VSW3": lambda: self.telemetry_request([0xE4, 0x30], 0.008993),  # SW3 output voltage in V
            "ISW3": lambda: self.telemetry_request([0xE4, 0x34], 0.006239),  # SW3 output current in A
            "VSW4": lambda: self.telemetry_request([0xE4, 0x40], 0.008993),  # SW4 output voltage in V
            "ISW4": lambda: self.telemetry_request([0xE4, 0x44], 0.006239),  # SW4 output current in A
            "VSW5": lambda: self.telemetry_request([0xE4, 0x50], 0.005865),  # SW5 output voltage in V
            "ISW5": lambda: self.telemetry_request([0xE4, 0x54], 0.001328),  # SW5 output current in A
            "VSW6": lambda: self.telemetry_request([0xE4, 0x60], 0.005865),  # SW6 output voltage in V
            "ISW6": lambda: self.telemetry_request([0xE4, 0x64], 0.001328),  # SW6 output current in A
            "VSW7": lambda: self.telemetry_request([0xE4, 0x70], 0.005865),  # SW7 output voltage in V
            "ISW7": lambda: self.telemetry_request([0xE4, 0x74], 0.001328),  # SW7 output current in A
            "VSW8": lambda: self.telemetry_request([0xE4, 0x80], 0.004311),  # SW8 output voltage in V
            "ISW8": lambda: self.telemetry_request([0xE4, 0x84], 0.001328),  # SW8 output current in A
            "VSW9": lambda: self.telemetry_request([0xE4, 0x90], 0.004311),  # SW9 output voltage in V
            "ISW9": lambda: self.telemetry_request([0xE4, 0x94], 0.001328),  # SW9 output current in A
            "VSW10": lambda: self.telemetry_request([0xE4, 0xA0], 0.004311),  # SW10 output voltage in V
            "ISW10": lambda: self.telemetry_request([0xE4, 0xA4], 0.001328),  # SW10 output current in A
            "TBRD": lambda: self.telemetry_request([0xE3, 0x08], 0.372434),  # Motherboard temperature in K

            #Telemetry unique to 25-02452 and 01-02453 (CHECK THIS LATER) 
            "VBCR1": lambda: self.telemetry_request([0xE1, 0x10], 0.0322581),  # Voltage feeding BCR1 in V
            "IBCR1A": lambda: self.telemetry_request([0xE1, 0x14], 0.0009775),  # Current BCR1 connector SA1A in A
            "IBCR1B": lambda: self.telemetry_request([0xE1, 0x15], 0.0009775),  # Current BCR1 connector SA1B in B
            "TBCR1A": lambda: self.telemetry_request([0xE1, 0x18], 0.4963),  # Array temperature connector SA1A in K
            "TBCR1B": lambda: self.telemetry_request([0xE1, 0x19], 0.4963),  # Array temperature connector SA1B in K
            "SDBCR1A": lambda: self.telemetry_request([0xE1, 0x1C], 1.59725),  # Sun detector connector SA1A in W/m^2
            "SDBCR1B": lambda: self.telemetry_request([0xE1, 0x1D], 1.59725),  # Sun detector connector SA1B in W/m^2
            
            "VBCR2": lambda: self.telemetry_request([0xE1, 0x20], 0.0322581),  # Voltage feeding BCR2 in V
            "IBCR2A": lambda: self.telemetry_request([0xE1, 0x24], 0.0009775),  # Current BCR2 connector SA2A in A
            "IBCR2B": lambda: self.telemetry_request([0xE1, 0x25], 0.0009775),  # Current BCR2 connector SA2B in B
            "TBCR2A": lambda: self.telemetry_request([0xE1, 0x28], 0.4963),  # Array temperature connector SA2A in K
            "TBCR2B": lambda: self.telemetry_request([0xE1, 0x29], 0.4963),  # Array temperature connector SA2B in K
            "SDBCR2A": lambda: self.telemetry_request([0xE1, 0x2C], 1.59725),  # Sun detector connector SA2A in W/m^2
            "SDBCR2B": lambda: self.telemetry_request([0xE1, 0x2D], 1.59725),  # Sun detector connector SA2B in W/m^2

            "VBCR3": lambda: self.telemetry_request([0xE1, 0x30], 0.0099706),  # Voltage feeding BCR3 in V,
            # can also be used to monitor input voltage from 5V USB CHG
            "IBCR3A": lambda: self.telemetry_request([0xE1, 0x34], 0.0009775),  # Current BCR3 connector SA3A in A,
            # can also be used to monitor input current from 5V USB CHG
            "IBCR3B": lambda: self.telemetry_request([0xE1, 0x35], 0.0009775),  # Current BCR3 connector SA3B in B
            "TBCR3A": lambda: self.telemetry_request([0xE1, 0x38], 0.4963),  # Array temperature connector SA3A in K
            "TBCR3B": lambda: self.telemetry_request([0xE1, 0x39], 0.4963),  # Array temperature connector SA3B in K
            "SDBCR3A": lambda: self.telemetry_request([0xE1, 0x3C], 1.59725),  # Sun detector connector SA3A in W/m^2
            "SDBCR3B": lambda: self.telemetry_request([0xE1, 0x3D], 1.59725),  # Sun detector connector SA3B in W/m^2

        }
        # PCM busses for the Bus Reset command
        # Combine as needed to reset multiple buses, e.g. 0x03 resets Battery and 5V
        self.pcm_busses = {
            "Battery": [0x01],
            "5V": [0x02],
            "3.3V": [0x04],
            "12V": [0x08],
        }

    def request(self, register, data, length) -> bytes:
        """
        Requests and returns uninterpreted bytes object
        :param register: register
        :param data: data
        :param length: number of bytes to read
        :return: (byte) response from EPS
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, register, data)
            time.sleep(.5)
            result = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, length)
        return result

    def command(self, register, data) -> bool:
        """
        Sends command to EPS
        :param register: register
        :param data: data
        :return: (bool) whether command was successful
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, register, data)

    def telemetry_request(self, tle, multiplier) -> float:
        """
        Requests and returns interpreted telemetry data
        :param tle: TLE code
        :parm multiplier: = multiplier
        :return: (float) telemetry value
        """
        raw = self.request(0x10, tle, 2)
        return (raw[0] << 8 | raw[1]) * multiplier

    def total_power(self) -> float:
        """
        Returns total power draw based on EPS telemetry
        :return: (float) power draw in W
        """
        return self.telemetry["I12VBUS"]() * self.telemetry["V12VBUS"]() + \
            self.telemetry["IBATBUS"]() * self.telemetry["VBATBUS"]() + \
            self.telemetry["I5VBUS"]() * self.telemetry["V5VBUS"]() + \
            self.telemetry["I3V3BUS"]() * self.telemetry["V3V3BUS"]() + \
            self.telemetry["I3V3BUS"]() * self.telemetry["V3V3BUS"]() + \
            self.telemetry["ISW3"]() * self.telemetry["VSW3"]() + \
            self.telemetry["ISW4"]() * self.telemetry["VSW4"]()
