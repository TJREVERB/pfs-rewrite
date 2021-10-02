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
        self.state_field_registry: state_field_registry = state_field_registry
        self.components = {  # List of components and their associated pins
            "APRS": [0x04],
            "Iridium": [0x03],
            "Antenna Deployer": ""
        }
        # Refer to EPS manual pages 40-50 for info on EPS commands
        # Format: self.eps.request(self.eps.request_args["REQUESTED INFORMATION"])
        self.request_args = {
            # Board info commands: Basic board info
            "Board Status": (0x01, [0.00], 2),  # Reads and returns board status
            "Last Error": (0x03, [0x00], 2),  # Reads and returns last error
            "Firmware Version": (0x04, [0x00], 2),  # Reads and returns firmware version
            "Checksum": (0x05, [0x00], 2),  # Reads and returns generated checksum of ROM contents
            "Firmware Revision": (0x06, [0x00], 2),  # Reads and returns firmware revision number

            # Watchdog commands: Watchdog will reset the EPS after a period of time (default 4 minutes)
            # with no commands received.
            "Watchdog Period": (0x20, [0x00], 2),  # Reads and returns current watchdog period

            # Reset count commands: EPS will be reset under various conditions,
            # these functions check how many times have been caused by each condition.
            # Counts roll over from 255 to 0.
            "Brownout Resets": (0x31, [0x00], 2),  # Reads and returns number of brownout resets
            "Software Resets": (0x32, [0x00], 2),  # Reads and returns number of software resets
            "Manual Resets": (0x33, [0x00], 2),  # Reads and returns number of manual resets
            "Watchdog Resets": (0x34, [0x00], 2),  # Reads and returns number of watchdog resets

            # PDM Control: Get information about PDMs and switch PDMs on and off to power on or off components
            "All Actual States": (0x42, [0x00], 4),  # Reads and returns actual state of all PDMs in byte form
            # PDMs may be shut off due to protections, and this command shows the actual state of all PDMs
            "All Expected States": (0x43, [0x00], 4),  # Reads and returns expected state of all PDMs in byte form
            # These depend on whether they have been commanded on or off, regardless of protection trips
            "All Initial States": (0x44, [0x00], 4),  # Reads and returns initial states of all PDMs in byte form
            # These are the states the PDMs will be in after a reset
        }
        # Format: self.eps.telemetry_request(self.eps.request_telemetry_args["REQUESTED TELEMETRY"])
        # Refer to EPS Manual Table 11.8-10
        self.request_telemetry_args = {
            "IBCROUT": ([0xE2, 0x84], 14.662757), #BCR Output current in mA
            "VBCROUT": ([0xE2, 0x80], 0.008993157), #BCR Output voltage in V
            "I3V3DRW": ([0xE2, 0x05], 0.001327547), #3V3 Current draw of EPS in A
            "I5VDRW" : ([0xE2, 0x15], 0.001327547), #5V Current draw of EPS in A
            "I12VBUS": ([0xE2, 0x34], 0.00207),  #12V Bus output current in A
            "V12VBUS": ([0xE2, 0x30], 0.01349),  #12V Bus output voltage in V
            "IBATBUS": ([0xE2, 0x24], 0.005237), #Batt Bus output current in A
            "VBATBUS": ([0xE2, 0x20], 0.008978), #Batt Bus output voltage in V
            "I5VBUS" : ([0xE2, 0x14], 0.005237), #5V Bus output current in A
            "V5VBUS" : ([0xE2, 0x10], 0.005865), #5V Bus output voltage in V
            "I3V3BUS": ([0xE2, 0x04], 0.005237), #3V3 Bus output current in A
            "V3V3BUS": ([0xE2, 0x00], 0.004311), #3V3 Bus output voltage in V
            "VSW1"   : ([0xE4, 0x10], 0.01349),  #SW1 output voltage in V
            "ISW1"   : ([0xE4, 0x14], 0.001328), #SW1 output current in A
            "VSW2"   : ([0xE4, 0x20], 0.01349),  #SW2 output voltage in V
            "ISW2"   : ([0xE4, 0x24], 0.001328), #SW2 output current in A
            "VSW3"   : ([0xE4, 0x30], 0.008993), #SW3 output voltage in V
            "ISW3"   : ([0xE4, 0x34], 0.006239), #SW3 output current in A
            "VSW4"   : ([0xE4, 0x40], 0.008993), #SW4 output voltage in V
            "ISW4"   : ([0xE4, 0x44], 0.006239), #SW4 output current in A
            "VSW5"   : ([0xE4, 0x50], 0.005865), #SW5 output voltage in V
            "ISW5"   : ([0xE4, 0x54], 0.001328), #SW5 output current in A
            "VSW6"   : ([0xE4, 0x60], 0.005865), #SW6 output voltage in V
            "ISW6"   : ([0xE4, 0x64], 0.001328), #SW6 output current in A
            "VSW7"   : ([0xE4, 0x70], 0.005865), #SW7 output voltage in V
            "ISW7"   : ([0xE4, 0x74], 0.001328), #SW7 output current in A
            "VSW8"   : ([0xE4, 0x80], 0.004311), #SW8 output voltage in V
            "ISW8"   : ([0xE4, 0x84], 0.001328), #SW8 output current in A
            "VSW9"   : ([0xE4, 0x90], 0.004311), #SW9 output voltage in V
            "ISW9"   : ([0xE4, 0x94], 0.001328), #SW9 output current in A
            "VSW10"  : ([0xE4, 0xA0], 0.004311), #SW10 output voltage in V
            "ISW10"  : ([0xE4, 0xA4], 0.001328), #SW10 output current in A
            "TBRD"   : ([0xE3, 0x08], 0.372434), #Motherboard temperature in K

            #Telemetry unique to 25-02452 and 01-02453 (CHECK THIS LATER) 
            "VBCR1"  : ([0xE1, 0x10], 0.0322581), #Voltage feeding BCR1 in V
            "IBCR1A" : ([0xE1, 0x14], 0.0009775), #Current BCR1 connector SA1A in A
            "IBCR1B" : ([0xE1, 0x15], 0.0009775), #Current BCR1 connector SA1B in B
            "TBCR1A" : ([0xE1, 0x18], 0.4963), #Array temperature connector SA1A in K
            "TBCR1B" : ([0xE1, 0x19], 0.4963), #Array temperature connector SA1B in K
            "SDBCR1A": ([0xE1, 0x1C], 1.59725), #Sun detector connector SA1A in W/m^2
            "SDBCR1B": ([0xE1, 0x1D], 1.59725), #Sun detector connector SA1B in W/m^2
            
            "VBCR2"  : ([0xE1, 0x20], 0.0322581), #Voltage feeding BCR2 in V
            "IBCR2A" : ([0xE1, 0x24], 0.0009775), #Current BCR2 connector SA2A in A
            "IBCR2B" : ([0xE1, 0x25], 0.0009775), #Current BCR2 connector SA2B in B
            "TBCR2A" : ([0xE1, 0x28], 0.4963), #Array temperature connector SA2A in K
            "TBCR2B" : ([0xE1, 0x29], 0.4963), #Array temperature connector SA2B in K
            "SDBCR2A": ([0xE1, 0x2C], 1.59725), #Sun detector connector SA2A in W/m^2
            "SDBCR2B": ([0xE1, 0x2D], 1.59725), #Sun detector connector SA2B in W/m^2

            "VBCR3"  : ([0xE1, 0x30], 0.0099706), #Voltage feeding BCR3 in V, can also be used to monitor input voltage from 5V USB CHG
            "IBCR3A" : ([0xE1, 0x34], 0.0009775), #Current BCR3 connector SA3A in A, can also be used to monitor input current from 5V USB CHG
            "IBCR3B" : ([0xE1, 0x35], 0.0009775), #Current BCR3 connector SA3B in B
            "TBCR3A" : ([0xE1, 0x38], 0.4963), #Array temperature connector SA3A in K
            "TBCR3B" : ([0xE1, 0x39], 0.4963), #Array temperature connector SA3B in K
            "SDBCR3A": ([0xE1, 0x3C], 1.59725), #Sun detector connector SA3A in W/m^2
            "SDBCR3B": ([0xE1, 0x3D], 1.59725), #Sun detector connector SA3B in W/m^2

        }
        # Format: self.eps.component_request(self.eps.component_request_args["REQUESTED INFORMATION"], component)
        self.component_request_args = {
            # PDM Control: Get information about PDMs and switch PDMs on and off to power on or off components
            "Pin Actual State": (0x54, 2),  # Reads and returns actual state of one PDM

            # PDM Timers: When enabled with timer restrictions, a PDM will remain on for only a set period of time.
            # By default each PDM does not have restrictions
            "PDM Timer Limit": (0x61, 2),  # Reads and returns timer limit for given PDM
            "PDM Timer Value": (0x62, 2),  # Reads and returns passed time since PDM timer was enabled
        }
        # Format: self.eps.command(self.eps.command_args["COMMAND"])
        self.command_args = {
            # Watchdog commands: Watchdog will reset the EPS after a period of time (default 4 minutes)
            # with no commands received.
            "Reset Watchdog": (0x22, [0x00]),  # Resets communications watchdog timer
            # Any command will reset the timer, this command can be used if no action from the EPS is needed

            # PDM Control: Get information about PDMs and switch PDMs on and off to power on or off components
            "All On": (0x40, [0x00]),  # Turn all PDMs on
            "All Off": (0x41, [0x00]),  # Turn all PDMs off
            "Set All Initial": (0x45, [0x00]),  # Set all PDMs to their initial state

            # Manual reset
            "Manual Reset": (0x80, [0x00]),  # Manually resets EPS to initial state, and increments manual reset counter
        }
        # Format: self.eps.component_command(self.eps.component_command_args["COMMAND"], component)
        self.component_command_args = {
            # PDM Control: Get information about PDMs and switch PDMs on and off to power on or off components
            "Pin On": 0x50,  # Enable component
            "Pin Off": 0x51,  # Disable component
            "Pin Init On": 0x52,  # Set initial state of component to "on"
            "Pin Init Off": 0x53,  # Set initial state of component to "off"
        }
        # PCM busses for the Bus Reset command
        # Combine as needed to reset multiple buses, e.g. 0x03 resets Battery and 5V
        self.pcm_busses = {
            "Battery": [0x01],
            "5V": [0x02],
            "3.3V": [0x04],
            "12V": [0x08],
        }

    def request(self, data) -> bytes:
        """
        Requests and returns uninterpreted bytes object
        :param data: data[0] = register, data[1] = data, data[2] = length
        :return: (byte) response from EPS
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, data[0], data[1])
            time.sleep(.5)
            result = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, data[2])
        return result

    def component_request(self, data, component: str) -> bytes:
        """
        Requests and returns uninterpreted bytes object from specific component
        :param data: data[0] = register, data[1] = length
        :param component: component to request information for
        :return: (byte) response from EPS
        """
        return self.request((data[0], self.components[component], data[1]))

    def telemetry_request(self, data) -> float:
        """
        Requests and returns interpreted telemetry data
        :param data: data[0] = TLE code, data[1] = multiplier
        :return: (float) telemetry value
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x10, data[0])
            time.sleep(.5)
            raw = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
            time.sleep(.5)
        return (raw[0] << 8 | raw[1]) * data[1]

    def command(self, data) -> bool:
        """
        Sends command to EPS
        :param data: data[0] = register, data[1] = data
        :return: (bool) whether command was successful
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, data[0], data[1])

    def component_command(self, register, component: str) -> bool:
        """
        Sends command to EPS targeting specific PDM
        :param register: register
        :param component: component to target
        :return: (bool) whether command was successful
        """
        return self.command((register, self.components[component]))

    # Watchdog commands: Watchdog will reset the EPS after a period of time (default 4 minutes)
    # with no commands received.
    def set_watchdog_period(self, period: bytes) -> bool:
        """
        Sets communications timeout watchdog period, minimum 1 minute maximum 90 minutes (REFER TO EPS MANUAL PG 48)
        :param period: (bytes) timeout period in minutes
        :return: (bool) whether set period was successful
        """
        return self.command((0x21, period))

    # PDM Timers: When enabled with timer restrictions, a PDM will remain on for only a set period of time.
    # By default each PDM does not have restrictions
    def set_timer_limit(self, component: str, period: bytes) -> bool:
        """
        Sets timer limit for given PDM
        :param component: Component to set timer limit for
        :param period: Period of time to set limit, increments of 30 seconds, with 0xFF setting the pin to indefinitely
        remain on and 0x00 setting the pin permanently off until set otherwise again (REFER TO EPS MANUAL PG 54)
        :return: (bool) whether set limit was successful
        """
        return self.command((0x60, [period[0], self.components[component][0]]))

    # PCM bus control:
    def bus_reset(self, pcm: [bytes]) -> bool:
        """
        Resets selected power buses by turning them off for 500ms then turning them back on
        :return: (bool) whether reset was successful
        """
        return self.command((0x70, pcm))