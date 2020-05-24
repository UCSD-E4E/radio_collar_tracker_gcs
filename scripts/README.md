# RCT Ground Control Station
## RCT GCS Drone Simulator
To run the simulator:
```
usage: droneSimulator.py [-h] [--port PORT] --protocol {udp,tcp}
                         [--target TARGET]
droneSimulator.py: error: the following arguments are required: --protocol
```

For instance, to run interactively with TCP: `ipython -i droneSimulator.py -- --protocol tcp`

The following parameters are avilable for the simulator (member variables of `sim`):
- SM - Simulator Mission parameters
	- SM_missionRun
	- SM_utmZoneNum
	- SM_utmZone
	- SM_origin
	- SM_TakeoffTarget
	- SM_waypoints
	- SM_targetThreshold
	- SM_loopPeriod
	- SM_TakeoffVel
	- SM_WPVel
	- SM_RTLVel
	- SM_LandVel
- SC - Simulation Communication parameters
	- SC_VehiclePositionMsgPeriod
	- SC_PingMeasurementPeriod
	- SC_PingMeasurementSigma
	- SC_HeartbeatPeriod
- SP - Simulation Ping parameters
	- SP_TxPower
	- SP_TxPowerSigma
	- SP_SystemLoss
	- SP_SystemLossSigma
	- SP_Exponent
	- SP_ExponentSigma
	- SP_Position
	- SP_NoiseFloor
	- SP_NoiseFloorSigma
	- SP_TxFreq
- SV - Simulation Vehicle parameters
	- SV_vehiclePositionSigma
- HS - Heartbeat State parameters
	- HS_run
- SS - Simulation State parameters
	- SS_utmZoneNum
	- SS_utmZone
	- SS_vehiclePosition
	- SS_vehicleState
	- SS_startTime
	- SS_velocityVector
	- SS_vehicleTarget
	- SS_waypointIdx
	- SS_payloadRunning

The following parameters are avilable for the payload:
- SDR - Software Defined Radio parameters
	- SDR_centerFreq
	- SDR_samplingFreq
	- SDR_gain
- TGT - Target parameters
	- TGT_frequencies
- DSP - Digital Signal Processing parameters
	- DSP_pingWidth
	- DSP_pingSNR
	- DSP_pingMax
	- DSP_pingMin
- GPS - GPS Sensor parameters
	- GPS_mode
	- GPS_device
	- GPS_baud
- SYS - System parameters
	- SYS_outputDir
	- SYS_autostart
- STS - Status parameters
	- STS_sdrStatus
	- STS_dirStatus
	- STS_gpsStatus
	- STS_sysStatus
	- STS_swStatus

Use the following member functions to configure the simulator:
```
droneSim.setGain(gain:float)
droneSim.setOutputDir(outputDir:str)
droneSim.setPingParameters(DSP_pingWidth:int, DSP_pingSNR:float, DSP_pingMax:float, DSP_pingMin:float)
droneSim.setGPSParameters(GPS_device:str, GPS_baud:int, GPS_mode:bool)
dromeSim.setAutostart(SYS_autostart:bool)
droneSim.setSystemState(system:str, state:int)
droneSim.setFrequencies(frequencies:list)
droneSim.setCenterFrequency(centerFreq:int)
droneSim.setSamplingFrequency(samplingFreq:int)
```

Use the following member functions to run the simulator
```
droneSim.start()
droneSim.stop()
droneSim.restart()
droneSim.gotPing(dronePing:ping.rctPing)
droneSim.setException(exception:str, traceback:str)
droneSim.getFrequencies()
droneSim.transmitPosition()
droneSim.doMission(returnOnEnd:bool)
droneSim.calculatePingMeasurement()
```