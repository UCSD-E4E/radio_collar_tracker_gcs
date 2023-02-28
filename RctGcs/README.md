# RCT Ground Control Station
## RCT GCS Drone Simulator
To run the simulator:
```
usage: droneSimulator.py [-h] [--port PORT] --protocol {udp,tcp}
                         [--target TARGET] [--clients NUM_CLIENTS]
droneSimulator.py: error: the following arguments are required: --protocol
```

For instance, to run interactively with TCP: `ipython -i droneSimulator.py -- --protocol tcp`

The following parameters are available for the simulator (member variables of `sim`):
- SM - Simulator Mission parameters
	- SM_mission_run
	- SM_utm_zone_num
	- SM_utm_zone
	- SM_origin
	- SM_takeoff_target
	- SM_waypoints
	- SM_target_threshold
	- SM_loop_period
	- SM_takeoff_vel
	- SM_wp_vel
	- SM_rtl_vel
	- SM_land_vel
- SC - Simulation Communication parameters
	- SC_vehicle_position_msg_period
	- SC_ping_measurement_period
	- SC_ping_measurement_sigma
	- SC_heartbeat_period
- SP - Simulation Ping parameters
	- SP_tx_power
	- SP_tx_power_sigma
	- SP_system_loss
	- SP_system_loss_sigma
	- SP_exponent
	- SP_exponent_sigma
	- SP_position
	- SP_noise_floor
	- SP_noise_floor_sigma
	- SP_tx_freq
- SV - Simulation Vehicle parameters
	- SV_vehicle_position_sigma
- HS - Heartbeat State parameters
	- HS_run
- SS - Simulation State parameters
	- SS_utm_zone_num
	- SS_utm_zone
	- SS_vehicle_position
	- SS_vehicle_state
	- SS_start_time
	- SS_velocity_vector
	- SS_vehicle_target
	- SS_waypoint_idx
	- SS_payload_running

The following parameters are available for the payload:
- SDR - Software Defined Radio parameters
	- SDR_center_freq
	- SDR_sampling_freq
	- SDR_gain
- TGT - Target parameters
	- TGT_frequencies
- DSP - Digital Signal Processing parameters
	- DSP_ping_width
	- DSP_ping_snr
	- DSP_ping_max
	- DSP_ping_min
- GPS - GPS Sensor parameters
	- GPS_mode
	- GPS_device
	- GPS_baud
- SYS - System parameters
	- SYS_output_dir
	- SYS_autostart
- STS - Status parameters
	- STS_sdr_status
	- STS_dir_status
	- STS_gps_status
	- STS_sys_status
	- STS_sw_status

Use the following member functions to configure the simulator:
```
DroneSim.set_gain(gain:float)
DroneSim.set_output_dir(output_dir:str)
DroneSim.set_ping_parameters(DSP_ping_width:int, DSP_ping_snr:float, DSP_ping_max:float, DSP_ping_min:float)
DroneSim.set_gps_parameters(GPS_device:str, GPS_baud:int, GPS_mode:bool)
dromeSim.set_autostart(SYS_autostart:bool)
DroneSim.set_system_state(system:str, state:int)
DroneSim.set_frequencies(frequencies:list)
DroneSim.set_center_frequency(center_freq:int)
DroneSim.set_sampling_frequency(sampling_freq:int)
```

Use the following member functions to run the simulator
```
DroneSim.start()
DroneSim.stop()
DroneSim.restart()
DroneSim.got_ping(drone_ping:ping.rctPing)
DroneSim.set_exception(exception:str, traceback:str)
DroneSim.get_frequencies()
DroneSim.transmit_position()
DroneSim.do_mission(return_on_end:bool)
DroneSim.calculate_ping_measurement()
```

Use the following function when using multiple clients (only available in tower mode)
```
add_client()
```

###Executing a Mission
```
bash$ ipython -i droneSimulator.py -- --protocol tcp
ipython>>> sim.start()
ipython>>> sim.do_mission()
```
