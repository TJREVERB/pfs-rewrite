# pFS-rewrite

## A full flight software rewrite

The goal of this rewrite is to increase the simplicity, readability, and conciseness of the TJREVERB PFS. General structure overview is below:

1. **registry.py** contains code for the **StateFieldRegistry**.
   1. **StateFieldRegistry** stores global variables that all parts of the PFS can access.
      1. **\_\_init\_\_**
         1. On instantiation, **StateFieldRegistry** attempts to read log file and set object attributes to the saved values. If this fails, it sets object attributes to the dictionary of **defaults**. NEEDS TESTING
         2. START_TIME is always set to the current time. This is because deploying the antenna later is better than deploying it early.
      2. **to_dict** returns a dictionary containing the **StateFieldRegistry’s** variables and values. NEEDS TESTING
      3. **dump** writes the current values of the **StateFieldRegistry** to the log file. NEEDS TESTING
      4. **reset** clears the log file so that on the next boot, **StateFieldRegistry** sets object attributes to default values. NEEDS TESTING
   2. **data/state_field_log.txt** contains a backup of the **StateFieldRegistry** in case the pi crashes in space.
2. **main.py** calls **run** in **main_control_loop.py**.
3. **main_control_loop.py** iterates forever, reading input from its components and deciding what to do in each cycle. The following are the attributes of the **MainControlLoop** class.
   1. **command_registry** stores all the 3-digit codes we can send up from the ground station and the associated lambda functions. Format: `self.command_registry[COMMAND]()`
      1. “TST”: Test method, calls **log** and logs "Hello" NEEDS TESTING
      2. “BVT”: Retrieves battery voltage from EPS and transmits the value to the ground station using **aprs.write**
      3. “CHG”: Calls **charging_mode** and enters charging mode NEEDS TESTING
      4. “SCI”: Calls **science_mode** and enters science mode NEEDS TESTING
      5. “U00”: Sets minimum battery voltage for when satellite will enter SCIENCE mode. Second character determines ones digit, third character determines tenths digit. NEEDS TESTING
      6. “L00”: Sets maximum battery voltage for when satellite will enter CHARGING mode. Second character determines ones digit, third character determines tenths digit. NEEDS TESTING
      7. “RST”: Calls **reset_power** and power resets the entire cubesat NEEDS TESTING
      8. “IRI”: Calls **iridium.wave** and transmits a simple hardcoded message back to the ground station over Iridium
      9. “PWR”: Retrieves total power draw from EPS and transmits the result using **aprs.write** NEEDS TESTING
   2. The **log** method calls **sfr.dump**, saving the current state of the **StateFieldRegistry**. This is a separate method in order to easily comment out logging across the entire satellite when testing and debugging.
   3. The **charging_mode** method disables Iridium
   4. The **science_mode** method enables Iridium
   5. The **command_interpreter** method takes the APRS message in the **StateFieldRegistry** (if any) and executes the command sent by the ground station if it’s in the **command_registry**. Logs the result in **log.txt**.
   6. The **on_start** method runs exactly once, when the satellite is in STARTUP mode, directly after the deployment switch is depressed.
      1. Switches off all PDMs to conserve power.
      2. Waits 30 minutes, then deploys the antenna and updates **sfr.ANTENNA_DEPLOYED**.
      3. Calls **log** to dump **StateFieldRegistry**.
      4. Switches off antenna deployer and switches on APRS to receive messages. Satellite is now in the equivalent of CHARGING mode.
      5. Waits for battery to charge up to the upper threshold before proceeding to IOC mode.
      6. Switches mode to IOC and calls **log** to dump **StateFieldRegistry**.
   7. The **ioc** method runs exactly once, directly after the satellite has left STARTUP mode.
      1. Switches on all PDMs.
      2. Calls **iridium.wave** to send hardcoded message down to groundstation over Iridium, completing mission objective of testing Iridium.
      3. Enters either CHARGING or SCIENCE mode depending on remaining battery voltage.
   8. The **execute** method first reads in data from our components, then decides what to do with that information.
      1. **aprs.read**
      2. Requests battery voltage from EPS
      3. **command_interpreter**
      4. Switches to CHARGING mode or SCIENCE mode depending on value
      5. **log**
   9. The **run** method is called by **main** on satellite boot.
      1. Sets START_TIME in **sfr**.
      2. Calls **on_startup** if in STARTUP mode.
      3. Calls **ioc** if in IOC mode.
      4. Calls **execute** in an infinite loop.
4. **aprs.py** contains all code pertaining to the APRS.
   1. The **read** method reads and returns a message received over the APRS, and adds it to the **StateFieldRegistry**.
   2. The **write** method transmits a message through the APRS.
   3. The **functional** method tests if the component is connected properly and responsive to commands NEEDS TESTING, NOT FULLY IMPLEMENTED
