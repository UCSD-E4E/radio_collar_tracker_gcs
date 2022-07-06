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
# 08/06/20  NH  Fixed syntax and variable masking
# 07/30/20  NH  Updated rctCore.MAVModel docstrings
# 05/25/20  NH  Added docstring to new events, added callback to process pings,
#                 added type hint to setFrequencies
# 05/20/20  NH  Fixed logging message in MAVmodel.setOptions
# 05/19/20  NH  Removed rctOptions skeleton, added cache bits for options,
#                 renamed rctCore.__options to rctCore.PP_options, fixed
#                 NO_HEARTBEAT name, added incremental frequency modifiers,
#                 added single option getter
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
import RCTComms.comms as rctComms
import logging
import threading
import ping
import copy


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
    NoHeartbeat - Callback when no heartbeat has been received for GC_HeartbeatWatchdogTime seconds
    NewPing - Callback when new ping is received
    NewEstimate - Callback when new estimate is generated

    '''
    Heartbeat = auto(),
    Exception = auto(),
    GetFreqs = auto(),
    GetOptions = auto(),
    NoHeartbeat = auto(),
    NewPing = auto(),
    NewEstimate = auto(),
    UpgradeStatus = auto(),
    VehicleInfo = auto(),
    ConeInfo = auto()


class MAVModel:
    '''
    RCT Payload Model - This class should provide an object oriented view of the
    vehicle state
    '''

    BASE_OPTIONS = 0x00
    EXP_OPTIONS = 0x01
    ENG_OPTIONS = 0xFF
    TGT_PARAMS = 0x100

    CACHE_GOOD = 0
    CACHE_INVALID = 1
    CACHE_DIRTY = 2

    __baseOptionKeywords = ['SDR_centerFreq', 'SDR_samplingFreq', 'SDR_gain']
    __expOptionKeywords = ['DSP_pingWidth', 'DSP_pingSNR',
                           'DSP_pingMax', 'DSP_pingMin', 'SYS_outputDir']
    __engOptionKeywords = ['GPS_mode',
                           'GPS_baud', 'GPS_device', 'SYS_autostart']

    def __init__(self, receiver: rctComms.gcsComms):
        '''
        Creates a new MAVModel
        Args:
            receiver: gcsComms Object
        '''
        self.__log = logging.getLogger('rctGCS:MAVModel')
        self.__rx = receiver

        self.__optionCacheDirty = {self.BASE_OPTIONS: self.CACHE_INVALID,
                                   self.EXP_OPTIONS: self.CACHE_INVALID,
                                   self.ENG_OPTIONS: self.CACHE_INVALID,
                                   self.TGT_PARAMS: self.CACHE_INVALID}

        self.state = {
            'STS_sdrStatus': 0,
            'STS_dirStatus': 0,
            'STS_gpsStatus': 0,
            'STS_sysStatus': 0,
            'STS_swStatus': 0,
            "UPG_state": -1,
            "UPG_msg": "",
            "VCL_track": {},
            "CONE_track": {}
        }

        self.PP_options = {
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
            rctComms.EVENTS.GENERAL_NO_HEARTBEAT, self.__processNoHeartbeat)
        self.__rx.registerCallback(
            rctComms.EVENTS.DATA_PING, self.__processPing)
        self.__rx.registerCallback(
            rctComms.EVENTS.DATA_VEHICLE, self.__processVehicle)
        self.__rx.registerCallback(
            rctComms.EVENTS.DATA_CONE, self.__processCone)

    def start(self, guiTickCallback=None):
        '''
        Initializes the MAVModel object
        
        Args:
            guiTickCallback: Callback to a function for progress bar.  This 
                             shall be a function with no parameters to be called
                             for progress
        '''
        self.__rx.start(guiTickCallback)
        self.__log.info("MVAModel started")

    def __processFrequencies(self, packet: rctComms.rctFrequenciesPacket, addr: str):
        '''
        Internal callback to handle frequency messages
        Args:
            packet: Frequency message payload
            addr: Source of packet as a string
        '''
        self.__log.info("Received frequencies")
        self.PP_options['TGT_frequencies'] = packet.frequencies
        self.__optionCacheDirty[self.TGT_PARAMS] = self.CACHE_GOOD
        for callback in self.__callbacks[Events.GetFreqs]:
            callback()

    def __processOptions(self, packet: rctComms.rctOptionsPacket, addr: str):
        '''
        Internal callback to handle option messages
        Args:
            packet: Options packet payload
            addr: Source of packet
        '''
        self.__log.info('Received options')
        for parameter in packet.options:
            self.PP_options[parameter] = packet.options[parameter]
        if packet.scope >= self.BASE_OPTIONS:
            self.__optionCacheDirty[self.BASE_OPTIONS] = self.CACHE_GOOD
        if packet.scope >= self.EXP_OPTIONS:
            self.__optionCacheDirty[self.EXP_OPTIONS] = self.CACHE_GOOD
        if packet.scope >= self.ENG_OPTIONS:
            self.__optionCacheDirty[self.ENG_OPTIONS] = self.CACHE_GOOD

        for callback in self.__callbacks[Events.GetOptions]:
            callback()

    def __processHeartbeat(self, packet: rctComms.rctHeartBeatPacket, addr: str):
        '''
        Internal callback to handle heartbeat messages
        Args:
            packet: Heartbeat packet payload
            addr: Source of packet
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
        Args:
            packet:    None
            addr:    None
        '''
        for callback in self.__callbacks[Events.NoHeartbeat]:
            callback()

    def __processUpgradeStatus(self, packet: rctComms.rctUpgradeStatusPacket, addr: str):
        '''
        Internal callback to handle upgrade status messages
        Args:
            packet:    Upgrade Status packet
            addr:    Source address
        '''
        self.PP_options['UPG_state'] = packet.state
        self.PP_options['UPG_msg'] = packet.msg
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
        Args:
            event:    Event to trigger on
            callback:    Callback to call
        '''
        assert(isinstance(event, Events))
        if event not in self.__callbacks:
            self.__callbacks[event] = [callback]
        else:
            self.__callbacks[event].append(callback)

    def startMission(self, timeout:int):
        '''
        Sends the start mission command
        Args:
            timeout: Timeout in seconds
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
        Args: 
                timeout: Timeout in seconds
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
        Args:
            timeout:    Seconds to wait before timing out
        '''
        if self.__optionCacheDirty[self.TGT_PARAMS] == self.CACHE_INVALID:
            frequencyPacketEvent = threading.Event()
            frequencyPacketEvent.clear()
            self.registerCallback(
                Events.GetFreqs, frequencyPacketEvent.set)

            self.__rx.sendPacket(rctComms.rctGETFCommand())
            self.__log.info("Sent getF command")

            frequencyPacketEvent.wait(timeout=timeout)
        return self.PP_options['TGT_frequencies']

    def __handleRemoteException(self, packet: rctComms.rctExceptionPacket, addr):
        '''
        Internal callback to handle traceback messages
        Args:
            packet: Traceback packet payload
            addr: Source of packet
        '''
        self.__log.exception("Remote Exception: %s" % packet.exception)
        self.__log.exception("Remote Traceback: %s" % packet.traceback)
        self.lastException[0] = packet.exception
        self.lastException[1] = packet.traceback
