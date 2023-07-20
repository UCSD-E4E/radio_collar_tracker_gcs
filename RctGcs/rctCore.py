'''GCS Core Model
'''
from __future__ import annotations

import copy
import logging
import threading
from enum import Enum, auto
from typing import Any, Dict, List, Optional

import RCTComms.comms
from deprecated import deprecated
from RCTComms.options import (ALL_OPTIONS, BASE_OPTIONS, ENG_OPTIONS,
                              EXP_OPTIONS, Options, base_options_keywords,
                              engineering_options_keywords,
                              expert_options_keywords, option_param_table)

from RctGcs import ping
from RctGcs.ping import DataManager


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

class NoActiveModel(RuntimeError):
    """Raised when no active model is present
    """

class MAVModel:
    '''
    RCT Payload Model - This class should provide an object oriented view of the
    vehicle state
    '''

    # This is a global map of active MAVModels
    current_models: Dict[int, MAVModel] = {}
    active_model: Optional[int] = None

    CACHE_GOOD = 0
    CACHE_INVALID = 1
    CACHE_DIRTY = 2

    @classmethod
    def get_model(cls, *, idx: int = None) -> MAVModel:
        """Returns the active model, or the specified model

        Args:
            idx (int, optional): Idx of model if different from active. Defaults to None.

        Raises:
            NoActiveModel: No active model

        Returns:
            MAVModel: Selected model
        """
        if idx is None:
            idx = cls.active_model
        if idx is None:
            raise NoActiveModel
        return cls.current_models[idx]

    def __init__(self, receiver: RCTComms.comms.gcsComms, idx: int):
        '''
        Creates a new MAVModel
        Args:
            receiver: gcsComms Object
        '''
        self.__log = logging.getLogger('MAVModel')
        self.__idx = idx

        if idx in MAVModel.current_models:
            raise RuntimeError('Receiver already registered!')
        MAVModel.current_models[idx] = self
        # we will be greedy here and the newest model will be active.
        MAVModel.active_model = idx
        self.__log.info('Registered %d', idx)
        self.__rx = receiver

        self.__option_cache_dirty = {BASE_OPTIONS: self.CACHE_INVALID,
                                     EXP_OPTIONS: self.CACHE_INVALID,
                                     ENG_OPTIONS: self.CACHE_INVALID,
                                     ALL_OPTIONS: self.CACHE_INVALID}

        self.state = {
            'STS_sdr_status': 0,
            'STS_dir_status': 0,
            'STS_gps_status': 0,
            'STS_sys_status': 0,
            'STS_sw_status': 0,
            "UPG_state": -1,
            "UPG_msg": "",
            "VCL_track": {},
            "CONE_track": {}
        }

        self.remote_options = {option:param.default_value
                               for option, param in option_param_table.items()}

        self.EST_mgr = DataManager()

        self.__callbacks = {}
        for event in Events:
            self.__callbacks[event] = []
        self.lastException = [None, None]
        self.__log.info("MAVModel Created")

        self.__ackVectors = {}

        self.__rx.registerCallback(
            RCTComms.comms.EVENTS.STATUS_HEARTBEAT, self.__processHeartbeat)
        self.__rx.registerCallback(
            RCTComms.comms.EVENTS.STATUS_EXCEPTION, self.__handleRemoteException)
        self.__rx.registerCallback(
            RCTComms.comms.EVENTS.CONFIG_FREQUENCIES, self.__processFrequencies)
        self.__rx.registerCallback(
            RCTComms.comms.EVENTS.GENERAL_NO_HEARTBEAT, self.__processNoHeartbeat)
        self.__rx.registerCallback(
            RCTComms.comms.EVENTS.CONFIG_OPTIONS, self.__processOptions)
        self.__rx.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_ACK, self.__processAck)
        self.__rx.registerCallback(
            RCTComms.comms.EVENTS.GENERAL_NO_HEARTBEAT, self.__processNoHeartbeat)
        self.__rx.registerCallback(
            RCTComms.comms.EVENTS.DATA_PING, self.__processPing)
        self.__rx.registerCallback(
            RCTComms.comms.EVENTS.DATA_VEHICLE, self.__processVehicle)
        self.__rx.registerCallback(
            RCTComms.comms.EVENTS.DATA_CONE, self.__processCone)

    def start(self, guiTickCallback=None):
        '''
        Initializes the MAVModel object

        Args:
            guiTickCallback: Callback to a function for progress bar.  This
                             shall be a function with no parameters to be called
                             for progress
        '''
        self.__rx.start(gui=guiTickCallback)
        self.__log.info("MAVModel started")

    def __processFrequencies(self, packet: RCTComms.comms.rctFrequenciesPacket, addr: str):
        '''
        Internal callback to handle frequency messages
        Args:
            packet: Frequency message payload
            addr: Source of packet as a string
        '''
        self.__log.info("Received frequencies")
        self.remote_options[Options.TGT_FREQUENCIES] = packet.frequencies
        self.__option_cache_dirty[ALL_OPTIONS] = self.CACHE_GOOD
        for callback in self.__callbacks[Events.GetFreqs]:
            callback()

    def __processOptions(self, packet: RCTComms.comms.rctOptionsPacket, addr: str):
        '''
        Internal callback to handle option messages
        Args:
            packet: Options packet payload
            addr: Source of packet
        '''
        self.__log.info('Received options')
        for parameter in packet.options:
            self.remote_options[parameter] = packet.options[parameter]
        if packet.scope >= BASE_OPTIONS:
            self.__option_cache_dirty[BASE_OPTIONS] = self.CACHE_GOOD
        if packet.scope >= EXP_OPTIONS:
            self.__option_cache_dirty[EXP_OPTIONS] = self.CACHE_GOOD
        if packet.scope >= ENG_OPTIONS:
            self.__option_cache_dirty[ENG_OPTIONS] = self.CACHE_GOOD

        for callback in self.__callbacks[Events.GetOptions]:
            callback()

    def __processHeartbeat(self, packet: RCTComms.comms.rctHeartBeatPacket, addr: str):
        '''
        Internal callback to handle heartbeat messages
        Args:
            packet: Heartbeat packet payload
            addr: Source of packet
        '''
        self.__log.info("Received heartbeat")
        self.state['STS_sdr_status'] = SDR_INIT_STATES(packet.sdrState)
        self.state['STS_dir_status'] = OUTPUT_DIR_STATES(
            packet.storageState)
        self.state['STS_gps_status'] = EXTS_STATES(packet.sensorState)
        self.state['STS_sys_status'] = RCT_STATES(packet.systemState)
        self.state['STS_sw_status'] = packet.switchState
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

    def __processUpgradeStatus(self, packet: RCTComms.comms.rctUpgradeStatusPacket, addr: str):
        '''
        Internal callback to handle upgrade status messages
        Args:
            packet:    Upgrade Status packet
            addr:    Source address
        '''
        # self.remote_options['UPG_state'] = packet.state
        # self.remote_options['UPG_msg'] = packet.msg
        for callback in self.__callbacks[Events.UpgradeStatus]:
            callback()

    def stop(self):
        '''
        Stops the MAVModel and underlying resources
        '''
        self.__rx.stop()
        MAVModel.current_models.pop(self.__idx)
        if self.__idx == MAVModel.active_model:
            MAVModel.active_model = None
        self.__log.info("MAVModel stopped")

    def registerCallback(self, event: Events, callback):
        '''
        Registers a callback for the specified event
        Args:
            event:    Event to trigger on
            callback:    Callback to call
        '''
        assert(isinstance(event, Events))
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
        self.__rx.sendPacket(RCTComms.comms.rctSTARTCommand())
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
        self.__rx.sendPacket(RCTComms.comms.rctSTOPCommand())
        self.__log.info("Sent stop command")
        event.wait(timeout=timeout)
        if not self.__ackVectors.pop(0x09)[1]:
            raise RuntimeError('STOP NACKED')

    def getFrequencies(self, timeout) -> List[int]:
        '''
        Retrieves the PRX_frequencies from the payload
        Args:
            timeout:    Seconds to wait before timing out
        '''
        if self.__option_cache_dirty[ALL_OPTIONS] == self.CACHE_INVALID:
            frequencyPacketEvent = threading.Event()
            frequencyPacketEvent.clear()
            self.registerCallback(
                Events.GetFreqs, frequencyPacketEvent.set)

            self.__rx.sendPacket(RCTComms.comms.rctGETFCommand())
            self.__log.info("Sent getF command")

            frequencyPacketEvent.wait(timeout=timeout)
        return self.remote_options[Options.TGT_FREQUENCIES]

    def __handleRemoteException(self, packet: RCTComms.comms.rctExceptionPacket, addr):
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

        self.__option_cache_dirty[ALL_OPTIONS] = self.CACHE_DIRTY

        event = threading.Event()
        self.__ackVectors[0x03] = [event, 0]
        self.__rx.sendPacket(RCTComms.comms.rctSETFCommand(freqs))
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
        if frequency in self.remote_options[Options.TGT_FREQUENCIES]:
            return
        self.setFrequencies(
            self.remote_options[Options.TGT_FREQUENCIES] + [frequency], timeout)

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
        if frequency not in self.remote_options[Options.TGT_FREQUENCIES]:
            raise RuntimeError('Invalid frequency')
        new_freqs: List[int] = copy.deepcopy(self.remote_options[Options.TGT_FREQUENCIES])
        new_freqs.remove(frequency)
        self.setFrequencies(new_freqs, timeout)

    @deprecated
    def getOptions(self, scope: int, timeout):
        return self.get_options(scope=scope, timeout=timeout)

    def get_options(self, scope: int, timeout: int) -> Dict[Options, Any]:
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

        self.__rx.sendPacket(RCTComms.comms.rctGETOPTCommand(scope))
        self.__log.info("Sent GETOPT command")

        optionPacketEvent.wait(timeout=timeout)

        acceptedKeywords: List[Options] = []
        if scope >= BASE_OPTIONS:
            acceptedKeywords.extend(base_options_keywords)
        if scope >= EXP_OPTIONS:
            acceptedKeywords.extend(expert_options_keywords)
        if scope >= ENG_OPTIONS:
            acceptedKeywords.extend(engineering_options_keywords)

        return {key: self.remote_options[key] for key in acceptedKeywords}

    def getOption(self, keyword: Options, timeout:int=10) -> Any:
        '''
        Retrieves the specific option by keyword
        Args:
            keyword:    Keyword of option to retrieve
            timeout:    Timeout in seconds
        '''
        if keyword in base_options_keywords:
            if self.__option_cache_dirty[BASE_OPTIONS] == self.CACHE_INVALID:
                return self.getOptions(BASE_OPTIONS, timeout)[keyword]
        if keyword in expert_options_keywords:
            if self.__option_cache_dirty[EXP_OPTIONS] == self.CACHE_INVALID:
                return self.getOptions(EXP_OPTIONS, timeout)[keyword]
        if keyword in engineering_options_keywords:
            if self.__option_cache_dirty[ENG_OPTIONS] == self.CACHE_INVALID:
                return self.getOptions(ENG_OPTIONS, timeout)[keyword]
        return copy.deepcopy(self.remote_options[keyword])

    def setOptions(self, timeout, **kwargs):
        '''
        Sets the specified options on the payload
        Args:
            timeout:    Timeout in seconds
            kwargs:    Options to set by keyword
        '''
        scope = BASE_OPTIONS
        for keyword in kwargs:
            if keyword in base_options_keywords:
                scope = max(scope, BASE_OPTIONS)
            elif keyword in expert_options_keywords:
                scope = max(scope, EXP_OPTIONS)
            elif keyword in engineering_options_keywords:
                scope = max(scope, ENG_OPTIONS)
            else:
                raise KeyError

        print(scope)
        self.remote_options.update(kwargs)
        acceptedKeywords = []
        if scope >= BASE_OPTIONS:
            self.__option_cache_dirty[BASE_OPTIONS] = self.CACHE_DIRTY
            acceptedKeywords.extend(base_options_keywords)
        if scope >= EXP_OPTIONS:
            self.__option_cache_dirty[EXP_OPTIONS] = self.CACHE_DIRTY
            acceptedKeywords.extend(expert_options_keywords)
        if scope >= ENG_OPTIONS:
            self.__option_cache_dirty[ENG_OPTIONS] = self.CACHE_DIRTY
            acceptedKeywords.extend(engineering_options_keywords)

        event = threading.Event()
        self.__ackVectors[0x05] = [event, 0]
        self.__rx.sendPacket(RCTComms.comms.rctSETOPTCommand(
            scope, {key: self.remote_options[key] for key in acceptedKeywords}))
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
            self.__rx.sendPacket(RCTComms.comms.rctUpgradePacket(i+1, numPackets, byteStream[startInd:endInd]))

    def __processPing(self, packet: RCTComms.comms.rctPingPacket, addr: str):
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

    def __processVehicle(self, packet: RCTComms.comms.rctVehiclePacket, addr: str):
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

    def __processCone(self, packet: RCTComms.comms.rctConePacket, addr: str):
        coordinate = [packet.lat, packet.lon, packet.alt, packet.power, packet.angle]
        self.state['CONE_track'][packet.timestamp] = coordinate
        for callback in self.__callbacks[Events.ConeInfo]:
            callback()

    def __processAck(self, packet: RCTComms.comms.rctACKCommand, addr: str):
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

    @classmethod
    def close_all(cls) -> None:
        models = list(cls.current_models.values())
        for model in models:
            model.stop()
        assert len(cls.current_models) == 0