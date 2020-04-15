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
# DATE        Name  Description
# -----------------------------------------------------------------------------
# 04/14/20    NH    Initial commit
#
###############################################################################

from enum import Enum
from builtins import list
from scripts.rctComms import MAVReceiver
import logging

class MAVModel:
    '''
    RCT Payload Model - This class should provide an object oriented view of the
    vehicle state
    '''
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

    class CALLBACK_EVENTS(Enum):
        '''
        Callback Events

        Hearbeat  - Callback when a heartbeat message is received
        Exception - Callback when an exception message is received
        GetFreqs  - Callback when the payload broadcasts a set of frequencies
        '''
        Heartbeat = 1,
        Exception = 2,
        GetFreqs = 3,
        
    class GPS_STATES(Enum):
        '''
        GPS States
        '''
        get_tty = 0
        get_msg = 1
        wait_recycle = 2
        rdy = 3
        fail = 4

    def __init__(self):
        '''
        Creates the MAVModel object.
        '''
        self.__log = logging.getLogger('rctGCS:MAVModel')
        self.__rx = MAVReceiver(9000)
        self.sdrStatus = 0
        self.dirStatus = 0
        self.gpsStatus = 0
        self.sysStatus = 0
        self.swStatus = 0
        self.frequencies = []
        self.__rx.registerRxCallback('heartbeat', self.__processHeartbeat)
        self.__rx.registerRxCallback('exception', self.__handleRemoteException)
        self.__rx.registerRxCallback('traceback', self.__handleRemoteTraceback)
        self.__rx.registerRxCallback('frequencies', self.__processFrequencies)
        self.__exceptions = []
        self.lastException = [None, None]
        self.__log.info("MAVModel Created")
        self.__callbacks = {
        }
        for event in self.CALLBACK_EVENTS:
            self.__callbacks[event] = []

    def start(self, guiTickCallback=None):
        '''
        Initializes the MAVModel object
        :param guiTickCallback: Callback to a function for progress bar
        :type guiTickCallback: Function with no parameters to be called for 
            progress
        '''
        self.__rx.start(guiTickCallback)
        self.__log.info("MVAModel started")

    def __processFrequencies(self, frequencies):
        '''
        Internal callback to handle frequency messages
        :param frequencies: Frequency message payload
        :type frequencies: List of integers
        '''
        self.__log.info("Received frequencies")
        self.frequencies = frequencies
        for callback in self.__callbacks[self.CALLBACK_EVENTS.GetFreqs]:
            callback()

    def __processHeartbeat(self, packet):
        '''
        Internal callback to handle heartbeat messages
        :param packet: Heartbeat packet payload
        :type packet:
        '''
        self.__log.info("Received heartbeat")
        statusString = packet['status']
        self.sdrStatus = self.SDR_INIT_STATES(int(statusString[0]))
        self.dirStatus = self.OUTPUT_DIR_STATES(int(statusString[1]))
        self.gpsStatus = self.GPS_STATES(int(statusString[2]))
        self.sysStatus = self.RCT_STATES(int(statusString[3]))
        self.swStatus = int(statusString[4])
        for callback in self.__callbacks[self.CALLBACK_EVENTS.Heartbeat]:
            callback()

    def stop(self):
        '''
        Stops the MAVModel and underlying resources
        '''
        self.__rx.stop()
        self.__log.info("MVAModel stopped")

    def registerCallback(self, event: CALLBACK_EVENTS, callback):
        '''
        Registers a callback for the specified event
        :param event: Event to trigger on
        :type event: CALLBACK_EVENTS
        :param callback: Callback to call
        :type callback:
        '''
        assert(isinstance(event, self.CALLBACK_EVENTS))
        self.__callbacks[event].append(callback)

    def startMission(self):
        '''
        Sends the start mission command
        '''
        commandPacket = {'cmd': {'id': 'gcs', 'action': 'start'}}
        self.__rx.sendMessage(commandPacket)
        self.__log.info("Sent start command")

    def getFreqsFromRemote(self):
        '''
        Sends the command to retrieve frequencies
        '''
        commandPacket = {'cmd': {'id': 'gcs', 'action': 'getF'}}
        self.__rx.sendMessage(commandPacket)
        self.__log.info("Sent getF command")

    def __handleRemoteException(self, exception):
        '''
        Internal callback to handle exception messages
        :param exception: Exception string
        :type exception:
        '''
        self.__log.exception("Remote Exception: %s" % exception)
        self.lastException[0] = exception

    def __handleRemoteTraceback(self, traceback):
        '''
        Internal callback to handle traceback messages
        :param traceback: Traceback string
        :type traceback:
        '''
        self.__log.exception("Remote Traceback: %s" % traceback)
        self.lastException[1] = traceback
#         This is a hack - there is no guarantee that the traceback occurs after
#         the exception!
        for callback in self.__callbacks[self.CALLBACK_EVENTS.Exception]:
            callback()

    def setFrequencies(self, freqs):
        '''
        Sends the command to set the specified frequencies
        :param freqs:
        :type freqs:
        '''
        assert(isinstance(freqs, list))
        for freq in freqs:
            assert(isinstance(freq, int))
        # TODO: finish

