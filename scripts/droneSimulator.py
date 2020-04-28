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
import time
import json
from enum import Enum, auto
import traceback
import logging
import sys
from rctTransport import RCTUDPServer, PACKET_TYPES
import rctTransport
import ping
from lib2to3.fixer_util import Comma


class SDR_STATES(Enum):
    find_devices = 0
    wait_recycle = 1
    usrp_probe = 2
    rdy = 3
    fail = 4


class EXT_SENSOR_STATES(Enum):
    get_tty = 0
    get_msg = 1
    wait_recycle = 2
    rdy = 3
    fail = 4


class STORAGE_STATES(Enum):
    get_output_dir = 0
    check_output_dir = 1
    check_space = 2
    wait_recycle = 3
    rdy = 4
    fail = 5


class SYS_STATES(Enum):
    init = 0
    wait_init = 1
    wait_start = 2
    start = 3
    wait_end = 4
    finish = 5
    fail = 6


class SW_STATES(Enum):
    stop = 0
    start = 1


class rctDroneCommEvent(Enum):
    COMMAND = PACKET_TYPES.COMMAND.value
    UNKNOWN_PACKET = auto()


class droneComms:

    __ownKeywords = ['frequencies', 'heartbeat', 'ping', 'exception',
                     'options', 'upgrade_ready', 'upgrade_status', 'upgrade_complete']

    def __init__(self, port: rctTransport.RCTAbstractTransport, idString: str):
        self.__port = port
        self.__run = True
        self.__callbackMap = {}
        self.__idString = idString
        self.__gcsAddr = None

    def start(self):
        self.__run = True
        self.__port.open()
        self.__rxThread = threading.Thread(target=self.__receiver)
        self.__rxThread.start()

    def stop(self):
        self.__run = False
        if self.__rxThread is not None:
            self.__rxThread.join(timeout=1)
        self.__port.close()

    def sendPacket(self, packet: dict, dest: str):
        self.__port.send(json.dumps(packet).encode('utf-8'), dest)

    def sendHeartbeat(self, sysState: SYS_STATES, sdrState: SDR_STATES, extState: EXT_SENSOR_STATES, strState: STORAGE_STATES, swState: SW_STATES):
        time = dt.datetime.now().timestamp()
        status = "%d%d%d%d%d" % (
            sdrState.value, strState.value, extState.value, sysState.value, swState.value)
        payload = {}
        payload['id'] = self.__idString
        payload['time'] = time
        payload['status'] = status
        packet = {PACKET_TYPES.HEARTBEAT.value: payload}
        self.sendPacket(packet, None)

    def sendPing(self, pingObj: ping.rctPing):
        packet = {}
        packet[PACKET_TYPES.PING.value] = pingObj.toDict()
        self.sendPacket(packet, None)

    def sendFrequencies(self, frequencies: list):
        packet = {}
        packet[PACKET_TYPES.FREQUENCIES.value] = frequencies
        self.sendPacket(packet, self.__gcsAddr)

    def sendOptions(self, options: dict):
        packet = {}
        packet[PACKET_TYPES.OPTIONS.value] = options
        self.sendPacket(packet, self.__gcsAddr)

    def sendException(self, exception: str, traceback: str):
        packet = {}
        packet[PACKET_TYPES.EXCEPTION.value] = exception
        packet[PACKET_TYPES.TRACEBACK.value] = traceback
        self.sendPacket(packet, None)

    def sendUpgradeReady(self):
        packet = {}
        packet[PACKET_TYPES.UPGRADE_READY.value] = "true"
        self.sendPacket(packet, self.__gcsAddr)

    def sendUpgradeStatus(self, status: str):
        packet = {}
        packet[PACKET_TYPES.UPGRADE_STATUS.value] = status
        self.sendPacket(packet, self.__gcsAddr)

    def sendUpgradeComplete(self, status: bool, reason: str = None):
        packet = {}
        if status:
            packet[PACKET_TYPES.UPGRADE_COMPLETE.value] = "true"
        else:
            packet[PACKET_TYPES.UPGRADE_COMPLETE.value] = "false"

        packet['reason'] = reason

        self.sendPacket(packet, self.__gcsAddr)

    def __receiver(self):
        keywordEventMap = {}
        for event in rctDroneCommEvent:
            keywordEventMap[event.value] = event
        while self.__run is True:
            try:
                data, addr = self.__port.receive(1024, 1)
                msg = data.decode()
                print(msg)
                packet = dict(json.loads(msg))
                for key in packet.keys():
                    if key in droneComms.__ownKeywords:
                        # ignore stuff we sent
                        continue
                    try:
                        event = keywordEventMap[key]
                        self.__gcsAddr = addr
                        for callback in self.__callbackMap[event]:
                            callback(packet=packet[key], addr=addr)
                    except KeyError:
                        for callback in self.__callbackMap[rctDroneCommEvent.UNKNOWN_PACKET]:
                            callback(packet=packet, addr=addr)
                    except Exception as e:
                        self.sendException(str(e), traceback.format_exc())
            except TimeoutError:
                continue

    def registerCallback(self, event: rctDroneCommEvent, callback):
        if event in self.__callbackMap:
            self.__callbackMap[event].append(callback)
        else:
            self.__callbackMap[event] = [callback]


