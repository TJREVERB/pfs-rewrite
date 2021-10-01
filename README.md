# pfs-rewrite

## A full flight software rewrite

The goal of this rewrite is to increase the simplicity, readability, and conciseness of the TJREVERB PFS. General structure overview is below:

1. **StateFieldRegistry** stores global variables that all parts of the PFS can access.
2. **main.py** executes **main_control_loop.py**.
3. **main_control_loop.py** iterates forever, reading input from its components and deciding what to do in each cycle.
   1. **command_registry** stores all the 3-digit codes we can send up from the ground station and the associated commands.
      1. **TST**: Test method, calls **log** and logs "Hello"
      2. **BVT**: Calls **eps.battery_voltage** and transmits the value to the ground station using **aprs.write** NEEDS TESTING
      3. **CHG**: Calls **charging_mode** and enters charging mode
      4. **SCI**: Calls **science_mode** and enters science mode
      5. **RST**: Calls **reset_power** and power resets the entire cubesat
   2. The **reset_power** method calls **eps.all_off** to disable all PDMs and then **eps.bus_reset** to reset power NEEDS TESTING
   3. The **log** method writes argument to file log.txt
   4. The **run** method calls **execute** in an infinite loop.
   5. The **charging_mode** method calls **eps.pin_off** to disable Iridium
   6. The **science_mode** method calls **eps.pin_on** to enable Iridium
   7. The **execute** method first reads in data from our components, then decides what to do with that information.
      1. **aprs.read** NEEDS TESTING
      2. **command_interpreter**
         1. The **command_interpreter** method takes the APRS message in the **StateFieldRegistry** (if any) and executes the command sent by the ground station if it’s in the **command_registry**. Logs result using **log** method.
      3. **battery_voltage**
         1. Reads battery voltage from eps and switches to charging mode or science mode depending on value
            1. **charging_mode** disables Iridium NEEDS TESTING
            2. **science_mode** enables Iridium NEEDS TESTING
4. **aprs.py** contains all code pertaining to the APRS.
   1. The **read** method reads and returns a message received over the APRS, and adds it to the **StateFieldRegistry**. NEEDS TESTING
   2. The **write** method transmits a message through the APRS. NEEDS TESTING
   3. The **functional** method tests if the component is connected properly and responsive to commands NEEDS TESTING, NOT FULLY IMPLEMENTED
5. **eps.py** contains all code pertaining to the EPS.
   1. The **components** dictionary contains a list of all components connected to the EPS and their respective PDMs
   2. The **battery_voltage** method reads and returns the current battery voltage.
6. **antenna_deployer.py** contains all code pertaining to the antenna
   1. Does not contain a read method, only a control method. control checks if 30 minutes have elapsed by checking the start time in the state field registry. 
   2. If 30 minutes have elapsed and the antenna has not already been deployed, then it deploys the antenna. Code to actually deploy still needs to be written. 
   3. The **pin_on** method enables a particular component
   4. The **pin_off** method disables a particular component
   5. The **all_on** method enables all PDM powered components
   6. The **all_off** method disables all PDM powered components
   7. The **bus_reset** method resets the 3.3V, 5V, 12V, and Battery power buses (which includes the flight computer), turning off for 0.5s then back on

For more details on each specific part of the PFS, refer to the comments within the code. This README will be kept as up-to-date as possible.
