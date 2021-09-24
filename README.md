# pfs-rewrite

## A full flight software rewrite

The goal of this rewrite is to increase the simplicity, readability, and conciseness of the TJREVERB PFS. General structure overview is below:

1. **StateFieldRegistry** stores global variables that all parts of the PFS can access.
2. **main.py** executes **main_control_loop.py**.
3. **main_control_loop.py** iterates forever, reading input from its components and deciding what to do in each cycle.
   1. **command_registry** stores all the 3-digit codes we can send up from the ground station and the associated commands.
      1. **TST**: Test method, prints “hello”.
      2. **BVT**: Calls **eps.battery_voltage** and transmits the value to the ground station using **aprs.write**.
   2. The **run** method calls **execute** in an infinite loop.
   3. The **execute** method first reads in data from our components, then decides what to do with that information.
      1. **aprs.read**
      2. **command_interpreter**
         1. The **command_interpreter** method takes the APRS message in the **StateFieldRegistry** (if any) and executes the command sent by the ground station if it’s in the **command_registry**.
4. **aprs.py** contains all code pertaining to the APRS.
   1. The **read** method reads and returns a message received over the APRS, and adds it to the **StateFieldRegistry**.
   2. The **write** method transmits a message through the APRS.
5. **eps.py** contains all code pertaining to the EPS.
   1. The **battery_voltage** method reads and returns the current battery voltage.

For more details on each specific part of the PFS, refer to the comments within the code. This README will be kept as up-to-date as possible.