def getIPs():
    ip = set()

    ip.add(socket.gethostbyname_ex(socket.gethostname())[2][0])
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 53))
    ip.add(s.getsockname()[0])
    s.close()
    return ip


class droneSim:
    __HeartbeatPeriod = 1

    def __init__(self, port: droneComms):

        self.port = port
        self.__commandMap = {}
        self.__state = {}

        self.__frequencies = set()
        self.__centerFrequency = 173500000
        self.__samplingFrequency = 2000000
        self.__gain = 20.0
        self.__outputDirectory = "/tmp"
        self.__pingWidthMs = 15
        self.__pingMinSNR = 4.0
        self.__pingMaxLen = 1.5
        self.__pingMinLen = 0.5
        self.__gpsMode = False
        self.__gpsTarget = "/dev/null"
        self.__gpsBaud = 115200
        self.__autostart = False

        # register command actions here
        self.__commandMap[rctTransport.COMMANDS.GET_FREQUENCY.value] = self.__doGetFrequency
        self.__commandMap[rctTransport.COMMANDS.START.value] = self.__doStartMission
        self.__commandMap[rctTransport.COMMANDS.STOP.value] = self.__doStopMission
        self.__commandMap[rctTransport.COMMANDS.SET_FREQUENCY.value] = self.__doSetFrequency
        self.__commandMap[rctTransport.COMMANDS.GET_OPTIONS.value] = self.__doGetOptions
        self.__commandMap[rctTransport.COMMANDS.SET_OPTIONS.value] = self.__doSetOptions
        self.__commandMap[rctTransport.COMMANDS.WRITE_OPTIONS.value] = self.__doWriteOptions
        self.__commandMap[rctTransport.COMMANDS.UPGRADE.value] = self.__doUpgrade

        self.port.registerCallback(rctDroneCommEvent.COMMAND, self.__doCommand)

    def setGain(self, gain: float):
        self.__gain = gain

    def setOutputDir(self, outputDir: str):
        self.__outputDirectory = outputDir

    def setPingParameters(self, width: int = None, minSNR: float = None, maxLen: float = None, minLen: float = None):
        if width is not None:
            self.__pingWidthMs = width

        if minSNR is not None:
            self.__pingMinSNR = minSNR

        if maxLen is not None:
            self.__pingMaxLen = maxLen

        if minLen is not None:
            self.__pingMinLen = minLen

    def setGPSParameters(self, target: str = None, baudrate: int = None, testMode: bool = None):
        if target is not None:
            self.__gpsTarget = target

        if baudrate is not None:
            self.__gpsBaud = baudrate

        if testMode is not None:
            self.__gpsMode = testMode

    def setAutostart(self, flag: bool):
        self.__autostart = flag

    def __init(self):
        self.__state = {}
        self.__state['system'] = SYS_STATES.init
        self.__state['sensor'] = EXT_SENSOR_STATES.get_tty
        self.__state['storage'] = STORAGE_STATES.get_output_dir
        self.__state['switch'] = SW_STATES.stop
        self.__state['sdr'] = SDR_STATES.find_devices

    def start(self):
        self.__init()
        self.port.start()
        self.__run = True
        self.__txThread = threading.Thread(target=self.__sender)
        self.__txThread.start()

    def stop(self):
        self.__run = False
        if self.__txThread is not None:
            self.__txThread.join()
            self.port.stop()

    def gotPing(self, dronePing):
        pass

    def setSystemState(self, system: str, state):
        self.__state[system] = state

    def setException(self, exception: str, traceback: str):
        self.port.sendException(exception, traceback)

    def setFrequencies(self, frequencies: list):
        self.__frequencies = set(frequencies)

    def getFrequencies(self):
        return list(self.__frequencies)

    def setCenterFrequency(self, centerFreq: int):
        self.__centerFrequency = centerFreq

    def setSamplingFrequency(self, samplingFreq: int):
        self.__samplingFrequency = samplingFreq

    def __doGetFrequency(self, commandPayload):
        self.port.sendFrequencies(list(self.__frequencies))

    def __doStartMission(self, commandPayload):
        pass

    def __doStopMission(self, commandPayload):
        pass

    def __doSetFrequency(self, commandPayload):
        frequencies = commandPayload['frequencies']

        # Nyquist check
        for freq in frequencies:
            if abs(freq - self.__centerFrequency) > self.__samplingFrequency / 2:
                raise RuntimeError("Invalid frequency")

        self.__frequencies = set(frequencies)

    def __doGetOptions(self, commandPayload):
        options = {}
        options['ping_width_ms'] = self.__pingWidthMs
        options['ping_min_snr'] = self.__pingMinSNR
        options['ping_max_len_mult'] = self.__pingMaxLen
        options['ping_min_len_mult'] = self.__pingMinLen
        if self.__gpsMode:
            options['gps_mode'] = "true"
        else:
            options['gps_mode'] = 'false'
        options['gps_target'] = self.__gpsTarget
        options['frequencies'] = list(self.__frequencies)
        if self.__autostart:
            options['autostart'] = 'true'
        else:
            options['autostart'] = 'false'
        options['output_dir'] = self.__outputDirectory
        options['sampling_freq'] = self.__samplingFrequency
        options['center_freq'] = self.__centerFrequency
        self.port.sendOptions(options)

    def __doSetOptions(self, commandPayload):
        options = commandPayload['options']
        if 'ping_width_ms' in options:
            self.__pingWidthMs = float(options['ping_width_ms'])
            options.pop('ping_width_ms')

        if 'ping_min_snr' in options:
            self.__pingMinSNR = float(options['ping_min_snr'])
            options.pop('ping_min_snr')

        if 'ping_max_len_mult' in options:
            self.__pingMaxLen = float(options['ping_max_len_mult'])
            options.pop('ping_max_len_mult')

        if 'ping_min_len_mult' in options:
            self.__pingMinLen = float(options['ping_min_len_mult'])
            options.pop('ping_min_len_mult')

        if 'gps_mode' in options:
            if options['gps_mode'] == 'true':
                self.__gpsMode = True
            elif options['gps_mode'] == 'false':
                self.__gpsMode = False
            else:
                raise RuntimeError("Unknown parameter %s" %
                                   (options['gps_mode']))
            options.pop('gps_mode')

        if 'gps_target' in options:
            self.__gpsTarget = options['gps_target']
            options.pop('gps_target')

        if 'frequencies' in options:
            self.__doSetFrequency(options)
            options.pop('frequencies')

        if 'autostart' in options:
            if options['autostart'] == 'true':
                self.__autostart = True
            elif options['autostart'] == 'false':
                self.__autostart = False
            else:
                raise RuntimeError("Unknown parameter %s" %
                                   (options['autostart']))
            options.pop('autostart')

        if 'output_dir' in options:
            self.__outputDirectory = options['output_dir']
            options.pop('output_dir')

        if 'sampling_freq' in options:
            self.__samplingFrequency = int(options['sampling_freq'])
            options.pop('sampling_freq')

        if 'center_freq' in options:
            self.__centerFrequency = int(options['center_freq'])
            options.pop('center_freq')

        if len(options) != 0:
            raise RuntimeError("Unknown parameters in set options packet")

    def __doWriteOptions(self, commandPayload):
        pass

    def __doUpgrade(self, commandPayload):
        pass

    def __doCommand(self, packet: dict = None, addr: str = None):
        try:
            action = packet['action']
        except KeyError as e:
            print(str(e))
            print(traceback.format_exc())
            self.setException(str(e), traceback.format_exc())
            return
        try:
            self.__commandMap[action](packet)
        except Exception as e:
            print(str(e))
            print(traceback.format_exc())
            self.setException(str(e), traceback.format_exc())

    def __sender(self):
        while self.__run is True:
            self.port.sendHeartbeat(self.__state['system'], self.__state['sdr'],
                                    self.__state['sensor'], self.__state['storage'], self.__state['switch'])
            time.sleep(self.__HeartbeatPeriod)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Radio Collar Tracker Payload Control Simulator')
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--protocol', type=str,
                        choices=['udp', 'tcp'], required=True)
    parser.add_argument('--target', type=str, default='255.255.255.255',
                        help='Target IP Address.  Use 255.255.255.255 for broadcast')
    args = parser.parse_args()
    logName = dt.datetime.now().strftime('%Y.%m.%d.%H.%M.%S.log')
    logger = logging.getLogger('simulator.DroneSimulator')
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d: %(levelname)s:%(name)s: %(message)s', datefmt='%Y-%M-%d %H:%m:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ch = logging.FileHandler(logName)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)

    if args.protocol == 'udp':
        port = rctTransport.RCTUDPServer(port=args.port)
    elif args.protocol == 'tcp':
        port = rctTransport.RCTTCPServer(port=args.port)

    comms = droneComms(port, 'sim')
    sim = droneSim(comms)
    try:
        __IPYTHON__
    except NameError:
        sim.start()
