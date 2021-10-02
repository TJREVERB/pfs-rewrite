# pfs-rewrite

## A full flight software rewrite

The goal of this rewrite is to increase the simplicity, readability, and conciseness of the TJREVERB PFS. General structure overview is below:

1. **StateFieldRegistry** stores global variables that all parts of the PFS can access.
   1. **StateFieldLogger** is a more permanent version of the state field; it stores the values in a file
      1. The values can be found in the `LOG_PATH` variable. Right now it is `./MainControlLoop/lib/StateFieldRegistry/data/state_field_log.txt`
      2. If the pi crashes in space, when the pfs is ran again, it can directly use the last saved variables in the state field instead of completely rebooting the system. It will load the variables from the file. 
      3. StateFieldLogger saves the variables in the statefield every 200 iterations. This can be changed easily through the variable `DUMP_ITERATION`
      4. Additional Notes:
         1. If a value is of type bool, in the state_field_log.txt file, it must have an empty value. This is because Python will convert all strings except the empty string to True. For example, `ANTENNA_DEPLOYED:`, not `ANTENNA_DEPLOYED:False`
3. **main.py** executes **main_control_loop.py**.
4. **main_control_loop.py** iterates forever, reading input from its components and deciding what to do in each cycle.
   1. **command_registry** stores all the 3-digit codes we can send up from the ground station and the associated commands.
      1. **TST**: Test method, calls **log** and logs "Hello"
      2. **BVT**: Calls **eps.battery_voltage** and transmits the value to the ground station using **aprs.write** NEEDS TESTING
      3. **CHG**: Calls **charging_mode** and enters charging mode
      4. **SCI**: Calls **science_mode** and enters science mode
      5. **RST**: Calls **reset_power** and power resets the entire cubesat
   2. The **reset_power** method disables all PDMs and then resets power to all busses NEEDS TESTING
   3. The **log** method writes argument to file log.txt
   4. The **run** method calls **execute** in an infinite loop.
   5. The **charging_mode** method disables Iridium
   6. The **science_mode** method enables Iridium
   7. The **execute** method first reads in data from our components, then decides what to do with that information.
      1. **aprs.read**
      2. **command_interpreter**
         1. The **command_interpreter** method takes the APRS message in the **StateFieldRegistry** (if any) and executes the command sent by the ground station if it’s in the **command_registry**. Logs result using **log** method.
      3. **battery_voltage**
         1. Reads battery voltage from eps and switches to charging mode or science mode depending on value
            1. **charging_mode** disables Iridium NEEDS TESTING
            2. **science_mode** enables Iridium NEEDS TESTING
5. **aprs.py** contains all code pertaining to the APRS.
   1. The **read** method reads and returns a message received over the APRS, and adds it to the **StateFieldRegistry**.
   2. The **write** method transmits a message through the APRS.
   3. The **functional** method tests if the component is connected properly and responsive to commands NEEDS TESTING, NOT FULLY IMPLEMENTED
