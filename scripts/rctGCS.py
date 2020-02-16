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
# 02/15/20    NH    Initial commit
#
###############################################################################

import tkinter as tk
import socket
import select
import json
import datetime as dt
import threading
import logging
from enum import Enum
from tkinter import ttk
from tkinter import messagebox as tkm
import sys
from builtins import list


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
        assert(freqs, list)
        for freq in freqs:
            assert(isinstance(freq, int))
        # TODO: finish


class MAVReceiver:
    '''
    Radio Collar Tracker UDP Interface
    '''
    __BUFFER_LEN = 1024

    def __init__(self, port: int):
        '''
        Initializes the UDP interface on the specified port.  Also specifies a
        filename to use as a logfile, which defaults to no log.

        :param port: Port number
        :type port: Integer
        '''
        assert(isinstance(port, (int)))
        self.__log = logging.getLogger('rctGCS.MAVReceiver')
        self.sock = None
        self.__portNo = port

        self.__receiverThread = None
        self.__log.info('RTC MAVReceiver created')
        self.__run = False
        self.__mavIP = None
        self.__lastHeartbeat = None
        self.__packetMap = {
            'heartbeat': [self.__processHeartbeat],
            '_nheartbeat': [],
            'exception': [],
        }

    def waitForHeartbeat(self, guiTick=None, timeout: int=30):
        '''
        Waits to receive a heartbeat packet.  Returns a tuple containing the
        MAV's IP address and port number as a single tuple, and the contents of
        the received heartbeat packet. 
        :param guiTick:
        :type guiTick:
        :param timeout: Seconds to wait before timing out
        :type timeout: Integer
        '''
        assert(isinstance(timeout, (int)))
        for i in range(timeout):
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                data, addr = self.sock.recvfrom(1024)
                packet = json.loads(data.decode('utf-8'))
                if 'heartbeat' in packet:
                    self.__log.info("Received heartbeat %s" % (packet))
                    self.__lastHeartbeat = dt.datetime.now()
                    return addr, packet
            if guiTick is not None:
                guiTick()
        self.__log.error("Failed to receive any heartbeats")
        return (None, None)

    def __receiverLoop(self):
        '''
        Receiver thread
        '''
        self.__log.info('RCT MAVReceiver rxThread started')
        while self.__run:
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                data, addr = self.sock.recvfrom(self.__BUFFER_LEN)
                self.__log.info("Received: %s" % data.decode())
                packet = json.loads(data.decode())
                for key in self.__packetMap.keys():
                    if key in packet:
                        for callback in self.__packetMap[key]:
                            callback(packet[key])
            if (dt.datetime.now() - self.__lastHeartbeat).total_seconds() > 30:
                self.__log.warn("No heartbeats!")
                for callback in self.__packetMap['_nheartbeat']:
                    callback(None)

    def start(self, gui=False):
        '''
        Starts the receiver.
        '''
        self.__log.info("RCT MAVReceiver starting...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.__portNo))
        self.__mavIP, packet = self.waitForHeartbeat(guiTick=gui)
        if self.__mavIP is None:
            raise RuntimeError("Failed to receive heartbeats")
        for key in self.__packetMap.keys():
            if key in packet:
                for callback in self.__packetMap[key]:
                    callback(packet[key])
        self.__run = True
        self.__receiverThread = threading.Thread(target=self.__receiverLoop)
        self.__receiverThread.start()
        self.__log.info('RCT MAVReceiver started')

    def stop(self):
        '''
        Stops the receiver.
        '''
        self.__log.info("__run set to False")
        self.__run = False
        if self.__receiverThread is not None:
            self.__receiverThread.join(timeout=1)
        self.__log.info('RCT MAVReceiver stopped')
        self.sock.close()

    def __processHeartbeat(self, packet):
        '''
        Internal callback to handle recognizing loss of heartbeat
        :param packet:
        :type packet:
        '''
        self.__lastHeartbeat = dt.datetime.now()

    def registerRxCallback(self, packetKey, callback):
        '''
        Registers a callback for the particular packet keyword
        :param packetKey: Keyword to recognize
        :type packetKey: String
        :param callback: Callback function
        :type callback: function pointer
        '''
        if packetKey in self.__packetMap:
            self.__packetMap[packetKey].append(callback)
        else:
            self.__packetMap[packetKey] = [callback]

    def sendMessage(self, packet: dict):
        '''
        Sends the specified dictionary as a packet
        :param packet: Packet to send
        :type packet: dictionary
        '''
        assert(isinstance(packet, dict))
        msg = json.dumps(packet)
        self.__log.info("Send: %s" % (msg))
        self.sock.sendto(msg.encode('utf-8'), self.__mavIP)


class GCS(tk.Tk):
    '''
    Ground Control Station GUI
    '''

    def __init__(self):
        '''
        Creates the GCS Application Object
        '''
        super().__init__()
        self.__log = logging.getLogger('rctGCS.GCS')
        self.__mavModel = MAVModel()
        self.__buttons = []
        self.innerFreqFrame = None
        self.freqElements = []
        self.__createWidgets()
        for button in self.__buttons:
            button.config(state='disabled')
        self.__mavModel.registerCallback(
            self.__mavModel.CALLBACK_EVENTS.Heartbeat, self.__updateStatus)
        self.__mavModel.registerCallback(
            self.__mavModel.CALLBACK_EVENTS.Exception, self.__handleRemoteException)
        self.__mavModel.registerCallback(
            self.__mavModel.CALLBACK_EVENTS.GetFreqs, self.__setFreqsFromRemote)

    def start(self):
        '''
        Start thread for the GCSP Application object.  This is responsible for
        initializing the comm channel.
        '''
        self.progressBar['maximum'] = 30
        try:
            self.__mavModel.start(self.progressBar.step)
        except RuntimeError:
            self.__noHeartbeat()

    def __setFreqsFromRemote(self):
        '''
        Callback to update the GUI with frequencies from the payload
        '''
        self.__log.info("Setting frequencies")
        freqs = self.__mavModel.frequencies
        if self.innerFreqFrame is not None:
            self.freqElements = []
            self.innerFreqFrame.destroy()
        self.innerFreqFrame = tk.Frame(self.freqFrame)

        for freq in freqs:
            self.freqElements.append(tk.Entry(self.innerFreqFrame))
            self.freqElements[-1].insert(0, freq)
            self.freqElements[-1].pack()
        self.__log.info("Updating GUI")
        self.innerFreqFrame.pack()
        self.update()

    def mainloop(self, n=0):
        '''
        Main Application Loop
        :param n:
        :type n:
        '''
        self.__startThread = threading.Thread(target=self.start)
        self.__startThread.start()
        tk.Tk.mainloop(self, n=n)

    def __startCommand(self):
        '''
        Internal callback to send the start command
        '''

    def __stopCommand(self):
        '''
        Internal callback to send the stop command
        '''

    def __getFreqs(self):
        '''
        Internal callback to retrieve the frequencies from the remote
        '''
        self.__mavModel.getFreqsFromRemote()

    def __addFreq(self):
        '''
        Internal callback to add a new frequency entry
        '''
        self.freqElements.append(tk.Entry(self.innerFreqFrame))
        self.freqElements[-1].pack()
        self.innerFreqFrame.update()
        self.__log.info("Added frequency entry")

    def __removeFreq(self):
        '''
        Internal callback to remove the lowest frequency entry
        '''
        self.freqElements[-1].destroy()
        self.freqElements.remove(self.freqElements[-1])
        self.innerFreqFrame.update()
        self.__log.info("Removed last frequency entry")

    def __sendFreq(self):
        '''
        Internal callback to send the current set of frequencies
        '''

    def __configureOpts(self):
        '''
        Internal callback to open the option configuration window
        '''

    def __upgradeSoftware(self):
        '''
        Internal callback to start the firmware upgrade process
        '''

    def __noHeartbeat(self):
        '''
        Internal callback for the no heartbeat state
        '''
        for button in self.__buttons:
            button.config(state='disabled')
        tkm.showerror(
            title="RCT GCS", message="No Heartbeats Received")

    def __handleRemoteException(self):
        '''
        Internal callback for an exception message
        '''
        tkm.showerror(title='RCT GCS', message='An exception has occured!\n%s\n%s' % (
            self.__mavModel.lastException[0], self.__mavModel.lastException[1]))

    def __updateStatus(self):
        '''
        Internal callback for status variable update
        '''
        for button in self.__buttons:
            button.config(state='normal')
        self.progressBar['value'] = 0
        sdrStatus = self.__mavModel.sdrStatus
        dirStatus = self.__mavModel.dirStatus
        gpsStatus = self.__mavModel.gpsStatus
        sysStatus = self.__mavModel.sysStatus
        swStatus = self.__mavModel.swStatus

        sdrMap = {
            self.__mavModel.SDR_INIT_STATES.find_devices: ('SDR: Searching for devices', 'yellow'),
            self.__mavModel.SDR_INIT_STATES.wait_recycle: ('SDR: Recycling!', 'yellow'),
            self.__mavModel.SDR_INIT_STATES.usrp_probe: ('SDR: Initializing SDR', 'yellow'),
            self.__mavModel.SDR_INIT_STATES.rdy: ('SDR: Ready', 'green'),
            self.__mavModel.SDR_INIT_STATES.fail: ('SDR: Failed!', 'red')
        }

        try:
            self.sdrStatusLabel.config(
                text=sdrMap[sdrStatus][0], bg=sdrMap[sdrStatus][1])
        except KeyError:
            self.sdrStatusLabel.config(
                text='SDR: NULL', bg='red')

        dirMap = {
            self.__mavModel.OUTPUT_DIR_STATES.get_output_dir: ('DIR: Searching', 'yellow'),
            self.__mavModel.OUTPUT_DIR_STATES.check_output_dir: ('DIR: Checking for mount', 'yellow'),
            self.__mavModel.OUTPUT_DIR_STATES.check_space: ('DIR: Checking for space', 'yellow'),
            self.__mavModel.OUTPUT_DIR_STATES.wait_recycle: ('DIR: Recycling!', 'yellow'),
            self.__mavModel.OUTPUT_DIR_STATES.rdy: ('DIR: Ready', 'green'),
            self.__mavModel.OUTPUT_DIR_STATES.fail: ('DIR: Failed!', 'red'),
        }

        try:
            self.dirStatusLabel.config(
                text=dirMap[dirStatus][0], bg=dirMap[dirStatus][1])
        except KeyError:
            self.dirStatusLabel.config(text='DIR: NULL', bg='red')

        gpsMap = {
            self.__mavModel.GPS_STATES.get_tty: {'text': 'GPS: Getting TTY Device', 'bg': 'yellow'},
            self.__mavModel.GPS_STATES.get_msg: {'text': 'GPS: Waiting for message', 'bg': 'yellow'},
            self.__mavModel.GPS_STATES.wait_recycle: {'text': 'GPS: Recycling', 'bg': 'yellow'},
            self.__mavModel.GPS_STATES.rdy: {'text': 'GPS: Ready', 'bg': 'green'},
            self.__mavModel.GPS_STATES.fail: {'text': 'GPS: Failed!', 'bg': 'red'}
        }

        try:
            self.gpsStatusLabel.config(**gpsMap[gpsStatus])
        except KeyError:
            self.gpsStatusLabel.config(text='GPS: NULL', bg='red')

        sysMap = {
            self.__mavModel.RCT_STATES.init: {'text': 'SYS: Initializing', 'bg': 'yellow'},
            self.__mavModel.RCT_STATES.wait_init: {'text': 'SYS: Initializing', 'bg': 'yellow'},
            self.__mavModel.RCT_STATES.wait_start: {'text': 'SYS: Ready for start', 'bg': 'green'},
            self.__mavModel.RCT_STATES.start: {'text': 'SYS: Starting', 'bg': 'blue'},
            self.__mavModel.RCT_STATES.wait_end: {'text': 'SYS: Running', 'bg': 'blue'},
            self.__mavModel.RCT_STATES.finish: {'text': 'SYS: Stopping', 'bg': 'blue'},
            self.__mavModel.RCT_STATES.fail: {'text': 'SYS: Failed!', 'bg': 'red'},
        }

        try:
            self.sysStatusLabel.config(**sysMap[sysStatus])
        except KeyError:
            self.sysStatusLabel.config(text='SYS: NULL', bg='red')

        if swStatus == 0:
            self.swStatusLabel.config(text='SW: OFF', bg='yellow')
        elif swStatus == 1:
            self.swStatusLabel.config(text='SW: ON', bg='green')
        else:
            self.swStatusLabel.config(text='SW: NULL', bg='red')

    def __windowClose(self):
        '''
        Internal callback for window close
        '''
        self.__startThread.join(timeout=1)
        self.__mavModel.stop()
        self.destroy()
        self.quit()

    def __createWidgets(self):
        '''
        Internal helper to make GUI widgets
        '''
        self.title('RCT GCS')
        self.grid_columnconfigure(0, weight=1)
        self.startButton = tk.Button(
            self, text='Start', command=self.__startCommand)
        self.startButton.grid(row=0, column=0, sticky='we')
        self.__buttons.append(self.startButton)

        self.stopButton = tk.Button(
            self, text='Stop', command=self.__stopCommand)
        self.stopButton.grid(row=1, column=0, sticky='we')
        self.__buttons.append(self.stopButton)

        self.freqFrame = tk.LabelFrame(
            self, text='Frequencies', padx=5, pady=5)
        self.innerFreqFrame = tk.Frame(self.freqFrame)
        self.innerFreqFrame.pack()
        self.freqFrame.grid(row=2, column=0, sticky='we')

        self.getFrequencyButton = tk.Button(
            self, text='Get Frequencies', command=self.__getFreqs)
        self.getFrequencyButton.grid(row=3, column=0, sticky='we')
        self.__buttons.append(self.getFrequencyButton)

        self.addFreqButton = tk.Button(
            self, text='Add Frequency', command=self.__addFreq)
        self.addFreqButton.grid(row=4, column=0, sticky='we')
        self.__buttons.append(self.addFreqButton)

        self.removeFreqButton = tk.Button(
            self, text='Remove Frequency', command=self.__removeFreq)
        self.removeFreqButton.grid(row=5, column=0, sticky='we')
        self.__buttons.append(self.removeFreqButton)

        self.commitFreqButton = tk.Button(
            self, text="Upload Frequencies", command=self.__sendFreq)
        self.commitFreqButton.grid(row=6, column=0, sticky='we')
        self.__buttons.append(self.commitFreqButton)

        self.configureButton = tk.Button(
            self, text="Configure", command=self.__configureOpts)
        self.configureButton.grid(row=7, column=0, sticky='we')
        self.__buttons.append(self.configureButton)

        self.upgradeButton = tk.Button(
            self, text="Upgrade Software", command=self.__upgradeSoftware)
        self.upgradeButton.grid(row=8, column=0, sticky='we')
        self.__buttons.append(self.upgradeButton)

        self.statusFrame = tk.LabelFrame(
            self, text="Payload Heartbeat", padx=5, pady=5)
        self.statusFrame.grid(row=9, column=0, sticky='we')

        self.sdrStatusLabel = tk.Label(self.statusFrame, text="SDR: NULL")
        self.sdrStatusLabel.grid(row=1, column=1)

        self.dirStatusLabel = tk.Label(self.statusFrame, text="DIR: NULL")
        self.dirStatusLabel.grid(row=2, column=1)

        self.gpsStatusLabel = tk.Label(self.statusFrame, text="GPS: NULL")
        self.gpsStatusLabel.grid(row=3, column=1)

        self.sysStatusLabel = tk.Label(self.statusFrame, text="SYS: NULL")
        self.sysStatusLabel.grid(row=4, column=1)

        self.swStatusLabel = tk.Label(self.statusFrame, text="SW: NULL")
        self.swStatusLabel.grid(row=5, column=1)

        self.protocol("WM_DELETE_WINDOW", self.__windowClose)
        self.progressBar = ttk.Progressbar(
            self, orient='horizontal', mode='determinate')
        self.progressBar.grid(row=10, column=0, sticky='we')


if __name__ == '__main__':
    logName = dt.datetime.now().strftime('%Y.%m.%d.%H.%M.%S.log')
    logName = 'log.log'
    logger = logging.getLogger()
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d: %(levelname)s:%(name)s: %(message)s', datefmt='%Y-%M-%d %H:%m:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ch = logging.FileHandler(logName)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    app = GCS()
    app.mainloop()
    app.quit()