#         This is a hack - there is no guarantee that the traceback occurs after
#         the exception!
        for callback in self.__callbacks[Events.Exception]:
            callback()

    def setFrequencies(self, freqs: list, timeout):
        '''
        Sends the command to set the specified PRX_frequencies
        Args:
            freqs: Frequencies to set as a list
            timeout: Timeout in seconds
        '''
        assert(isinstance(freqs, list))
        for freq in freqs:
            assert(isinstance(freq, int))

        self.__optionCacheDirty[self.TGT_PARAMS] = self.CACHE_DIRTY

        event = threading.Event()
        self.__ackVectors[0x03] = [event, 0]
        self.__rx.sendPacket(rctComms.rctSETFCommand(freqs))
        self.__log.info("Set setF command")
        event.wait(timeout=timeout)
        if not self.__ackVectors.pop(0x03)[1]:
            raise RuntimeError("SETF NACKED")

    def addFrequency(self, frequency: int, timeout):
        '''
        Adds the specified frequency to the target frequencies.
        
        If the specified frequency is already in TGT_frequencies, then this 
        function does nothing.  Otherwise, this function will update the 
        TGT_frequencies on the payload.
        Args:
            frequency:    Frequency to add
            timeout:    Timeout in seconds
        '''
        if frequency in self.PP_options['TGT_frequencies']:
            return
        else:
            self.setFrequencies(
                self.PP_options['TGT_frequencies'] + [frequency], timeout)

    def removeFrequency(self, frequency: int, timeout):
        '''
        Removes the specified frequency from the target frequencies.
        
        If the specified frequency is not in TGT_frequencies, then this function
        raises a RuntimeError.  Otherwise, this function will update the 
        TGT_frequencies on the payload.
        Args:
            frequency:    Frequency to remove
            timeout:    Timeout in seconds
        '''
        if frequency not in self.PP_options['TGT_frequencies']:
            raise RuntimeError('Invalid frequency')
        else:
            newFreqs = copy.deepcopy(self.PP_options['TGT_frequencies'])
            newFreqs.remove(frequency)
            self.setFrequencies(newFreqs, timeout)

    def getOptions(self, scope: int, timeout):
        '''
        Retrieves and returns the options as a dictionary from the remote.
        
        scope should be set to one of rctCore.MAVModel.BASE_OPTIONS, 
        rctCore.MAVModel.EXP_OPTIONS, or rctCore.MAVModel.ENG_OPTIONS.
        Args:
            scope: Scope of options to return
            timeout: Timeout in seconds
        '''
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

        return {key: self.PP_options[key] for key in acceptedKeywords}

    def getOption(self, keyword, timeout=10):
        '''
        Retrieves the specific option by keyword
        Args:
            keyword:    Keyword of option to retrieve
            timeout:    Timeout in seconds
        '''
        if keyword in self.__baseOptionKeywords:
            if self.__optionCacheDirty[self.BASE_OPTIONS] == self.CACHE_INVALID:
                return self.getOptions(self.BASE_OPTIONS, timeout)[keyword]
        if keyword in self.__expOptionKeywords:
            if self.__optionCacheDirty[self.EXP_OPTIONS] == self.CACHE_INVALID:
                return self.getOptions(self.EXP_OPTIONS, timeout)[keyword]
        if keyword in self.__engOptionKeywords:
            if self.__optionCacheDirty[self.ENG_OPTIONS] == self.CACHE_INVALID:
                return self.getOptions(self.ENG_OPTIONS, timeout)[keyword]
        return copy.deepcopy(self.PP_options[keyword])

    def setOptions(self, timeout, **kwargs):
        '''
        Sets the specified options on the payload
        Args:
            timeout:    Timeout in seconds
            kwargs:    Options to set by keyword
        '''
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

        print(scope)
        self.PP_options.update(kwargs)
        acceptedKeywords = []
        if scope >= self.BASE_OPTIONS:
            self.__optionCacheDirty[self.BASE_OPTIONS] = self.CACHE_DIRTY
            acceptedKeywords.extend(self.__baseOptionKeywords)
        if scope >= self.EXP_OPTIONS:
            self.__optionCacheDirty[self.EXP_OPTIONS] = self.CACHE_DIRTY
            acceptedKeywords.extend(self.__expOptionKeywords)
        if scope >= self.ENG_OPTIONS:
            self.__optionCacheDirty[self.ENG_OPTIONS] = self.CACHE_DIRTY
            acceptedKeywords.extend(self.__engOptionKeywords)

        event = threading.Event()
        self.__ackVectors[0x05] = [event, 0]
        self.__rx.sendPacket(rctComms.rctSETOPTCommand(
            scope, **{key: self.PP_options[key] for key in acceptedKeywords}))
        self.__log.info('Sent SETOPT command with scope %d' % scope)
        event.wait(timeout=timeout)
        if not self.__ackVectors.pop(0x05)[1]:
            raise RuntimeError("SETOPT NACKED")
        
    def sendUpgradePacket(self, byteStream): 
        numPackets = -1
        if (len(byteStream) % 1000) != 0:
            numPackets = len(byteStream)/1000 + 1
        else:
            numPackets = len(byteStream)/1000
        for i in range(0,numPackets):
            startInd = i*1000
            endInd = startInd + 1000
            self.__rx.sendPacket(rctComms.rctUpgradePacket(i+1, numPackets, byteStream[startInd:endInd]))

    def __processPing(self, packet: rctComms.rctPingPacket, addr: str):
        '''
        Internal callback to handle ping packets from the payload.
        Args:
            packet: Ping packet
            addr: Source address
        '''
        pingObj = ping.rctPing.fromPacket(packet)
        estimate = self.EST_mgr.addPing(pingObj)
        for callback in self.__callbacks[Events.NewPing]:
            callback()
        if estimate is not None:
            for callback in self.__callbacks[Events.NewEstimate]:
                callback()

    def __processVehicle(self, packet: rctComms.rctVehiclePacket, addr: str):
        '''
        Internal callback to handle vehicle position packets from the payload.
        Args:
            packet:    Vehicle Position packet
            addr:    Source address
        '''
        coordinate = [packet.lat, packet.lon, packet.alt, packet.hdg]
        self.state['VCL_track'][packet.timestamp] = coordinate
        for callback in self.__callbacks[Events.VehicleInfo]:
            callback()

    def __processCone(self, packet: rctComms.rctConePacket, addr: str):
        coordinate = [packet.lat, packet.lon, packet.alt, packet.power, packet.angle]
        self.state['CONE_track'][packet.timestamp] = coordinate
        for callback in self.__callbacks[Events.ConeInfo]:
            callback()

    def __processAck(self, packet: rctComms.rctACKCommand, addr: str):
        '''
        Internal callback to handle command ACK packets from the payload.
        Args:
            packet:    ACK message
            addr:    Source address
        '''
        commandID = packet.commandID
        if commandID in self.__ackVectors:
            vector = self.__ackVectors[commandID]
            vector[1] = packet.ack
            vector[0].set()