6. **eps.py** contains all code pertaining to the EPS.
   1. The **components** dictionary contains a list of all components connected to the EPS and their respective PDMs.

      1. “APRS”: APRS
      2. “Iridium”: Iridium
      3. “Antenna Deployer”: Antenna deployer NOT FULLY IMPLEMENTED
   2. The **request_args** dictionary contains a list of arguments for the **request** method. The arguments will determine what data is requested from the EPS. The data is in a raw, uninterpreted bytes format. Refer to pages 40-50 on the EPS manual for more information on EPS commands.

      1. Board Info Commands: Basic board information.

         1. “Board Status”: Reads and returns board status
         2. “Last Error”: Reads and returns last error
         3. “Firmware Version”: Reads and returns firmware version
         4. “Checksum”: Reads and returns generated checksum of ROM contents
         5. “Firmware Revision”: Reads and returns firmware revision number
         6. “Battery Voltage”: Reads and returns battery voltage
      2. Watchdog Commands: Watchdog will reset the EPS after a period of time (default 4 minutes) with no commands received.

         1. “Watchdog Period”: Reads and returns current watchdog period
      3. Reset Count Commands: The EPS resets under various conditions. These commands return the number of times the EPS has reset due to each condition. Counts roll over from 255 to 0.
         1. “Brownout Resets”: Reads and returns number of brownout resets
         2. “Software Resets”: Reads and returns number of software resets
         3. “Manual Resets”: Reads and returns number of manual resets
         4. “Watchdog Resets”: Reads and returns number of watchdog resets
      4. PDM Control: Get information about PDMs and switch PDMs on and off to control power to components.
         1. “All Actual States”: Reads and returns actual state of all PDMs in byte form. PDMs may be shut off due to protections, and this command shows the actual state of all PDMs.
         2. “All Expected States”: Reads and returns expected state of all PDMs in byte form. These depend on whether they have been commanded on or off, regardless of protection trips.
         3. “All Initial States”: Reads and returns initial states of all PDMs in byte form. These are the states the PDMs will be in after a reset.
   3. The **component_request_args** dictionary contains a list of arguments for the **component_request** method. The arguments will determine what data is requested from the EPS. The data is in a raw, uninterpreted bytes format. Refer to pages 40-50 on the EPS manual for more information on EPS commands.
      1. PDM Control: Get information about PDMs and switch PDMs on and off to control power to components.
         1. “Pin Actual State”: Reads and returns actual state of one PDM
      2. PDM Timers: When enabled with timer restrictions, a PDM will remain on for only a set period of time. By default each PDM does not have restrictions.
         1. “PDM Timer Limit”: Reads and returns timer limit for given PDM
         2. “PDM Timer Value”: Reads and returns passed time since PDM timer was enabled
   4. The **command_args** dictionary contains a list of arguments for the **command** method. The arguments will determine what command is sent to the EPS. Refer to pages 40-50 on the EPS manual for more information on EPS commands.
      1. Watchdog Commands: Watchdog will reset the EPS after a period of time (default 4 minutes) with no commands received.
         1. “Reset Watchdog”: Resets communications watchdog timer. Any command will reset the timer, this command can be used if no action from the EPS is needed.
      2. PDM Control: Get information about PDMs and switch PDMs on and off to control power to components.
         1. “All On”: Turn all PDMs on
         2. “All Off”: Turn all PDMs off
         3. “Set All Initial”: Set all PDMs to their initial state
      3. Manual Reset
         1. “Manual Reset”: Manually resets EPS to initial state, and increments manual reset counter
   5. The **component_command_args** dictionary contains a list of arguments for the **component_command** method. The arguments will determine what command is sent to the EPS. Refer to pages 40-50 on the EPS manual for more information on EPS commands.
      1. PDM Control: Get information about PDMs and switch PDMs on and off to control power to components.
         1. “Pin On”: Enable component
         2. “Pin Off”: Disable component
         3. “Pin Init On”: Set initial state of component to “on”
         4. “Pin Init Off”: Set initial state of component to “off”
   6. The **pcm_busses** dictionary contains a list of values for each of the busses on the EPS. Used for the **bus_reset** method. To reset multiple busses, add the values for each bus to be reset and send the result to **bus_reset**.
   7. The **request** method requests and returns an uninterpreted bytes object from the EPS. Call request(request_args[“REQUESTED INFORMATION”]).
   8. The **component_request** method requests and returns an uninterpreted bytes object from a specific PDM. Call component_request(component_request_args[“REQUESTED INFORMATION”], COMPONENT).
   9. The **command** method sends a command to the EPS. Call command(command_args[“COMMAND”]).
   10. The **component_command** method sends a command to the EPS targeted at a specific component. Call component_command(component_command_args[“COMMAND”], COMPONENT).
   11. Other commands:
       1. The **set_watchdog_period** method sets the communications timeout period for the watchdog timer. 1 minute minimum, 90 minute maximum, 4 minute default.
       2. The **set_timer_limit** method sets the timer limit for a given PDM. This is the time the PDM is allowed to remain on before being switched off automatically by the EPS. The **period** argument defines how long to set the limit in increments of 30 seconds. 0xFF sets the time limit indefinitely, forcing the pin to remain on at all times, and 0x00 sets the time limit to 0, forcing the pin to remain off unless set again.
       3. The **bus_reset** method resets the selected power busses by turning them off for a half second and turning them back on. The **pcm_busses** dictionary lists the values for each of the EPS’ busses.
   12. The **battery_voltage** method reads and returns the current battery voltage, interpreted into a usable number.
6. **antenna_deployer.py** contains all code pertaining to the antenna.
   1. The **deploy** method deploys the antenna.
   2. The **control** method deploys the antenna if 30 minutes have elapsed and the antenna is not already deployed.
7. **iridium.py** contians all code pertaining to the Iridium.
   1. The **commands** dictionary contains a list of all commands which can be sent to the Iridium.
      1. “Test”: Tests iridium by sending “AT”. Correct reply is “OK”.
      2. “Geolocation”: NOT UNDERSTOOD
      3. “Active Config”: NOT UNDERSTOOD
      4. “Check Registration”: NOT UNDERSTOOD
      5. “Phone Model”: NOT UNDERSTOOD
      6. “Phone Revision”: NOT UNDERSTOOD
      7. “Phone IMEI”: NOT UNDERSTOOD
      8. “Check Network”: NOT UNDERSTOOD
      9. “Shut Down”: NOT UNDERSTOOD
      10. “Signal Quality”: Returns strength of satellite signal.
      11. “Send SMS”: NOT UNDERSTOOD
      12. “SBD Ring Alert On”: NOT UNDERSTOOD
      13. “SBD Ring Alert Off”: NOT UNDERSTOOD
      14. “Battery Check”: NOT UNDERSTOOD
      15. “Call Status”: NOT UNDERSTOOD
      16. “Soft Reset”: NOT UNDERSTOOD
   2. The **functional** method verifies that the serial port is open and that sending AT returns OK.
   3. The **request** method requests information from the Iridium and returns the parsed response.
   4. The **write** method writes a command to the Iridium.
   5. The **read** method reads in as many bytes as are available from the Iridium, serial timeout permitting.

For more details on each specific part of the PFS, refer to the comments within the code. This README will be kept as up-to-date as possible.