5. **eps.py** contains all code pertaining to the EPS.
   1. The **components** dictionary contains a list of all components connected to the EPS and their respective PDMs.

      1. “APRS”: APRS
      2. “Iridium”: Iridium
      3. “Antenna Deployer”: Antenna deployer
   2. The **commands** dictionary contains a list of lambda functions to request data from and send commands to the EPS. The returned data (for request commands) is in a raw, uninterpreted bytes format. Refer to pages 40-50 on the EPS manual for more information on EPS commands. Format: `self.eps.commands[COMMAND]()`

      1. Board Info Commands: Basic board information.

         1. “Board Status”: Reads and returns board status
         2. “Last Error”: Reads and returns last error
         3. “Firmware Version”: Reads and returns firmware version
         4. “Checksum”: Reads and returns generated checksum of ROM contents
         5. “Firmware Revision”: Reads and returns firmware revision number
         6. “Battery Voltage”: Reads and returns battery voltage
      2. Watchdog Commands: Watchdog will reset the EPS after a period of time (default 4 minutes) with no commands received.

         1. “Watchdog Period”: Reads and returns current watchdog period
         2. “Reset Watchdog”: Resets communications watchdog timer. Any command will reset the timer, this command can be used if no action from the EPS is needed.
      3. Reset Count Commands: The EPS resets under various conditions. These commands return the number of times the EPS has reset due to each condition. Counts roll over from 255 to 0.
         1. “Brownout Resets”: Reads and returns number of brownout resets
         2. “Software Resets”: Reads and returns number of software resets
         3. “Manual Resets”: Reads and returns number of manual resets
         4. “Watchdog Resets”: Reads and returns number of watchdog resets
      4. PDM Control: Get information about PDMs and switch PDMs on and off to control power to components.
         1. “All Actual States”: Reads and returns actual state of all PDMs in byte form. PDMs may be shut off due to protections, and this command shows the actual state of all PDMs.
         2. “All Expected States”: Reads and returns expected state of all PDMs in byte form. These depend on whether they have been commanded on or off, regardless of protection trips.
         3. “All Initial States”: Reads and returns initial states of all PDMs in byte form. These are the states the PDMs will be in after a reset.
         4. “Pin Actual State”: Reads and returns actual state of one PDM
         5. “All On”: Turn all PDMs on
         6. “All Off”: Turn all PDMs off
         7. “Set All Initial”: Set all PDMs to their initial state
         8. “Pin On”: Enable component
         9. “Pin Off”: Disable component
         10. “Pin Init On”: Set initial state of component to “on”
         11. “Pin Init Off”: Set initial state of component to “off”
      5. PDM Timers: When enabled with timer restrictions, a PDM will remain on for only a set period of time. By default each PDM does not have restrictions.
         1. “PDM Timer Limit”: Reads and returns timer limit for given PDM
         2. “PDM Timer Value”: Reads and returns passed time since PDM timer was enabled
      6. Manual Reset
         1. “Manual Reset”: Manually resets EPS to initial state, and increments manual reset counter.
   3. The **telemetry** dictionary contains a list of lambda functions which request and return interpreted telemetry from the EPS. Format: `self.eps.telemetry[TELEMETRY]()` NOT ALL COMMANDS UNDERSTOOD
      1. “IBCROUT”: Battery current
      2. “VBCROUT”: Battery voltage
      3. See comments in code for full documentation
   4. The **pcm_busses** dictionary contains a list of values for each of the busses on the EPS. Used for the **bus_reset** method. To reset multiple busses, add the values for each bus to be reset and send the result to **bus_reset**.
   5. The **request** method requests and returns an uninterpreted bytes object from the EPS.
   6. The **command** method sends a command to the EPS.
   7. The **telemetry_request** method requests and returns interpreted telemetry data given tle and a multiplier.
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
      12. “Transmit”: Transmits a message as an email to the ground station via the Iridium constellation.
      13. “SBD Ring Alert On”: NOT UNDERSTOOD
      14. “SBD Ring Alert Off”: NOT UNDERSTOOD
      15. “Battery Check”: NOT UNDERSTOOD
      16. “Call Status”: NOT UNDERSTOOD
      17. “Soft Reset”: NOT UNDERSTOOD
   2. The **functional** method verifies that the serial port is open and that sending AT returns OK.
   3. The **request** method requests information from the Iridium and returns the parsed response.
   4. The **wave** method transmits a simple hardcoded message to the ground station. This is to accomplish our mission objective of testing Iridium.
   5. The **write** method writes a command to the Iridium.
   6. The **read** method reads in as many bytes as are available from the Iridium, serial timeout permitting.
8. **reset.py** is a simple script to reset the **StateFieldRegistry** log.

For more details on each specific part of the PFS, refer to the comments within the code. This README will be kept as up-to-date as possible.
