#!/usr/bin/env python3
###############################################################################
#     Radio Collar Tracker Ground Control Software
#     Copyright (C) 2020  Nathan Hui
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
#
# DATE      WHO Description
# -----------------------------------------------------------------------------
# 08/07/22  HG  Added multiple-client functionality
# 08/06/20  NH  Fixed reset on init
# 07/29/20  NH  Added docstrings
# 05/23/20  NH  Fixed simulator run/stop actions
# 05/20/20  NH  Added droneSim.reset to facilitate simulator reset, fixed
#                 logging setup
# 05/19/20  NH  Renamed droneSim.__options to droneSim.PP_options to provide
#                 command line access
# 05/18/20  NH  Moved droneComms to rctComms, combined payload options into
#                 dict, annotated simulator parameters, updated commands to use
#                 binary protocol, integrated vehicle and ping data
# 05/05/20  NH  Integrated mission simulator and ping generation
# 04/26/20  NH  Removed old droneSimulator class, added output, added command
#                 callback, fixed sendFrequencies, added error capture, fixed
#                 cli args
# 04/25/20  NH  Finished abstraction of droneSimulator to droneSim
# 04/20/20  NH  Fixed sender to not send tuple as addr
# 04/19/20  NH  Added abstraction, switched to rctTransport comm interface
# 04/14/20  NH  Initial history
#
###############################################################################
import argparse
import math
import threading
import socket
import datetime as dt
from enum import Enum
import logging
import sys
import RCTComms.transport as rctTransport
import numpy as np
from time import sleep
from ping import rctPing
import utm
import json
import RCTComms.comms
import RCTComms.transport
import time
import math
from ui.display import towerMode

def getIPs():
    '''
    Returns this machine's IP addresses as a set
    '''
    ip = set()

    ip.add(socket.gethostbyname_ex(socket.gethostname())[2][0])
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 53))
    ip.add(s.getsockname()[0])
    s.close()
    return ip


