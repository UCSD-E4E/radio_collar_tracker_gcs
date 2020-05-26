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
import threading
import socket
import datetime as dt
from enum import Enum
import logging
import sys
import rctTransport
import numpy as np
from time import sleep
from ping import rctPing
import utm

from rctComms import mavComms, rctBinaryPacket
import rctComms
import time


class rctDroneCommEvent(Enum):
    COMMAND = 0x05
    UNKNOWN_PACKET = -1


def getIPs():
    ip = set()

    ip.add(socket.gethostbyname_ex(socket.gethostname())[2][0])
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 53))
    ip.add(s.getsockname()[0])
    s.close()
    return ip


class droneSim:

    def __init__(self, port: mavComms):
        self.port = port
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
        self.SM_WPVel = 5
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

        # HS - Heartbeat State parameters
        self.HS_run = True

        # register command actions here
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_GETF, self.__doGetFrequency)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_SETF, self.__doSetFrequency)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_GETOPT, self.__doGetOptions)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_SETOPT, self.__doSetOptions)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_START, self.__doStartMission)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_STOP, self.__doStopMission)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_UPGRADE, self.__doUpgrade)

    def reset(self):
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
        self.SM_WPVel = 5
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

        # HS - Heartbeat State parameters
        self.HS_run = True

        # register command actions here
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_GETF, self.__doGetFrequency)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_SETF, self.__doSetFrequency)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_GETOPT, self.__doGetOptions)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_SETOPT, self.__doSetOptions)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_START, self.__doStartMission)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_STOP, self.__doStopMission)
        self.port.registerCallback(
            rctComms.EVENTS.COMMAND_UPGRADE, self.__doUpgrade)

    def setGain(self, gain: float):
        self.PP_options['SDR_gain'] = gain

    def setOutputDir(self, outputDir: str):
        self.PP_options['SYS_outputDir'] = outputDir

    def setPingParameters(self, DSP_pingWidth: int = None, DSP_pingSNR: float = None, DSP_pingMax: float = None, DSP_pingMin: float = None):
        if DSP_pingWidth is not None:
            self.PP_options['DSP_pingWidth'] = DSP_pingWidth

        if DSP_pingSNR is not None:
            self.PP_options['DSP_pingSNR'] = DSP_pingSNR

        if DSP_pingMax is not None:
            self.PP_options['DSP_pingMax'] = DSP_pingMax

        if DSP_pingMin is not None:
            self.PP_options['DSP_pingMin'] = DSP_pingMin

    def setGPSParameters(self, GPS_device: str = None, GPS_baud: int = None, GPS_mode: bool = None):
        if GPS_device is not None:
            self.PP_options['GPS_device'] = GPS_device

        if GPS_baud is not None:
            self.PP_options['GPS_baud'] = GPS_baud

        if GPS_mode is not None:
            self.PP_options['GPS_mode'] = GPS_mode

    def setAutostart(self, SYS_autostart: bool):
        self.PP_options['SYS_autostart'] = SYS_autostart

    def __init(self):
        self.__state['STS_sdrStatus'] = 0
        self.__state['STS_dirStatus'] = 0
        self.__state['STS_gpsStatus'] = 0
        self.__state['STS_sysStatus'] = 0
        self.__state['STS_swStatus'] = 0

    def start(self):
        self.__init()
        self.port.start()
        self.HS_run = True
        self.__txThread = threading.Thread(target=self.__sender)
        self.__txThread.start()

    def stop(self):
        self.HS_run = False
        if self.__txThread is not None:
            self.__txThread.join()
            self.port.stop()

    def restart(self):
        self.stop()
        self.start()

    def gotPing(self, dronePing: rctPing):
        print("Ping on %d at %3.7f, %3.7f, %3.0f m, measuring %3.3f" %
              (dronePing.freq, dronePing.lat, dronePing.lon, dronePing.alt, dronePing.amplitude))
        packet = dronePing.toPacket()
        self.port.sendToAll(packet)

    def setSystemState(self, system: str, state):
        self.__state[system] = state

    def setException(self, exception: str, traceback: str):
        self.port.sendException(exception, traceback)

    def setFrequencies(self, frequencies: list):
        self.PP_options['TGT_frequencies'] = frequencies

    def getFrequencies(self):
        return self.PP_options['TGT_frequencies']

    def setCenterFrequency(self, centerFreq: int):
        self.PP_options['SDR_centerFreq'] = centerFreq

    def setSamplingFrequency(self, samplingFreq: int):
        self.PP_options['SDR_samplingFreq'] = samplingFreq

    def __ackCommand(self, command: rctBinaryPacket):
        self.port.sendToGCS(rctComms.rctACKCommand(command._pid, 1))

    def __doGetFrequency(self, packet: rctComms.rctGETFCommand, addr: str):
        self.port.sendToGCS(rctComms.rctFrequenciesPacket(
            self.PP_options['TGT_frequencies']))

    def __doStartMission(self, packet: rctComms.rctSTARTCommand, addr: str):
        self.SS_payloadRunning = True
        self.__ackCommand(packet)

    def __doStopMission(self, packet: rctComms.rctSTOPCommand, addr: str):
        self.SS_payloadRunning = False
        self.__ackCommand(packet)

    def __doSetFrequency(self, packet: rctComms.rctSETFCommand, addr: str):
        frequencies = packet.frequencies

        # Nyquist check
        for freq in frequencies:
            if abs(freq - self.PP_options['SDR_centerFreq']) > self.PP_options['SDR_samplingFreq']:
                raise RuntimeError("Invalid frequency")

        self.PP_options['TGT_frequencies'] = frequencies
        self.__ackCommand(packet)
        self.__doGetFrequency(packet, addr)

    def __doGetOptions(self, packet: rctComms.rctGETOPTCommand, addr: str):
        scope = packet.scope
        packet = rctComms.rctOptionsPacket(scope, **self.PP_options)
        self.port.sendToGCS(packet)

    def __doSetOptions(self, packet: rctComms.rctSETOPTCommand, addr: str):
        self.PP_options.update(packet.options)
        self.__doGetOptions(packet, addr)
        self.__ackCommand(packet)

    def __doUpgrade(self, commandPayload):
        pass

    def __sender(self):
        while self.HS_run is True:
            packet = rctComms.rctHeartBeatPacket(self.__state['STS_sysStatus'],
                                                 self.__state['STS_sdrStatus'],
                                                 self.__state['STS_gpsStatus'],
                                                 self.__state['STS_dirStatus'],
                                                 self.__state['STS_swStatus'])
            self.port.sendToAll(packet)
            time.sleep(self.SC_HeartbeatPeriod)

    class MISSION_STATE:
        TAKEOFF = 0
        WAYPOINTS = 1
        RTL = 2
        LAND = 3
        END = 4

    def transmitPosition(self):
        print(self.SS_vehiclePosition, self.SS_vehicleState,
              np.linalg.norm(self.SS_velocityVector))
        lat, lon = utm.to_latlon(
            self.SS_vehiclePosition[0], self.SS_vehiclePosition[1], self.SS_utmZoneNum, self.SS_utmZone)
        alt = self.SS_vehiclePosition[2]
        hdg = 0
        packet = rctComms.rctVehiclePacket(lat, lon, alt, hdg)
        self.port.sendToAll(packet)

    def doMission(self, returnOnEnd: bool = False):

        self.SS_vehiclePosition = self.SM_origin
        self.SS_vehicleState = droneSim.MISSION_STATE.TAKEOFF
        self.SS_startTime = dt.datetime.now()
        self.SS_velocityVector = np.array([0, 0, 0])
        self.SS_vehicleTarget = np.array(self.SM_TakeoffTarget)
        self.SS_waypointIdx = 0

        prevPosTime = prevPingTime = prevTime = self.SS_startTime
        wpTime = self.SS_startTime
        while self.SM_missionRun:
            curTime = dt.datetime.now()
            elTime = (curTime - self.SS_startTime).total_seconds()
            itTime = (curTime - prevTime).total_seconds()
            segTime = (curTime - wpTime).total_seconds()
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
                    if self.SS_waypointIdx < len(self.SM_waypoints):
                        self.SS_vehicleState = droneSim.MISSION_STATE.WAYPOINTS
                        self.SS_vehicleTarget = np.array(
                            self.SM_waypoints[self.SS_waypointIdx])
                    else:
                        self.SS_vehicleState = droneSim.MISSION_STATE.RTL
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
            if (curTime - prevPingTime).total_seconds() > self.SC_PingMeasurementPeriod:
                pingMeasurement = self.calculatePingMeasurement()
                if pingMeasurement is not None:
                    lat, lon = utm.to_latlon(
                        self.SS_vehiclePosition[0], self.SS_vehiclePosition[1], self.SM_utmZoneNum, self.SM_utmZone)
                    newPing = rctPing(
                        lat, lon, pingMeasurement[0], pingMeasurement[1], self.SS_vehiclePosition[2], curTime.timestamp())
                    if self.SS_payloadRunning:
                        self.gotPing(newPing)
                prevPingTime = curTime

            if (curTime - prevPosTime).total_seconds() > self.SC_VehiclePositionMsgPeriod:
                self.transmitPosition()
                prevPosTime = curTime
            prevTime = curTime

    def calculatePingMeasurement(self):
        # check against frequencies
        if abs(self.SP_TxFreq - self.PP_options['SDR_centerFreq']) > self.PP_options['SDR_samplingFreq']:
            return None

        if self.SP_TxFreq not in self.PP_options['TGT_frequencies']:
            return None

        # vehicle is correctly configured
        l_rx = np.array(self.SS_vehiclePosition)
        l_tx = np.array(self.SP_Position)
        P_tx = self.SP_TxPower
        n = self.SP_Exponent
        C = self.SP_SystemLoss
        f_tx = self.SP_TxFreq
        P_n = self.SP_NoiseFloor

        d = np.linalg.norm(l_rx - l_tx)

        Prx = P_tx - 10 * n * np.log10(d) - C

        measurement = (Prx, f_tx)

        # implement noise floor
        if Prx < P_n:
            measurement = None

        return measurement


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Radio Collar Tracker Payload Control Simulator')
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--protocol', type=str,
                        choices=['udp', 'tcp'], required=True)
    parser.add_argument('--target', type=str, default='255.255.255.255',
                        help='Target IP Address.  Use 255.255.255.255 for broadcast')
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
        port = rctTransport.RCTUDPServer(port=args.port)
    elif args.protocol == 'tcp':
        port = rctTransport.RCTTCPServer(port=args.port)

    comms = mavComms(port)
    sim = droneSim(comms)
    try:
        __IPYTHON__
    except NameError:
        sim.start()
