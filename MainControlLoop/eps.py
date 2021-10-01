from MainControlLoop.lib.StateFieldRegistry.registry import StateFieldRegistry
from smbus2 import SMBusWrapper
#from smbus2 import SMBus
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
            "AntennaDeployer": ""
        }

    #BOARD INFO COMMANDS
    def board_status(self) -> bytes:
        """
        Reads and returns board status
        :return: (byte) board status (REFER TO EPS MANUAL PG 40)
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x01, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data

    def last_error(self) -> bytes:
        """
        Reads and returns last error
        :return: (bytes) details about last error (REFER TO EPS MANUAL PG 41)
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x03, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data
    
    def get_firmware_version(self) -> bytes:
        """
        Reads and returns firmware version
        :return: (bytes) uninterpreted firmware version (REFER TO EPS MANUAL PG 41)
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x04, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data

    def get_checksum(self) -> bytes:
        """
        Reads and returns generated checksum of ROM contents
        :return: (bytes) uninterpreted checksum (REFER TO EPS MANUAL PG 42)
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x05, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data

    def get_firmware_rev(self) -> bytes:
        """
        Reads and returns firmware revision number
        :return: (bytes) uninterpreted firmware version number (REFER TO EPS MANUAL PG 42)
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x06, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data
    #END BOARD INFO

    #TODO: IMPLEMENT GET TELEMETRY (0x10) FOR INFORMATION OTHER THAN BATTERY VOLTAGE

    def battery_voltage(self) -> float:
        """
        Reads and returns current battery voltage
        :return: (float) battery voltage
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x10, [0xE2, 0x80])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
            time.sleep(0.5)
            adc_count = (data[0] << 8 | data[1]) * .008993157
        return adc_count

    #Watchdog commands: Watchdog will reset the EPS after a period of time (default 4 minutes) with no commands recieved.
    def get_watchdog_period(self) -> bytes:
        """
        Reads and returns current watchdog period
        :return: (bytes) watchdog timeout period in minutes
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x20, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data

    def set_watchdog_period(self, period: bytes) -> bool:
        """
        Sets communications timeout watchdog period, minimum 1 minute maximum 90 minutes (REFER TO EPS MANUAL PG 48)
        :param period: (bytes) timeout period in minutes
        :return: (bool) whether set period was successful
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x21, period)
    
    def reset_watchdog(self) -> bool:
        """
        Resets communications watchdog timer
        Any command will reset the timer, this command can be used if no action from the EPS is needed
        :return: (bool) whether reset was successful
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x22, [0x00])

    #End watchdog commands

    #Reset count commands: EPS will be reset under various conditions, these functions check how many times have been caused by each condition
    def get_brownout_reset(self) -> bytes:
        """
        Reads and returns number of brownout resets
        Counter rolls over from 255 to 0
        :return: (bytes) number of brownout resets
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x31, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data

    def get_software_reset(self) -> bytes:
        """
        Reads and returns number of times EPS microcontroller has malfunctioned and reset
        Counter rolls over from 255 to 0
        :return: (bytes) number of brownout resets
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x32, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data

    def get_manual_reset(self) -> bytes:
        """
        Reads and returns number of times EPS has been reset manually
        Counter rolls over from 255 to 0
        :return: (bytes) number of manual resets
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x33, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data

    def get_watchdog_reset(self) -> bytes:
        """
        Reads and returns number of times EPS has been reset by watchdog timer
        Counter rolls over from 255 to 0
        :return: (bytes) number of EPS resets from watchdog timer
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x34, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data

    #End reset count commands

    #PDM Control: Get information about PDMs and switch PDMs on and off to power on or off components
    def all_on(self) -> bool:
        """
        Turn all PDMs on
        :return: (bool) whether PDM on succeeded
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x40, [0x00])

    def all_off(self) -> bool:
        """
        Turn all PDMs off
        :return: (bool) whether PDM off succeeded
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x41, [0x00])

    def all_actual_states(self) -> bytes:
        """
        Reads and returns actual state of all PDMs in byte form
        PDMs may be shut off due to protections, and this command shows the actual state of all PDMs
        :return: (bytes) uninterpreted PDM states (REFER TO EPS MANUAL PG 50)
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x42, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 4)
        return data

    def all_expected_states(self) -> bytes:
        """
        Reads and returns expected state of all PDMs in byte form
        These depend on whether they have been commanded on or off, regardless of protection trips
        :return: (bytes) uninterpreted PDM states (REFER TO EPS MANUAL PG 50)
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x43, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 4)
        return data

    def all_initial_states(self) -> bytes:
        """
        Reads and returns initial states of all PDMs in byte form
        These are the states the PDMs will be in after a reset
        :return: (bytes) uninterpreted PDM states (REFER TO EPS MANUAL PG 50)
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x44, [0x00])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 4)
        return data
    
    def set_all_initial(self) -> bool:
        """
        Sets all PDMs to their initial states
        :return: (bool) whether set PDMs was successful
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x45, [0x00])

    def pin_on(self, component: str) -> bool:
        """
        Enable component
        :param component: Component to enable
        :return: (bool) whether enable component succeeded
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x50, self.components[component])

    def pin_off(self, component: str) -> bool:
        """
        Disable component
        :param component: Component to disable
        :return: (bool) whether disable component succeeded
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x51, self.components[component])

    def pin_init_on(self, component: str) -> bool:
        """
        Sets initial state of component PDM on
        :param component: Component to set
        :return: (bool) whether set component initial state was successful
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x52, self.components[component])

    def pin_init_off(self, component: str) -> bool:
        """
        Sets initial state of component PDM off
        :param component: Component to set
        :return: (bool) whether set component initial state was successful
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x53, self.components[component])

    def pin_actual_state(self, component: str) -> bytes:
        """
        Reads and returns actual state of PDM (same as all_actual_states but for one individual pin)
        :param component: Component state to read
        :return: (byte) uninterpreted actual state of PDM
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x54, self.components[component])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data

    #End PDM control

    #PDM Timers: When enabled with timer restrictions, a PDM will remain on for only a set period of time. By default each PDM does not have restrictions
    def set_timer_limit(self, component: str, period: bytes) -> bool:
        """
        Sets timer limit for given PDM
        :param component: Component to set timer limit for
        :param period: Period of time to set limit, increments of 30 seconds, with 0xFF setting the pin to indefinitely remain on and 0x00 setting the pin permanently off until set otherwise again (REFER TO EPS MANUAL PG 54)
        :return: (bool) whether set limit was successful
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x60, [period[0], self.components[component][0]])

    def get_timer_limit(self, component: str) -> bytes:
        """
        Reads and returns timer limit for given PDM
        :param component: Component to read timer limit from
        :return: (bytes) uninterpreted timer limit, increments of 30 seconds
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x61, self.components[component])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data

    def get_timer_value(self, component: str) -> bytes:
        """
        Reads and returns passed time since PDM timer was enabled
        :param component: Component to read timer value from
        :return: (bytes) current timer value, increments of 30 seconds
        """
        with SMBusWrapper(1) as bus:
            bus.write_i2c_block_data(self.EPS_ADDRESS, 0x62, self.components[component])
            time.sleep(0.5)
            data = bus.read_i2c_block_data(self.EPS_ADDRESS, 0, 2)
        return data
    
    #End PDM Timer control

    #PCM BUS CONTROL:
    def bus_reset(self, pcm: bytes) -> bool:
        """
        Resets selected power buses by turning them off for 500ms then turning them back on
        :param pcm: bus to reset
        0x01 Batt
        0x02 5V
        0x04 3V3
        0x08 12V
        Combine as needed to reset multiple buses, e.g. 0x03 resets BATT and 5V
        :return: (bool) whether reset was successful
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x70, pcm)

    #END PCM BUS CONTROL

    #MANUAL RESET
    def man_reset(self) -> bool:
        """
        Manually resets EPS to initial state, and increments manual reset counter
        :return: (bool) whether EPS was reset successfully
        """
        with SMBusWrapper(1) as bus:
            return bus.write_i2c_block_data(self.EPS_ADDRESS, 0x80, [0x00])
    
    #END MANUAL RESET