class droneSim:
    '''
    Drone simulator class
    '''
    class MISSION_STATE:
        '''
        Mission State values.  These are the possible values of
        self.SS_vehicleState
        '''
        TAKEOFF = 0
        WAYPOINTS = 1
        RTL = 2
        LAND = 3
        END = 4
        SPIN = 5

    def __init__(self, port: RCTComms.comms.mavComms):
        '''
        Creates a new DroneSim object
        :param port:
        '''
        self.__txThread = None
        self.port = port
        self.__commandMap = {}
        self.__state = {
            'STS_sdrStatus': 0,
            'STS_dirStatus': 0,
            'STS_gpsStatus': 0,
            'STS_sysStatus': 0,
            'STS_swStatus': 0,
        }

        self.__txThread = None

        # PP - Payload parameters
        self.PP_options = {
            "TGT_frequencies": [],
            "SDR_centerFreq": 173500000,
            "SDR_samplingFreq": 2000000,
            "SDR_gain": 20.0,
            "DSP_pingWidth": 15,
            "DSP_pingSNR": 4.0,
            "DSP_pingMax": 1.5,
            "DSP_pingMin": 0.5,
            "GPS_mode": 0,
            "GPS_device": "/dev/null",
            "GPS_baud": 115200,
            "SYS_outputDir": "/tmp",
            "SYS_autostart": False,
        }

        # SM - Simulator Mission parameters
        self.SM_missionRun = True

        self.SM_utmZoneNum = 11
        self.SM_utmZone = 'S'
        self.SM_origin = (478110, 3638925, 0)
        self.SM_end = (478110, 3638400, 0)
        self.SM_TakeoffTarget = (478110, 3638925, 30)
        self.SM_waypoints = [(477974.06988529314, 3638776.3039655555, 30),
                             (478281.5079546513, 3638711.2010632926, 30),
                             (478274.9146625505, 3638679.2543171947, 30),
                             (477975.5071926904, 3638745.8378777136, 30),
                             (477968.40893670684, 3638712.893777053, 30),
                             (478266.818223601, 3638648.3095763493, 30),
                             (478258.7096344019, 3638611.871386835, 30),
                             (477961.8023651167, 3638675.453913263, 30),
                             (477953.6915540979, 3638638.5166701586, 30),
                             (478246.5868126497, 3638575.4419162693, 30),
                             (478239.4937485707, 3638544.494662541, 30),
                             (477943.58029727807, 3638604.5801627054, 30),
                             (477968.0164183045, 3638761.8351352056, 30),
                             (477976.95013863116, 3638774.1124560814, 30)]
        self.SM_targetThreshold = 5
        self.SM_loopPeriod = 0.1
        self.SM_TakeoffVel = 5
        self.SM_WPVel = 35
        self.SM_RTLVel = 20
        self.SM_LandVel = 1

        # SC - Simulation Communications parameters
        self.SC_VehiclePositionMsgPeriod = 1
        self.SC_PingMeasurementPeriod = 1
        self.SC_PingMeasurementSigma = 0
        self.SC_HeartbeatPeriod = 5

        # SP - Simulation Ping parameters
        self.SP_TxPower = 144
        self.SP_TxPowerSigma = 0
        self.SP_SystemLoss = 0
        self.SP_SystemLossSigma = 0
        self.SP_Exponent = 2.5
        self.SP_ExponentSigma = 0
        self.SP_Position = (478110, 3638661, 0)
        self.SP_NoiseFloor = 90
        self.SP_NoiseFloorSigma = 0
        self.SP_TxFreq = 173500000

        # SV - Simulation Vehicle parameters
        self.SV_vehiclePositionSigma = np.array((0, 0, 0))

        # SS - Simulation State parameters
        self.SS_utmZoneNum = 11
        self.SS_utmZone = 'S'
        self.SS_vehiclePosition = self.SM_origin
        self.SS_vehicleState = droneSim.MISSION_STATE.TAKEOFF
        self.SS_startTime = dt.datetime.now()
        self.SS_velocityVector = np.array([0, 0, 0])
        self.SS_vehicleTarget = np.array(self.SM_TakeoffTarget)
        self.SS_waypointIdx = 0
        self.SS_payloadRunning = False
        self.SS_heading = 0

        # HS - Heartbeat State parameters
        self.HS_run = True

        # register command actions here
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_GETF, self.__doGetFrequency)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_SETF, self.__doSetFrequency)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_GETOPT, self.__doGetOptions)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_SETOPT, self.__doSetOptions)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_START, self.__doStartMission)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_STOP, self.__doStopMission)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_UPGRADE, self.__doUpgrade)

        # Reset state parameters
        self.reset()

    def reset(self):
        '''
        Sets simulator parameters to their default
        '''
        self.stop()
        self.__commandMap = {}
        self.__state = {
            'STS_sdrStatus': 0,
            'STS_dirStatus': 0,
            'STS_gpsStatus': 0,
            'STS_sysStatus': 0,
            'STS_swStatus': 0,
        }

        # PP - Payload parameters
        self.PP_options = {
            "TGT_frequencies": [],
            "SDR_centerFreq": 173500000,
            "SDR_samplingFreq": 2000000,
            "SDR_gain": 20.0,
            "DSP_pingWidth": 15,
            "DSP_pingSNR": 4.0,
            "DSP_pingMax": 1.5,
            "DSP_pingMin": 0.5,
            "GPS_mode": 0,
            "GPS_device": "/dev/null",
            "GPS_baud": 115200,
            "SYS_outputDir": "/tmp",
            "SYS_autostart": False,
        }

        # SM - Simulator Mission parameters
        self.SM_missionRun = True

        self.SM_utmZoneNum = 11
        self.SM_utmZone = 'S'
        self.SM_origin = (478110, 3638925, 0)
        self.SM_end = (478110, 3638400, 0)
        self.SM_TakeoffTarget = (478110, 3638925, 30)
        '''
        Triangle
        self.SM_waypoints = [(478110, 3638925, 30),
                             (478080, 3638700, 30),
                             (478140, 3638700, 30)]
        Square
        self.SM_waypoints = [(477995, 3638776, 30),
                             (477995, 3638546, 30),
                             (478225, 3638546, 30),
                             (478225, 3638776, 30),
                             (477995, 3638776, 30)]
        100m
        self.SM_waypoints = [(478110.0, 3638761.0, 30),
                            (478060.0, 3638747.6025403785, 30),
                            (478023.39745962154, 3638711.0, 30),
                            (478010.0, 3638661.0, 30),
                            (478023.39745962154, 3638611.0, 30),
                            (478060.0, 3638574.3974596215, 30),
                            (478110.0, 3638561.0, 30),
                            (478160.0, 3638574.3974596215, 30),
                            (478196.60254037846, 3638611.0, 30),
                            (478210.0, 3638661.0, 30),
                            (478196.60254037846, 3638711.0, 30),
                            (478160.0, 3638747.6025403785, 30),
                            (478110.0, 3638761.0, 30)]
        70m
        self.SM_waypoints = [(478110.0, 3638731.0, 30),
                            (478075.0, 3638721.621778265, 30),
                            (478049.37822173507, 3638696.0, 30),
                            (478040.0, 3638661.0, 30),
                            (478049.37822173507, 3638626.0, 30),
                            (478075.0, 3638600.378221735, 30),
                            (478110.0, 3638591.0, 30),
                            (478145.0, 3638600.378221735, 30),
                            (478170.62177826493, 3638626.0, 30),
                            (478180.0, 3638661.0, 30),
                            (478170.62177826493, 3638696.0, 30),
                            (478145.0, 3638721.621778265, 30),
                            (478110.0, 3638731.0, 30)]

        OG
        self.SM_waypoints = [(477974.06988529314, 3638776.3039655555, 30),
                             (477974.06988529314, 3638776.3039655555, 30),
                             (477974.06988529314, 3638776.3039655555, 30),
                             (477974.06988529314, 3638776.3039655555, 30),
                             (477974.06988529314, 3638776.3039655555, 30),
                             (478281.5079546513, 3638711.2010632926, 30),
                             (478274.9146625505, 3638679.2543171947, 30),
                             (477975.5071926904, 3638745.8378777136, 30),
                             (477968.40893670684, 3638712.893777053, 30),
                             (478266.818223601, 3638648.3095763493, 30),
                             (478258.7096344019, 3638611.871386835, 30),
                             (477961.8023651167, 3638675.453913263, 30),
                             (477953.6915540979, 3638638.5166701586, 30),
                             (478246.5868126497, 3638575.4419162693, 30),
                             (478239.4937485707, 3638544.494662541, 30),
                             (477943.58029727807, 3638604.5801627054, 30),
                             (477968.0164183045, 3638761.8351352056, 30),
                             (477976.95013863116, 3638774.1124560814, 30)]
        '''
        self.SM_waypoints = [(478060, 3638631, 30),
                             (478170, 3638631, 30)]
        self.SM_targetThreshold = 5
        self.SM_loopPeriod = 0.1
        self.SM_TakeoffVel = 5
        self.SM_WPVel = 35
        self.SM_RTLVel = 20
        self.SM_LandVel = 1

        # SC - Simulation Communications parameters
        self.SC_VehiclePositionMsgPeriod = 1
        self.SC_PingMeasurementPeriod = 0.5
        self.SC_PingMeasurementSigma = 0
        self.SC_HeartbeatPeriod = 5

        # SP - Simulation Ping parameters
        self.SP_TxPower = 144
        self.SP_TxPowerSigma = 0
        self.SP_SystemLoss = 0
        self.SP_SystemLossSigma = 0
        self.SP_Exponent = 2.5
        self.SP_ExponentSigma = 0
        self.SP_Position = (478110, 3638661, 0)

        #center
        #self.SP_Position = (478110, 3638825, 0)

        #20m beyond
        #self.SP_Position = (478110, 3638680, 0)

        #20m right
        #self.SP_Position = (478130, 3638825, 0)

        #50m right
        #self.SP_Position = (478160, 3638825, 0)

        #diagonal
        #self.SP_Position = (478150, 3638680, 0)

        self.SP_NoiseFloor = 90
        self.SP_NoiseFloorSigma = 0
        self.SP_TxFreq = 173500000

        # SV - Simulation Vehicle parameters
        self.SV_vehiclePositionSigma = np.array((0, 0, 0))

        # SS - Simulation State parameters
        self.SS_utmZoneNum = 11
        self.SS_utmZone = 'S'
        self.SS_vehiclePosition = self.SM_origin
        self.SS_vehicleState = droneSim.MISSION_STATE.TAKEOFF
        self.SS_startTime = dt.datetime.now()
        self.SS_velocityVector = np.array([0, 0, 0])
        self.SS_vehicleTarget = np.array(self.SM_TakeoffTarget)
        self.SS_waypointIdx = 0
        self.SS_vehicleHdg = 0
        self.SS_hdgIndex = 0
        self.SS_payloadRunning = False
        self.SS_heading = 0

        # HS - Heartbeat State parameters
        self.HS_run = True

    def setGain(self, gain: float):
        '''
        Sets the SDR_gain parameter to the specified value
        :param gain:
        '''
        self.PP_options['SDR_gain'] = gain

    def setOutputDir(self, outputDir: str):
        '''
        Sets the output directory to the specified value
        :param outputDir:
        '''
        self.PP_options['SYS_outputDir'] = outputDir

    def setPingParameters(self, DSP_pingWidth: int = None, DSP_pingSNR: float = None, DSP_pingMax: float = None, DSP_pingMin: float = None):
        '''
        Sets the specified ping parameters
        :param DSP_pingWidth:
        :param DSP_pingSNR:
        :param DSP_pingMax:
        :param DSP_pingMin:
        '''
        if DSP_pingWidth is not None:
            self.PP_options['DSP_pingWidth'] = DSP_pingWidth

        if DSP_pingSNR is not None:
            self.PP_options['DSP_pingSNR'] = DSP_pingSNR

        if DSP_pingMax is not None:
            self.PP_options['DSP_pingMax'] = DSP_pingMax

        if DSP_pingMin is not None:
            self.PP_options['DSP_pingMin'] = DSP_pingMin

    def setGPSParameters(self, GPS_device: str = None, GPS_baud: int = None, GPS_mode: bool = None):
        '''
        Sets the specified GPS parameters
        :param GPS_device:
        :param GPS_baud:
        :param GPS_mode:
        '''
        if GPS_device is not None:
            self.PP_options['GPS_device'] = GPS_device

        if GPS_baud is not None:
            self.PP_options['GPS_baud'] = GPS_baud

        if GPS_mode is not None:
            self.PP_options['GPS_mode'] = GPS_mode

    def setAutostart(self, SYS_autostart: bool):
        '''
        Sets the autostart parameter
        :param SYS_autostart:
        '''
        self.PP_options['SYS_autostart'] = SYS_autostart

    def start(self):
        '''
        Starts the simulator.  This is equivalent to turning on the payload with
        autostart enabled.
        '''
        #self.reset()
        self.port.start()
        self.HS_run = True
        self.__txThread = threading.Thread(target=self.__sender)
        self.__txThread.start()

    def stop(self):
        '''
        Stops the simulator.  This is equivalent to turning off the payload.
        '''
        self.HS_run = False
        if self.__txThread is not None:
            self.__txThread.join()
            self.port.stop()

    def restart(self):
        '''
        Stops then starts the simulator.  This is equivalent to power cycling
        the payload.
        '''
        self.stop()
        self.start()

    def gotPing(self, dronePing: rctPing, hdg:float):
        '''
        Helper function to send a ping packet.  This must be called while the
        port is open.
        :param dronePing: rctPing object to send
        '''
        if not self.port.isOpen():
            raise RuntimeError
        print("Ping on %d at %3.7f, %3.7f, %3.0f m, measuring %3.3f" %
              (dronePing.freq, dronePing.lat, dronePing.lon, dronePing.alt, dronePing.power))

        conepacket = RCTComms.comms.rctConePacket(dronePing.lat, dronePing.lon, dronePing.alt, dronePing.power, hdg)


        self.port.sendCone(conepacket)

    def setSystemState(self, system: str, state):
        '''
        Sets the simulator's system state to the specified state.
        :param system: One of STS_sdrStatus, STS_dirStatus, STS_gpsStatus,
                        STS_sysStatus, or STS_swStatus
        :param state: The appropriate state number per ICD
        '''
        self.__state[system] = state

    def setException(self, exception: str, traceback: str):
        '''
        Helper function to send an exception packet.  This must be called while
        the port is open.
        :param exception: Exception string
        :param traceback: Traceback string
        '''
        if not self.port.isOpen():
            raise RuntimeError
        self.port.sendException(exception, traceback)

    def setFrequencies(self, frequencies: list):
        '''
        Sets the simulator's frequencies to the specified frequencies
        :param frequencies:
        '''
        self.PP_options['TGT_frequencies'] = frequencies

    def getFrequencies(self):
        '''
        Retrieves the simulator's frequencies
        '''
        return self.PP_options['TGT_frequencies']

    def setCenterFrequency(self, centerFreq: int):
        '''
        Sets the simulator's center frequency
        :param centerFreq:
        '''
        self.PP_options['SDR_centerFreq'] = centerFreq

    def setSamplingFrequency(self, samplingFreq: int):
        '''
        Sets the simulator's sampling frequency
        :param samplingFreq:
        '''
        self.PP_options['SDR_samplingFreq'] = samplingFreq

    def __ackCommand(self, command: RCTComms.comms.rctBinaryPacket):
        '''
        Sends the command acknowledge packet for the given command.
        :param command:
        '''
        self.port.sendToGCS(RCTComms.comms.rctACKCommand(command._pid, 1))

    def __doGetFrequency(self, packet: RCTComms.comms.rctGETFCommand, addr: str):
        '''
        Callback for the Get Frequency command packet
        :param packet:
        :param addr:
        '''
        self.port.sendToGCS(RCTComms.comms.rctFrequenciesPacket(
            self.PP_options['TGT_frequencies']))

    def __doStartMission(self, packet: RCTComms.comms.rctSTARTCommand, addr: str):
        '''
        Callback for the Start Mission command packet
        :param packet:
        :param addr:
        '''
        self.SS_payloadRunning = True
        self.__ackCommand(packet)

    def __doStopMission(self, packet: RCTComms.comms.rctSTOPCommand, addr: str):
        '''
        Callback for the Stop Mission command packet
        :param packet:
        :param addr:
        '''
        self.SS_payloadRunning = False
        self.__ackCommand(packet)

    def __doSetFrequency(self, packet: RCTComms.comms.rctSETFCommand, addr: str):
        '''
        Callback for the Set Frequency command packet
        :param packet:
        :param addr:
        '''
        frequencies = packet.frequencies

        # Nyquist check
        for freq in frequencies:
            if abs(freq - self.PP_options['SDR_centerFreq']) > self.PP_options['SDR_samplingFreq']:
                raise RuntimeError("Invalid frequency")

        self.PP_options['TGT_frequencies'] = frequencies
        self.__ackCommand(packet)
        self.__doGetFrequency(packet, addr)

    def __doGetOptions(self, packet: RCTComms.comms.rctGETOPTCommand, addr: str):
        '''
        Callback for the Get Options command packet
        :param packet:
        :param addr:
        '''
        scope = packet.scope
        print(self.PP_options)
        packet = RCTComms.comms.rctOptionsPacket(scope, **self.PP_options)
        self.port.sendToGCS(packet)

    def __doSetOptions(self, packet: RCTComms.comms.rctSETOPTCommand, addr: str):
        '''
        Callback for the Set Options command packet
        :param packet:
        :param addr:
        '''
        self.PP_options.update(packet.options)
        self.__doGetOptions(packet, addr)
        self.__ackCommand(packet)

    def __doUpgrade(self, commandPayload):
        '''
        Callback for the Upgrade command packet
        :param commandPayload:
        '''
        pass

    def __sender(self):
        '''
        Thread function for the heartbeat sender.  This function sends the
        heartbeat packet every self.SC_HeartbeatPeriod seconds.
        '''
        while self.HS_run is True:
            packet = RCTComms.comms.rctHeartBeatPacket(self.__state['STS_sysStatus'],
                                                 self.__state['STS_sdrStatus'],
                                                 self.__state['STS_gpsStatus'],
                                                 self.__state['STS_dirStatus'],
                                                 self.__state['STS_swStatus'])
            self.port.sendToAll(packet)
            time.sleep(self.SC_HeartbeatPeriod)

    def transmitPosition(self):
        '''
        Transmits the current vehicle position.  This function must only be used
        when the port is open.  Position is defined by self.SS_vehiclePosition
        in the self.SS_utmZoneNum and self.SS_utmZone zone.
        '''
        if not self.port.isOpen():
            raise RuntimeError
        print(self.SS_vehiclePosition, self.SS_vehicleState,
              np.linalg.norm(self.SS_velocityVector))
        lat, lon = utm.to_latlon(
            self.SS_vehiclePosition[0], self.SS_vehiclePosition[1], self.SS_utmZoneNum, self.SS_utmZone)
        alt = self.SS_vehiclePosition[2]
        hdg = 0
        packet = RCTComms.comms.rctVehiclePacket(lat, lon, alt, hdg)

        self.port.sendVehicle(packet)

    def doMission(self, returnOnEnd: bool = False):
        '''
        Runs the flight mission.  This function simulates flying the mission
        specified in the SM parameters.
        :param returnOnEnd:
        '''

        self.SS_vehiclePosition = self.SM_origin
        self.SS_vehicleState = droneSim.MISSION_STATE.TAKEOFF
        self.SS_startTime = dt.datetime.now()
        self.SS_velocityVector = np.array([0, 0, 0])
        self.SS_vehicleTarget = np.array(self.SM_TakeoffTarget)
        self.SS_waypointIdx = 0

        prevPosTime = prevPingTime = prevTime = self.SS_startTime
        wpTime = self.SS_startTime
        while self.SM_missionRun:
            #######################
            # Loop time variables #
            #######################
            # Current time
            curTime = dt.datetime.now()
            # Time since mission start
            elTime = (curTime - self.SS_startTime).total_seconds()
            # Time since last loop
            itTime = (curTime - prevTime).total_seconds()
            # Time since last waypoint
            segTime = (curTime - wpTime).total_seconds()

            ########################
            # Flight State Machine #
            ########################
            if self.SS_vehicleState == droneSim.MISSION_STATE.TAKEOFF:
                self.SS_velocityVector = np.array(
                    [0, 0, 1]) * self.SM_TakeoffVel
                self.SS_vehiclePosition += self.SS_velocityVector * itTime
                distanceToTarget = np.linalg.norm(
                    self.SS_vehicleTarget - self.SS_vehiclePosition)
                if distanceToTarget < self.SM_targetThreshold:
                    self.SS_velocityVector = np.array([0, 0, 0])
                    self.SS_vehicleState = droneSim.MISSION_STATE.WAYPOINTS
                    self.SS_vehicleTarget = np.array(
                        self.SM_waypoints[self.SS_waypointIdx])
                    wpTime = dt.datetime.now()

            elif self.SS_vehicleState == droneSim.MISSION_STATE.WAYPOINTS:
                targetVector = self.SS_vehicleTarget - self.SS_vehiclePosition
                distanceToTarget = np.linalg.norm(targetVector)
                self.SS_velocityVector = targetVector / distanceToTarget * self.SM_WPVel

                self.SS_vehiclePosition += self.SS_velocityVector * itTime
                if distanceToTarget < self.SM_targetThreshold:
                    self.SS_velocityVector = np.array([0, 0, 0])
                    wpTime = dt.datetime.now()

                    self.SS_waypointIdx += 1
                    self.SS_vehicleState = droneSim.MISSION_STATE.SPIN

            elif self.SS_vehicleState == droneSim.MISSION_STATE.SPIN:
                self.SS_vehicleHdg = self.SS_hdgIndex*5
                self.SS_hdgIndex += 1
                if self.SS_vehicleHdg == 360:
                    self.SS_hdgIndex = 0
                    if self.SS_waypointIdx < len(self.SM_waypoints):
                        self.SS_vehicleState = droneSim.MISSION_STATE.WAYPOINTS
                        self.SS_vehicleTarget = np.array(
                            self.SM_waypoints[self.SS_waypointIdx])
                    else:
                        self.SS_vehicleState = droneSim.MISSION_STATE.RTL
                        #self.SS_vehicleTarget = np.array(self.SM_end)
                        self.SS_vehicleTarget = np.array(self.SM_TakeoffTarget)
            elif self.SS_vehicleState == droneSim.MISSION_STATE.RTL:
                targetVector = self.SS_vehicleTarget - self.SS_vehiclePosition
                distanceToTarget = np.linalg.norm(targetVector)
                self.SS_velocityVector = targetVector / distanceToTarget * self.SM_RTLVel

                self.SS_vehiclePosition += self.SS_velocityVector * itTime
                if distanceToTarget < self.SM_targetThreshold:
                    self.SS_velocityVector = np.array([0, 0, 0])
                    wpTime = dt.datetime.now()

                    self.SS_vehicleState = droneSim.MISSION_STATE.LAND
                    #self.SS_vehicleTarget = np.array(self.SM_end)
                    self.SS_vehicleTarget = np.array(self.SM_origin)

            elif self.SS_vehicleState == droneSim.MISSION_STATE.LAND:
                self.SS_velocityVector = np.array([0, 0, -1]) * self.SM_LandVel
                self.SS_vehiclePosition += self.SS_velocityVector * itTime
                distanceToTarget = np.linalg.norm(
                    self.SS_vehicleTarget - self.SS_vehiclePosition)
                if distanceToTarget < self.SM_targetThreshold:
                    self.SS_velocityVector = np.array([0, 0, 0])
                    wpTime = dt.datetime.now()
                    self.SS_vehicleState = droneSim.MISSION_STATE.END
            else:
                if returnOnEnd:
                    return
                else:
                    self.SS_velocityVector = np.array([0, 0, 0])

            sleep(self.SM_loopPeriod)
            ###################
            # Ping Simulation #
            ###################
            if (curTime - prevPingTime).total_seconds() > self.SC_PingMeasurementPeriod:
                lat, lon = utm.to_latlon(
                    self.SS_vehiclePosition[0], self.SS_vehiclePosition[1], self.SM_utmZoneNum, self.SM_utmZone)
                latT, lonT = utm.to_latlon(
                    self.SS_vehicleTarget[0], self.SS_vehicleTarget[1], self.SM_utmZoneNum, self.SM_utmZone)
                if self.SS_vehicleState == droneSim.MISSION_STATE.SPIN:
                        hdg = self.SS_vehicleHdg
                else:
                    hdg = self.get_bearing(lat, lon, latT, lonT)
                    self.SS_vehicleHdg = hdg
                pingMeasurement = self.calculatePingMeasurement()
                if pingMeasurement is not None:
                    print("in Ping Measurement")

                    newPing = rctPing(
                        lat, lon, pingMeasurement[0], pingMeasurement[1], self.SS_vehiclePosition[2], curTime.timestamp())

                    #hdg = self.get_bearing(self.SS_vehiclePosition[0], self.SS_vehiclePosition[1], self.SS_vehicleTarget[0], self.SS_vehicleTarget[1])

                    print(hdg)
                    '''
                    if self.SS_payloadRunning:
                        self.gotPing(newPing)
                    '''
                    if newPing is not None:
                        self.gotPing(newPing, hdg)
                prevPingTime = curTime

            ###################
            # Position Output #
            ###################
            if (curTime - prevPosTime).total_seconds() > self.SC_VehiclePositionMsgPeriod:
                self.transmitPosition()
                prevPosTime = curTime
            prevTime = curTime

    def get_bearing(self, lat1, long1, lat2, long2):
        dLon = (long2 - long1)
        x = math.cos(math.radians(lat2)) * math.sin(math.radians(dLon))
        y = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(dLon))
        brng = np.arctan2(x,y)
        brng = np.degrees(brng)

        return brng

    def __antennaModel(self, beam_angle) -> float:
        return np.abs(np.cos(beam_angle)) ** (2.99999)

    def __computeHeadingMultiplier(self) -> float:
        # Get my current heading
        x = np.cos(np.deg2rad(self.SS_vehicleHdg))
        y = np.sin(np.deg2rad(self.SS_vehicleHdg))
        heading_vector = np.array([x, y, 0])

        # Get the bearing to the transmitter
        transmitter_vector = np.array(self.SP_Position) - np.array(self.SS_vehiclePosition)
        transmitter_vector = transmitter_vector / np.linalg.norm(transmitter_vector)

        # Compute the bearing from antenna to transmitter
        dot = np.dot(heading_vector, transmitter_vector)
        angle = np.arccos(dot)
        print("Angle: ", np.rad2deg(angle))

        # Plug into directivity model
        model = self.__antennaModel(angle)
        print("Model: ", model)
        return model

    def calculatePingMeasurement(self):
        '''
        Calculate the simulated ping measurement from the current state
        variables
        '''
        # check against frequencies
        '''
        if abs(self.SP_TxFreq - self.PP_options['SDR_centerFreq']) > self.PP_options['SDR_samplingFreq']:
            return None

        if self.SP_TxFreq not in self.PP_options['TGT_frequencies']:
            return None
        '''
        # vehicle is correctly configured
        l_rx = np.array(self.SS_vehiclePosition)
        l_tx = np.array(self.SP_Position)
        rand = np.random.normal(scale=self.SP_TxPowerSigma)
        P_tx = self.SP_TxPower + rand
        randEx = np.random.normal(scale=self.SP_ExponentSigma)
        n = self.SP_Exponent + randEx
        C = self.SP_SystemLoss
        f_tx = self.SP_TxFreq
        randN = np.random.normal(scale=self.SP_NoiseFloorSigma)#added
        P_n = self.SP_NoiseFloor + randN
        print(randN)
        print(P_n)

        d = np.linalg.norm(l_rx - l_tx)

        Prx = P_tx - 10 * n * np.log10(d) - C

        measurement = [Prx, f_tx]

        measurement[0] *= self.__computeHeadingMultiplier()

        measurement = (measurement[0], measurement[1])

        # implement noise floor
        if Prx < P_n:
           measurement = None


        return measurement


    def exportSettings(self, filename):
        e = {}
        e['commandMap'] = str(self.__commandMap)

        e['State'] = str(self.__state )

        e['PP_options'] = str(self.PP_options )
        e['SM_missionRun'] = str(self.SM_missionRun )

        e['SM_utmZoneNum'] = str(self.SM_utmZoneNum)
        e['SM_utmZone'] = str(self.SM_utmZone)

        e['SM_origin'] = str(self.SM_origin)

        e['SM_TakeoffTarget'] = str(self.SM_TakeoffTarget)

        e['SM_waypoints'] = str(self.SM_waypoints )

        e['SM_targetThreshold'] = str(self.SM_targetThreshold)

        e['SM_loopPeriod'] = str(self.SM_loopPeriod )

        e['SM_TakeoffVel'] = str(self.SM_TakeoffVel)

        e['SM_WPVel'] = str(self.SM_WPVel )

        e['SM_RTLVel'] = str(self.SM_RTLVel)

        e['SM_LandVel'] = str(self.SM_LandVel)


        e['SC_VehiclePositionMsgPeriod'] = str(self.SC_VehiclePositionMsgPeriod)

        e['SC_PingMeasurementPeriod'] = str(self.SC_PingMeasurementPeriod )

        e['SC_PingMeasurementSigma'] = str(self.SC_PingMeasurementSigma )

        e['SC_HeartbeatPeriod'] = str(self.SC_HeartbeatPeriod )


        e['SP_TxPower'] = str(self.SP_TxPower )

        e['SP+TxPowerSigma'] = str(self.SP_TxPowerSigma)

        e['SP_SystemLoss'] = str(self.SP_SystemLoss )

        e['SP_SystemLossSigma'] = str(self.SP_SystemLossSigma )

        e['SP_Exponent'] = str(self.SP_Exponent )

        e['SP_ExponentSigma'] = str(self.SP_ExponentSigma)

        e['SP_Position'] = str(self.SP_Position )

        e['SP_NoiseFloor'] = str(self.SP_NoiseFloor)

        e['SP_NoiseFloorSigma:'] = str(self.SP_NoiseFloorSigma )

        e['SP_TxFreq'] = str(self.SP_TxFreq )


        e['SV_VehiclePositionSigma'] = str(self.SV_vehiclePositionSigma)


        e['SS_utmZoneNum'] = str(self.SS_utmZoneNum)

        e['SS_utmZone'] = str(self.SS_utmZone )

        e['SS_VehiclePosition'] = str(self.SS_vehiclePosition )

        e['SS_vehicleState'] = str(self.SS_vehicleState)

        e['SS_startTime'] = str(self.SS_startTime )

        e['SS_velocityVector'] = str(self.SS_velocityVector)

        e['SS_vehicleTarget'] = str(self.SS_vehicleTarget)

        e['SS_waypointIdx'] = str(self.SS_waypointIdx )

        e['SS_payloadRunning'] = str(self.SS_payloadRunning )

        e['SS_heading'] = str(self.SS_heading )
        


        e['HS_run'] = str(self.HS_run )

        settingsFile = filename + '.json'
        with open(settingsFile, 'w') as outfile:
            json.dump(e, outfile)

