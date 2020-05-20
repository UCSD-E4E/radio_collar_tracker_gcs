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
# 05/18/20  NH  Updated to use binary interface and dictionary options
# 05/01/20  AG  Added __processOptions, getOptions, and setOptions methods
# 04/27/20  NH  Fixed getFrequencies callback
# 04/26/20  NH  Fixed getFrequencies name, added sleep hack to getFrequencies,
#                 added object for options, removed builtins import
# 04/20/20  NH  Updated docstrings and imports
# 04/19/20  NH  Added event clear for frequency packet event
# 04/17/20  NH  Fixed callback map, added timeout to getFreqs
# 04/16/20  NH  Added auto enum, moved enums to module scope, updated comms
#               eventing, added event for no heartbeat, added start and
#               stop mission functions, implemented setFrequencies
# 04/14/20  NH  Initial commit
#
###############################################################################

from enum import Enum, auto
import rctComms
import logging
import threading
import ping

class rctOptions:
    def __init__(self):
        pass

class SDR_INIT_STATES(Enum):
    '''
    SDR Initialization States

    find_devices - The system is searching for valid devices
    wait_recycle - The system is cycling to retry initialization
    usrp_prove   - The system is attempting to probe and initialize the URSP
    rdy          - The system has initialized the USRP and is ready
    fail         - The system has encountered a fatal error initializing the
                   USRP
    '''
    find_devices = 0
    wait_recycle = 1
    usrp_probe = 2
    rdy = 3
    fail = 4

class EXTS_STATES(Enum):
    '''
    GPS Initialization State

    get_tty      - The system is opening the serial port
    get_msg      - The system is waiting for a message from the external
                   sensors
    wait_recycle - The system is cycling to retry initialization
    rdy          - The system has initialized the external sensors and is
                   ready
    fail         - The system has encountered a fatal error initializing the
                   external sensors
    '''
    get_tty = 0
    get_msg = 1
    wait_recycle = 2
    rdy = 3
    fail = 4

class OUTPUT_DIR_STATES(Enum):
    '''
    Output Directory Initialization State

    get_output_dir   - The system is obtaining the output directory path
    check_output_dir - The system is checking that the output directory is
                       located on removable media
    check_space      - The system is checking that the external media has
                       sufficient space
    wait_recycle     - The system is cycling to retry initialization
    rdy              - The system has initialized the storage location and
                       is ready
    fail             - The system has encountered a fatal error initializing
                       the external storage
    '''
    get_output_dir = 0
    check_output_dir = 1
    check_space = 2
    wait_recycle = 3
    rdy = 4
    fail = 5

class RCT_STATES(Enum):
    '''
    System Initialization State

    init       - The system is starting all initialization threads
    wait_init  - The system is waiting for initialization tasks to complete
    wait_start - The system is initialized and is waiting for the start
                 command
    start      - The system is starting the mission software
    wait_end   - The system is running and waiting for the stop command
    finish     - The system is stopping the mission software and ensuring
                 data is written to disk
    fail       - The system has encountered a fatal error
    '''
    init = 0
    wait_init = 1
    wait_start = 2
    start = 3
    wait_end = 4
    finish = 5
    fail = 6

class Events(Enum):
    '''
    Callback Events

    Hearbeat  - Callback when a heartbeat message is received
    Exception - Callback when an exception message is received
    GetFreqs  - Callback when the payload broadcasts a set of frequencies
    GetOptions - Callback when the payload broadcasts its parameters
    '''
    Heartbeat = auto(),
    Exception = auto(),
    GetFreqs = auto(),
    GetOptions = auto(),
    NoHeartbeat = auto(),
    NewPing = auto(),
    NewEstimate = auto(),
    UpgradeStatus = auto()
    VehicleInfo = auto()

