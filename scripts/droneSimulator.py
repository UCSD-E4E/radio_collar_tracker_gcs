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


class DroneSimulator:

    __SDR_STATES_POS = 0
    __STG_STATES_POS = 1
    __EXT_STATES_POS = 2
    __SYS_STATES_POS = 3
    __SWT_STATES_POS = 4

    def __init__(self, port=9000, target='255.255.255.255', log=False):
        self._port = port
        self._target = target
        self.__log = logging.getLogger('simulator.DroneSimulator')
        self.system_states = [None] * 5
        self.system_states[self.__SDR_STATES_POS] = SDR_STATES.find_devices
        self.system_states[self.__STG_STATES_POS] = STORAGE_STATES.get_output_dir
        self.system_states[self.__EXT_STATES_POS] = EXT_SENSOR_STATES.get_tty
        self.system_states[self.__SYS_STATES_POS] = SYS_STATES.init
        self.system_states[self.__SWT_STATES_POS] = SW_STATES.stop
        self.frequencies = []

        self.numErrors = 0
        self.numMsgSent = 0
        self.numMsgReceived = 0

        self.socketLock = threading.Lock()

        self.MENU = {
            'cmd': self._processCommand}

        self.CMD_MENU = {
            'getF': self._transmitFreqs,
        }

        self._socket = RCTUDPServer(self._port)

    def start(self):
        print("Simulator started")
        self.numErrors = 0
        self.numMsgSent = 0
        self.numMsgReceived = 0
        self._run = True
#         self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#         self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
#         self._socket.setblocking(0)
#         self._socket.bind(("", self._port))
        self._socket.open()
        self._senderThread = threading.Thread(target=self.__sender)
        self._receiveThread = threading.Thread(target=self.__receiver)
        self._senderThread.start()
        self._receiveThread.start()

    def stop(self):
        self._run = False
        self._senderThread.join()
        self._receiveThread.join()
        self._socket.close()
        self.__log.info("Stopped at %d" %
                        (dt.datetime.now().timestamp()))
        self.__log.info("Received %d messages" % self.numMsgReceived)
        self.__log.info("Sent %d messages" % self.numMsgSent)
        self.__log.info("%d Errors" % self.numErrors)
        print("Simulator stopped")

    def __sender(self):
        prevTime = dt.datetime.now()
        sendTarget = self._target

        while self._run is True:
            now = dt.datetime.now()

#             Heartbeat
            if (now - prevTime).total_seconds() > 1:
                heartbeatPacket = {}
                heartbeatPacket['heartbeat'] = {}
                heartbeatPacket['heartbeat']['time'] = now.timestamp()
                heartbeatPacket['heartbeat']['id'] = 'sim'
                status_string = "%d%d%d%d%d" % (self.system_states[0].value,
                                                self.system_states[1].value,
                                                self.system_states[2].value,
                                                self.system_states[3].value,
                                                self.system_states[4].value)
                heartbeatPacket['heartbeat']['status'] = status_string
                self.sendPacket(heartbeatPacket, sendTarget)
                prevTime = now
            time.sleep(0.5)

    def __receiver(self):
        ownIPs = getIPs()
        while self._run is True:
            try:
                data, addr = self._socket.receive(1024, 1)
#             ready = select.select([self._socket], [], [], 1)
#             if ready[0]:
#                 with self.socketLock:
#                     data, addr = self._socket.recvfrom(1024)
#                 Decode
                msg = data.decode()
                packet = dict(json.loads(msg))
                print("RX: %s" % (packet))
                # Ignore things that we output
                if 'frequencies' in packet:
                    continue
                elif 'heartbeat' in packet:
                    continue
                elif 'ping' in packet:
                    continue
                elif 'exception' in packet:
                    continue
                elif 'options' in packet:
                    continue
                elif 'upgrade_ready' in packet:
                    continue
                elif 'upgrade_status' in packet:
                    continue
                elif 'upgrade_complete' in packet:
                    continue
                self.__log.info("Received %s at %.1f from %s" % (
                    msg, dt.datetime.now().timestamp(), addr))
                self.numMsgReceived += 1
                for key in packet.keys():
                    try:
                        self.MENU[key](packet[key], addr)
                    except Exception as e:
                        self.numErrors += 1
                        self.__log.exception(str(e))
                        errorPacket = {"exception": str(e),
                                       "traceback": traceback.format_exc()}
                        self.sendPacket(errorPacket, addr)
            except TimeoutError:
                pass

    def _processCommand(self, packet, addr):
        self.__log.info("Received Command Packet")
        try:
            self.CMD_MENU[packet['action']](packet, addr)
        except Exception as e:
            self.numErrors += 1
            self.__log.exception(str(e))
            errorPacket = {"exception": str(e),
                           "traceback": traceback.format_exc()}
            self.sendPacket(errorPacket, addr)

    def setSDRState(self, state):
        assert(isinstance(state, SDR_STATES))
        self.system_states[self.__SDR_STATES_POS] = state

    def setEXTState(self, state):
        assert(isinstance(state, EXT_SENSOR_STATES))
        self.system_states[self.__EXT_STATES_POS] = state

    def setSTGState(self, state):
        assert(isinstance(state, STORAGE_STATES))
        self.system_states[self.__STG_STATES_POS] = state

    def setSYSState(self, state):
        assert(isinstance(state, SYS_STATES))
        self.system_states[self.__SYS_STATES_POS] = state

    def setSWTState(self, state):
        assert(isinstance(state, SW_STATES))
        self.system_states[self.__SYS_STATES_POS] = state

    def _transmitFreqs(self, packet, addr):
        self.__log.info("Request to transmit frequencies")
        freqPacket = {"frequencies": self.frequencies}
        self.sendPacket(freqPacket, addr)

    def sendPacket(self, packet: dict, addr):
        msg = json.dumps(packet) + '\r\n'
        with self.socketLock:
            #             self._socket.sendto(msg.encode(), addr)
            self._socket.send(msg.encode(), addr)
        self.numMsgSent += 1
        self.__log.info("Sent %s at %.1f" % (
            msg, dt.datetime.now().timestamp()))
        print("TX: %s" % (packet))

    def setFreqs(self, freqs):
        self.frequencies = freqs
        self.__log.info("Frequencies updated to %s" % freqs)


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

    def setCenterFrequency(self, centerFreq: int):
        self.__centerFrequency = centerFreq

    def setSamplingFrequency(self, samplingFreq: int):
        self.__samplingFrequency = samplingFreq

    def __doGetFrequency(self, commandPayload):
        self.port.sendFrequencies(self.__frequencies)

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

    def __doCommand(self, commandPayload: dict):
        try:
            action = commandPayload['action']
        except KeyError as e:
            self.setException(str(e), traceback.format_exc())
            return
        try:
            self.__commandMap[action](commandPayload)
        except Exception as e:
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
    simulator = DroneSimulator(args.port, args.target, True)

    simulator.start()