def addClient():
    '''
    Connects another client and adds the associated simulator to simList
    '''

    if args.protocol == 'udp':
        port = RCTComms.transport.RCTUDPClient(port=args.port, addr=args.target)
    elif args.protocol == 'tcp':
        port = RCTComms.transport.RCTTCPClient(port=args.port, addr=args.target)

    sim = droneSim(RCTComms.comms.mavComms(port))
    simList.append(sim)

def doAll(action:str, args=None):
    '''
    Calls the specified action on each simulator in simList

    :param action: the function to be called
    '''
    try:
        for sim in simList:
            if action == "start":
                sim.start()
            elif action == "stop":
                sim.stop()
            elif action == "restart":
                sim.restart()
            elif action == "gotPing":
                sim.gotPing(args[0])
            elif action == "setException":
                sim.setException(args[0], args[1])
            elif action == "getFrequencies":
                sim.getFrequencies()
            elif action == "transmitPosition":
                sim.transmitPosition()
            elif action == "doMission":
                sim.doMission(args[0])
            elif action == "calculatePingMeasurement":
                sim.calculatePingMeasurement()
            else:
                print("Error: Select one of the following functions:")
                print("\'start\', \'stop\', \'restart\', \'gotPing\', ", end='')
                print("\'setException\', \'getFrequencies\', ", end='')
                print("\'transmitPosition\', \'doMission\', \'calculatePingMeasurement\'")
                break
    except TypeError:
        print("Error: Ensure you have provided all required arguments in a list.")