class MAVModel:
    '''
    RCT Payload Model - This class should provide an object oriented view of the
    vehicle state
    '''

    BASE_OPTIONS = 0x00
    EXP_OPTIONS = 0x01
    ENG_OPTIONS = 0xFF

    __baseOptionKeywords = ['SDR_centerFreq', 'SDR_samplingFreq', 'SDR_gain']
    __expOptionKeywords = ['DSP_pingWidth', 'DSP_pingSNR',
                           'DSP_pingMax', 'DSP_pingMin', 'SYS_outputDir']
    __engOptionKeywords = ['GPS_mode',
                           'GPS_baud', 'GPS_device', 'SYS_autostart']

    def __init__(self, receiver: rctComms.gcsComms):
        '''
        Creates a new MAVModel
        :param receiver: gcsComms Object
        :type receiver: rctComms.gcsComms
        '''
        self.__log = logging.getLogger('rctGCS:MAVModel')
        self.__rx = receiver

        self.state = {
            'STS_sdrStatus': 0,
            'STS_dirStatus': 0,
            'STS_gpsStatus': 0,
            'STS_sysStatus': 0,
            'STS_swStatus': 0,
            "UPG_state": -1,
            "UPG_msg": "",
            "VCL_track": {},
        }

        self.__options = {
            "TGT_frequencies": [],
            "SDR_centerFreq": 0,
            "SDR_samplingFreq": 0,
            "SDR_gain": 0,
            "DSP_pingWidth": 0,
            "DSP_pingSNR": 0,
            "DSP_pingMax": 0,
            "DSP_pingMin": 0,
            "GPS_mode": 0,
            "GPS_device": "",
            "GPS_baud": 0,
            "SYS_outputDir": "",
            "SYS_autostart": False,
        }

        self.EST_mgr = ping.DataManager()

        self.__callbacks = {}
        for event in Events:
            self.__callbacks[event] = []
        self.lastException = [None, None]
        self.__log.info("MAVModel Created")

        self.__ackVectors = {}

        self.__rx.registerCallback(
            rctComms.EVENTS.STATUS_HEARTBEAT, self.__processHeartbeat)
        self.__rx.registerCallback(
            rctComms.EVENTS.STATUS_EXCEPTION, self.__handleRemoteException)
        self.__rx.registerCallback(
            rctComms.EVENTS.CONFIG_FREQUENCIES, self.__processFrequencies)
        self.__rx.registerCallback(
            rctComms.EVENTS.GENERAL_NO_HEARTBEAT, self.__processNoHeartbeat)
        self.__rx.registerCallback(
            rctComms.EVENTS.CONFIG_OPTIONS, self.__processOptions)
        self.__rx.registerCallback(
            rctComms.EVENTS.COMMAND_ACK, self.__processAck)
        self.__rx.registerCallback(
            rctComms.EVENTS.NO_HEARTBEAT, self.__processNoHeartbeat)

    def start(self, guiTickCallback=None):
        '''
        Initializes the MAVModel object
        :param guiTickCallback: Callback to a function for progress bar
        :type guiTickCallback: Function with no parameters to be called for
            progress
        '''
        self.__rx.start(guiTickCallback)
        self.__log.info("MVAModel started")

    def __processFrequencies(self, packet: rctComms.rctFrequenciesPacket, addr: str):
        '''
        Internal callback to handle frequency messages
        :param packet: Frequency message payload
        :type packet: List of integers
        :param addr: Source of packet
        :type addr: str
        '''
        self.__log.info("Received frequencies")
        self.__options['TGT_frequencies'] = packet.frequencies
        for callback in self.__callbacks[Events.GetFreqs]:
            callback()

    def __processOptions(self, packet: rctComms.rctOptionsPacket, addr: str):
        self.__log.info('Received options')
        for parameter in packet.options:
            self.__options[parameter] = packet.options[parameter]
        for callback in self.__callbacks[Events.GetOptions]:
            callback()

    def __processHeartbeat(self, packet: rctComms.rctHeartBeatPacket, addr: str):
        '''
        Internal callback to handle heartbeat messages
        :param packet: Heartbeat packet payload
        :type packet: dict
        :param addr: Source of packet
        :type addr: str
        '''
        self.__log.info("Received heartbeat")
        self.state['STS_sdrStatus'] = SDR_INIT_STATES(packet.sdrState)
        self.state['STS_dirStatus'] = OUTPUT_DIR_STATES(
            packet.storageState)
        self.state['STS_gpsStatus'] = EXTS_STATES(packet.sensorState)
        self.state['STS_sysStatus'] = RCT_STATES(packet.systemState)
        self.state['STS_swStatus'] = packet.switchState
        for callback in self.__callbacks[Events.Heartbeat]:
            callback()

    def __processNoHeartbeat(self, packet, addr):
        '''
        Internal callback to handle no hearbeat messages
        :param packet: None
        :type packet: None
        :param addr: None
        :type addr: None
        '''
        for callback in self.__callbacks[Events.NoHeartbeat]:
            callback()

    def __processUpgradeStatus(self, packet: rctComms.rctUpgradeStatusPacket, addr: str):
        self.__options['UPG_state'] = packet.state
        self.__options['UPG_msg'] = packet.msg
        for callback in self.__callback[Events.UpgradeStatus]:
            callback()

    def stop(self):
        '''
        Stops the MAVModel and underlying resources
        '''
        self.__rx.stop()
        self.__log.info("MVAModel stopped")

    def registerCallback(self, event: Events, callback):
        '''
        Registers a callback for the specified event
        :param event: Event to trigger on
        :type event: rctCore.Events
        :param callback: Callback to call
        :type callback:
        '''
        assert(isinstance(event, Events))
        if event not in self.__callbacks:
            self.__callbacks[event] = [callback]
        else:
            self.__callbacks[event].append(callback)

    def startMission(self, timeout):
        '''
        Sends the start mission command
        '''
        event = threading.Event()
        event.clear()
        self.__ackVectors[0x07] = [event, 0]
        self.__rx.sendPacket(rctComms.rctSTARTCommand())
        self.__log.info("Sent start command")
        event.wait(timeout=timeout)
        if not self.__ackVectors.pop(0x07)[1]:
            raise RuntimeError('START NACKED')

    def stopMission(self, timeout):
        '''
        Sends the stop mission command
        '''
        event = threading.Event()
        event.clear()
        self.__ackVectors[0x09] = [event, 0]
        self.__rx.sendPacket(rctComms.rctSTOPCommand())
        self.__log.info("Sent stop command")
        event.wait(timeout=timeout)
        if not self.__ackVectors.pop(0x09)[1]:
            raise RuntimeError('STOP NACKED')

    def getFrequencies(self, timeout):
        '''
        Retrieves the PRX_frequencies from the payload

        :param timeout: Seconds to wait before timing out
        :type timeout: number
        '''
        frequencyPacketEvent = threading.Event()
        frequencyPacketEvent.clear()
        self.registerCallback(
            Events.GetFreqs, frequencyPacketEvent.set)

        self.__rx.sendPacket(rctComms.rctGETFCommand())
        self.__log.info("Sent getF command")

        frequencyPacketEvent.wait(timeout=timeout)
        return self.__options['TGT_frequencies']

    def __handleRemoteException(self, packet: rctComms.rctExceptionPacket, addr):
        '''
        Internal callback to handle traceback messages
        :param packet: Traceback packet payload
        :type packet: str
        :param addr: Source of packet
        :type addr: str
        '''
        self.__log.exception("Remote Exception: %s" % packet.exception)
        self.__log.exception("Remote Traceback: %s" % packet.traceback)
        self.lastException[0] = packet.exception
        self.lastException[1] = packet.traceback
