class MODE:

    #initialization: turn on any necessary devices using EPS, initialize any instance variables, etc.
    # Turns off any power-intensive devices not needed by this mode (just in case)
    def __init__(self):
        self.conditions = {}  # Dictionary storing conditions for switch, updated via check_conditions
        pass

    #checks the conditions this mode requires, for example a minimum battery voltage
    #store any mode conditions as instance variables so that you only have to retrieve them once, and can then use them in switch_modes right after if necessary
    #RETURN: True if conditions are met, False otherwise
    # DO NOT SWITCH MODES IF FALSE - this is up to the main control loop to decide
    def check_conditions(self):
        pass
    
    #execute one iteration of this mode, for example: read from the radio and retrieve EPS telemtry one time
    #this method should take care of reading from the radio and executing commands (which is happening in basically all of the modes)
    #NOTE: receiving and executing commmands is not up to the main control loop because different modes might do this in different manners
    #save any values to instance varaibles if they may be necessary in future execute_cycle calls
    def execute_cycle(self):
        pass

    #If conditions (from the check_conditions method) for a running mode are not met, it will choose which new mode to switch to. 
    #THIS SHOULD ONLY BE CALLED FROM MAIN CONTROL LOOP
    #This is a mode specific switch, meaning the current mode chooses which new mode to switch to based only on the current mode's conditions.
    #This method does not handle manual override commands from the groundstation to switch to specific modes, that's handled by the Main Control Loop.
    def switch_modes(self):
        pass      

    #Safely terminates the current mode:
    #Turns off any non-essential devices that were turned on (non-essential meaning devices that other modes might not need, so don't turn off the flight pi...)
    #delete (using del) any memory-expensive instance variables so that we don't have to wait for python garbage collector to clear them out
    #RETURN: True if it was able to be terminated to a safe extent, False otherwise (safe extent meaning it's safe to switch to another mode)
    #NOTE: This should be standalone, so it can be called by itself on a mode object, but it should also be used in switch_modes
    def terminate_mode(self):
        pass
