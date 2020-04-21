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
from builtins import list
import rctComms
import logging
import threading


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
    '''
    Heartbeat = auto(),
    Exception = auto(),
    GetFreqs = auto(),
    NoHeartbeat = auto(),
    NewPing = auto(),
    NewEstimate = auto(),


class MAVModel:
    '''
    RCT Payload Model - This class should provide an object oriented view of the
    vehicle state
    '''

    def __init__(self, receiver: rctComms.MAVReceiver):
        '''
        Creates a new MAVModel
        :param receiver: MAVReceiver Object
        :type receiver: rctComms.MAVReceiver
        '''
        self.__log = logging.getLogger('rctGCS:MAVModel')
        self.__rx = receiver
        self.sdrStatus = 0
        self.dirStatus = 0
        self.gpsStatus = 0
        self.sysStatus = 0
        self.swStatus = 0
        self.frequencies = []
        self.__callbacks = {}
        for event in Events:
            self.__callbacks[event] = []
        self.__exceptions = []
        self.lastException = [None, None]
        self.__log.info("MAVModel Created")

        self.__rx.registerCallback(
            rctComms.EVENTS.HEARTBEAT, self.__processHeartbeat)
        self.__rx.registerCallback(
            rctComms.EVENTS.EXCEPTION, self.__handleRemoteException)
        self.__rx.registerCallback(
            rctComms.EVENTS.TRACEBACK, self.__handleRemoteTraceback)
        self.__rx.registerCallback(
            rctComms.EVENTS.FREQUENCIES, self.__processFrequencies)
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

    def __processFrequencies(self, packet, addr):
        '''
        Internal callback to handle frequency messages
        :param packet: Frequency message payload
        :type packet: List of integers
        :param addr: Source of packet
        :type addr: str
        '''
        self.__log.info("Received frequencies")
        self.frequencies = packet
        for callback in self.__callbacks[Events.GetFreqs]:
            callback()

    def __processHeartbeat(self, packet, addr):
        '''
        Internal callback to handle heartbeat messages
        :param packet: Heartbeat packet payload
        :type packet: dict
        :param addr: Source of packet
        :type addr: str
        '''
        self.__log.info("Received heartbeat")
        statusString = packet['status']
        self.sdrStatus = SDR_INIT_STATES(int(statusString[0]))
        self.dirStatus = OUTPUT_DIR_STATES(int(statusString[1]))
        self.gpsStatus = EXTS_STATES(int(statusString[2]))
        self.sysStatus = RCT_STATES(int(statusString[3]))
        self.swStatus = int(statusString[4])
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

    def startMission(self):
        '''
        Sends the start mission command
        '''
        self.__rx.sendCommandPacket(rctComms.COMMANDS.START)
        self.__log.info("Sent start command")

    def stopMission(self):
        '''
        Sends the stop mission command
        '''
        self.__rx.sendCommandPacket(rctComms.COMMANDS.STOP)
        self.__log.info("Sent stop command")

    def getFreqs(self, timeout: float=None):
        '''
        Retrieves the frequencies from the payload

        :param timeout: Seconds to wait before timing out
        :type timeout: number
        '''
        self.__rx.sendCommandPacket(rctComms.COMMANDS.GET_FREQUENCY)
        self.__log.info("Sent getF command")

        frequencyPacketEvent = threading.Event()
        frequencyPacketEvent.clear()
        self.registerCallback(
            Events.GetFreqs, frequencyPacketEvent.set())
        frequencyPacketEvent.wait(timeout=timeout)
        return self.frequencies

    def __handleRemoteException(self, packet, addr):
        '''
        Internal callback to handle exception messages
        :param packet: Exception packet payload
        :type packet: str
        :param addr: Source of packet
        :type addr: str
        '''
        self.__log.exception("Remote Exception: %s" % packet)
        self.lastException[0] = packet

    def __handleRemoteTraceback(self, packet, addr):
        '''
        Internal callback to handle traceback messages
        :param packet: Traceback packet payload
        :type packet: str
        :param addr: Source of packet
        :type addr: str
        '''
        self.__log.exception("Remote Traceback: %s" % packet)
        self.lastException[1] = packet
#         This is a hack - there is no guarantee that the traceback occurs after
#         the exception!
        for callback in self.__callbacks[Events.Exception]:
            callback()

    def setFrequencies(self, freqs):
        '''
        Sends the command to set the specified frequencies
        :param freqs: Frequencies to set
        :type freqs: list
        '''
        assert(isinstance(freqs, list))
        for freq in freqs:
            assert(isinstance(freq, int))
        # TODO: Validate frequencies here?
        self.__rx.sendCommandPacket(
            rctComms.COMMANDS.SET_FREQUENCY, {'frequencies': freqs})
        self.__log.info("Set setF command")