#         This is a hack - there is no guarantee that the traceback occurs after
#         the exception!
        for callback in self.__callbacks[Events.Exception]:
            callback()

    def setFrequencies(self, freqs, timeout):
        '''
        Sends the command to set the specified PRX_frequencies
        :param freqs: Frequencies to set
        :type freqs: list
        '''
        assert(isinstance(freqs, list))
        for freq in freqs:
            assert(isinstance(freq, int))
        # TODO: Validate PRX_frequencies here?
        event = threading.Event()
        self.__ackVectors[0x03] = [event, 0]
        self.__rx.sendPacket(rctComms.rctSETFCommand(freqs))
        self.__log.info("Set setF command")
        event.wait(timeout=timeout)
        if not self.__ackVectors.pop(0x03)[1]:
            raise RuntimeError("SETF NACKED")

    def getOptions(self, scope: int, timeout):
        optionPacketEvent = threading.Event()
        optionPacketEvent.clear()
        self.registerCallback(
            Events.GetOptions, optionPacketEvent.set)

        self.__rx.sendPacket(rctComms.rctGETOPTCommand(scope))
        self.__log.info("Sent GETOPT command")

        optionPacketEvent.wait(timeout=timeout)

        acceptedKeywords = []
        if scope >= self.BASE_OPTIONS:
            acceptedKeywords.extend(self.__baseOptionKeywords)
        if scope >= self.EXP_OPTIONS:
            acceptedKeywords.extend(self.__expOptionKeywords)
        if scope >= self.ENG_OPTIONS:
            acceptedKeywords.extend(self.__engOptionKeywords)

        return {key: self.__options[key] for key in acceptedKeywords}

    def setOptions(self, timeout, **kwargs):
        scope = self.BASE_OPTIONS
        for keyword in kwargs:
            if keyword in self.__baseOptionKeywords:
                scope = max(scope, self.BASE_OPTIONS)
            elif keyword in self.__expOptionKeywords:
                scope = max(scope, self.EXP_OPTIONS)
            elif keyword in self.__engOptionKeywords:
                scope = max(scope, self.ENG_OPTIONS)
            else:
                raise KeyError

        self.__options.update(kwargs)
        acceptedKeywords = []
        if scope >= self.BASE_OPTIONS:
            acceptedKeywords.extend(self.__baseOptionKeywords)
        if scope >= self.EXP_OPTIONS:
            acceptedKeywords.extend(self.__expOptionKeywords)
        if scope >= self.ENG_OPTIONS:
            acceptedKeywords.extend(self.__engOptionKeywords)

        event = threading.Event()
        self.__ackVectors[0x05] = [event, 0]
        self.__rx.sendPacket(rctComms.rctSETOPTCommand(
            scope, **{key: self.__options[key] for key in acceptedKeywords}))
        self.__log.info('Sent GETOPT command')
        event.wait(timeout=timeout)
        if not self.__ackVectors.pop(0x05)[1]:
            raise RuntimeError("GETOPT NACKED")

    def __processPing(self, packet: rctComms.rctPingPacket, addr: str):
        ping = ping.rctPing.fromPacket(packet)
        estimate = self.EST_mgr.addPing(ping)
        for callback in self.__callbacks[Events.NewPing]:
            callback()
        if estimate is not None:
            for callback in self.__callbacks[Events.NewEstimate]:
                callback()

    def __processVehicle(self, packet: rctComms.rctVehiclePacket, addr: str):
        coordinate = [packet.lat, packet.lon. packet.alt, packet.hdg]
        self.state['VCL_track'][packet.timestamp] = coordinate
        for callback in self.__callbacks[Events.VehicleInfo]:
            callback()

    def __processAck(self, packet: rctComms.rctACKCommand, addr: str):
        commandID = packet.commandID
        if commandID in self.__ackVectors:
            vector = self.__ackVectors[commandID]
            vector[1] = packet.ack
            vector[0].set()