def connectionHandler(connection, id):
    print('Connected {}'.format(id))
    comms = RCTComms.comms.mavComms(connection)
    sim = droneSim(comms)
    simList.append(sim)

simList = []
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Radio Collar Tracker Payload Control Simulator')
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--protocol', type=str,
                        choices=['udp', 'tcp'], required=True)
    parser.add_argument('--target', type=str, default='127.0.0.1',
                        help='Target IP Address.  Use 255.255.255.255 for broadcast, 127.0.0.1 for local')
    parser.add_argument('--clients', type=int, default=1)
    args = parser.parse_args()
    logName = dt.datetime.now().strftime('%Y.%m.%d.%H.%M.%S_sim.log')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.ERROR)
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d: %(levelname)s:%(name)s: %(message)s', datefmt='%Y-%M-%d %H:%m:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ch = logging.FileHandler(logName)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    if args.protocol == 'udp':
        if towerMode:
            for i in range(args.clients):
                port = RCTComms.transport.RCTUDPClient(port=args.port, addr=args.target)
                sim = droneSim(RCTComms.comms.mavComms(port))
                simList.append(sim)
        else:
            port = RCTComms.transport.RCTUDPServer(port=args.port)
            sim = droneSim(RCTComms.comms.mavComms(port))
    elif args.protocol == 'tcp':
        if towerMode:
            for i in range(args.clients):
                port = RCTComms.transport.RCTTCPClient(port=args.port, addr=args.target)
                sim = droneSim(RCTComms.comms.mavComms(port))
                simList.append(sim)
        else:
            connected = False
            port = RCTComms.transport.RCTTCPServer(args.port, connectionHandler, addr=args.target)
            port.open()
            while len(simList) == 0:
                continue
            sim = simList[0]

    try:
        __IPYTHON__
    except NameError:
        for sim in simList:
            sim.start()
