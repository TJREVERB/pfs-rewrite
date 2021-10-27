import time
from MainControlLoop.Drivers.eps import EPS
from MainControlLoop.Drivers.aprs import APRS
from MainControlLoop.Drivers.iridium import Iridium
from MainControlLoop.Drivers.imu import IMU
from MainControlLoop.Drivers.antenna_deployer.AntennaDeployer import AntennaDeployer


class Mode:

    #initialization: turn on any necessary devices using EPS, initialize any instance variables, etc.
    # Turns off any power-intensive devices not needed by this mode (just in case)
    def __init__(self, sfr, conditions):
        self.LOWER_THRESHOLD = 6  # Lower battery voltage threshold for switching to CHARGING mode
        self.UPPER_THRESHOLD = 8  # Upper battery voltage threshold for switching to SCIENCE mode
        self.previous_time = 0
        self.sfr = sfr
        self.eps = EPS(sfr)
        self.aprs = APRS(sfr)
        self.iridium = Iridium(sfr)
        self.antenna_deployer = AntennaDeployer(sfr)
        self.imu = IMU(sfr)
        self.command_registry = {
            "TST": lambda: self.iridium.commands["Transmit"]("TJ;Hello"),  # Test method, transmits "Hello"
            # Reads and transmits battery voltage
            "BVT": lambda: self.iridium.commands["Transmit"]("TJ;" + str(self.eps.telemetry["VBCROUT"]())),
            # TODO: MANUAL MODE SWITCHING
            "CHG": self.charging_mode(),  # Enters charging mode
            "SCI": self.science_mode(self.NUM_DATA_POINTS, self.NUM_SCIENCE_MODE_ORBITS),  # Enters science mode
            "OUT": self.outreach_mode,  # Enters outreach mode
            "U": lambda value: setattr(self, "UPPER_THRESHOLD", value),  # Set upper threshold
            "L": lambda value: setattr(self, "LOWER_THRESHOLD", value),  # Set lower threshold
            # Reset power to the entire satellite (!!!!)
            "RST": lambda: [i() for i in [
                lambda: self.eps.commands["All Off"],
                lambda: time.sleep(.5),
                lambda: self.eps.commands["Bus Reset"], (["Battery", "5V", "3.3V", "12V"])
            ]],
            # Transmit proof of life through Iridium to ground station
            "IRI": lambda: self.iridium.wave(self.eps.telemetry["VBCROUT"](),
                                             self.eps.solar_power(),
                                             self.eps.total_power()),
            # Transmit total power draw of connected components
            "PWR": lambda: self.iridium.commands["Transmit"]("TJ;" + str(self.eps.total_power(3)[0])),
            # Calculate and transmit Iridium signal strength variability
            "SSV": lambda: self.iridium.commands["Transmit"]("TJ;SSV:" + str(self.sfr.signal_strength_variability())),
            # Transmit current solar panel production
            "SOL": lambda: self.iridium.commands["Transmit"]("TJ;SOL:" + str(self.eps.solar_power())),
            "TBL": lambda: self.aprs.write("TJ;" + self.imu.getTumble())  # Test method, transmits tumble value
        }
        # Dictionary storing conditions for switch, updated via check_conditions
        self.conditions = conditions

    #checks the conditions this mode requires, for example a minimum battery voltage
    #store any mode conditions as instance variables so that you only have to retrieve them once, and can then use them in switch_modes right after if necessary
    #RETURN: True if conditions are met, False otherwise
    # DO NOT SWITCH MODES IF FALSE - this is up to the main control loop to decide
    # implemented for the seach specific mode
    def check_conditions(self):
        pass
    
    #execute one iteration of this mode, for example: read from the radio and retrieve EPS telemtry one time
    #this method should take care of reading from the radio and executing commands (which is happening in basically all of the modes)
    #NOTE: receiving and executing commmands is not up to the main control loop because different modes might do this in different manners
    #save any values to instance varaibles if they may be necessary in future execute_cycle calls
    #this method is called in each specific mode before specific execute_cycle for that code
    def execute_cycle(self):
        self.integrate_charge()

    #If conditions (from the check_conditions method) for a running mode are not met, it will choose which new mode to switch to. 
    #THIS SHOULD ONLY BE CALLED FROM MAIN CONTROL LOOP
    #This is a mode specific switch, meaning the current mode chooses which new mode to switch to based only on the current mode's conditions.
    #This method does not handle manual override commands from the groundstation to switch to specific modes, that's handled by the Main Control Loop.
    # implemented for the specific modes
    def switch_modes(self):
        pass

    #Safely terminates the current mode:
    #Turns off any non-essential devices that were turned on (non-essential meaning devices that other modes might not need, so don't turn off the flight pi...)
    #delete (using del) any memory-expensive instance variables so that we don't have to wait for python garbage collector to clear them out
    #RETURN: True if it was able to be terminated to a safe extent, False otherwise (safe extent meaning it's safe to switch to another mode)
    #NOTE: This should be standalone, so it can be called by itself on a mode object, but it should also be used in switch_modes
    def terminate_mode(self):
        del self.eps
        del self.aprs
        del self.iridium
        del self.antenna_deployer
        del self.imu

    def integrate_charge(self):
        """
        Integrate charge in Joules
        """
        draw = self.eps.total_power(4)[0]
        gain = self.eps.solar_power()
        self.sfr.BATTERY_CAPACITY_INT -= (draw - gain) * (time.perf_counter() - self.previous_time)
        self.previous_time = time.perf_counter()

    def systems_check(self) -> list:
        """
        Performs a complete systems check and returns a list of component failures
        DOES NOT SWITCH ON PDMS!!! SWITCH ON PDMS BEFORE RUNNING!!!
        TODO: implement system check of antenna deployer
        TODO: account for different exceptions in .functional() and attempt to troubleshoot
        :return: list of component failures
        """
        result = []
        if not self.aprs.functional: result.append("APRS")
        if not self.iridium.functional: result.append("Iridium")
        return result
