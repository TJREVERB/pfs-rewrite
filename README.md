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
2. **mission_control.py** calls **run** in **main_control_loop.py**.
   1. Iterates through main_control_loop and catches any errors that show up and troubleshoots them, continuing the MCL if troubleshooting is succesful.
   2. If troubleshooting fails, the program errors out.
3. **main_control_loop.py** iterates forever, reading input from its components and deciding what to do in each cycle. The following are the attributes of the **MainControlLoop** class.
   1. On **__init__** it creates the **StateFieldRegistry** object.
   2. The **start** method initializes everything for the MCL.
      1. Saves current time in the **StateFieldRegistry** vars as LAST_STARTUP.
      2. Instantiates a Recovery mode object if (antenna deployed) or (aprs or ad are locked off). Otherwise, instantiates a Startup mode object.
      3. Calls the Mode's **start** method.
   3. The **iterate** method is what iterates forever
      1. If there hasn't been contact from Iridium in a long time, it switches the primary radio to APRS.
      2. It iterates the Mode object.
      3. If there isn't a mode lock, it checks for if the Mode object wants to changes to another mode.
      4. It then calls the **command_executor** to execute any commands.
      5. It then logs the **StateFieldRegistry**.
5. **command_executor.py** contains all code pertaining to executing commands from TransmissionPackets
   1. The **primary_registry** dictionary contains method declarations for all of the commands that APRS and Iridium can execute.
   2. The **secondary_registry** dictionary contains method declarations for all of the commands that are accessible to outreach partners.
   3. The **execute** method is called through **execute_buffers**, reading any TransmissionPackets that have been recieved.
      1. It reads the packet for whatever command is given, handling any garbled messages.
      2. It then tries to execute the command, handling any exceptions in the process.
      3. It then logs the command through the **StateFieldRegistry**. 
6. **startup.py** extends the Mode class and is the mode responsible for operations at startup
   1. The **start** method powers on the Iridium radio.
   2. The **deploy_antenna** method attempts to deploy the APRS antenna if we've detumbled and enough time has passed.
   3. The **ping** method attempts to establish connection with ground using the **command_executor**.
   4. **execute_cycle**
      1. If the battery is low, it turns off all PDMs and sleeps for an orbit.
      2. Else, it turns on the primary radio, tries **deploy_antenna**, and attempts to beacon.
   5. **suggested_mode**
      1.  If the antennae haven't been deployed, or contact hasn't been established, returns Startup.
      2.  Else if low battery, returns Charging.
      3.  Else returns Science.
7. **charging.py** extends the Mode class and is the mode responsible for operations while charging
   1. The **start** method powers on the primary radio.
   2. Does nothing in order to preserve power.
8. **outreach.py** extends the Mode class and is the mode responsible for operations while outreaching
   1. The **start** method powers on the APRS radio.
   2. **suggested_mode** returns Charging if there is low power, and self if there is not low power.
   3. Does nothing. It acts as a buffer while waiting for APRS commands using the **command_executor**. (soon to be gaming mode)
9. **science.py** extends the Mode class and is the mode responsible for operations while conducting science
   1. The **start** method powers on the Iridium radio.
   2. **suggested_mode** returns the following
      3. Returns Charging if low battery
      4. Returns Outreach if done with data collection or Iridium is offline.
      5. Else returns Science.     
   3. The **ping** method pings ground with Iridium, logging geolocation data and signal strength.
   4. The **transmit_results** method transmits logged results using the **command_executor**.
   5. **execute_cycle** iterates through the required amount of pings and then transmits results.

10. **aprs.py** contains all code pertaining to the APRS.
   1. The **read** method reads and returns a message received over the APRS, and adds it to the **StateFieldRegistry**.
   2. The **write** method transmits a message through the APRS.
   3. The **functional** method tests if the component is connected properly and responsive to commands NEEDS TESTING, NOT FULLY IMPLEMENTED
11. **eps.py** contains all code pertaining to the EPS.
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
12. **antenna_deployer.py** contains all code pertaining to the antenna.
   1. The **deploy** method deploys the antenna.
   2. The **control** method deploys the antenna if 30 minutes have elapsed and the antenna is not already deployed.
13. **iridium.py** contians all code pertaining to the Iridium.
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
14. **reset.py** is a simple script to reset the **StateFieldRegistry** log.

For more details on each specific part of the PFS, refer to the comments within the code. This README will be kept as up-to-date as possible.
