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
# 04/20/20  NH  Updated API and imports
# 04/17/20  NH  Updated imports and MAVModel API
# 02/15/20  NH  Initial commit
#
###############################################################################

import tkinter as tk

import datetime as dt
import threading
import logging
from tkinter import ttk
from tkinter import messagebox as tkm
import sys
import rctTransport
import rctComms
import rctCore


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
        self.__rctPort = rctTransport.RCTUDPClient()
        self.__mavReceiver = rctComms.MAVReceiver(self.__rctPort)
        self.__mavModel = rctCore.MAVModel(self.__mavReceiver)
        self.__buttons = []
        self.innerFreqFrame = None
        self.freqElements = []
        self.__createWidgets()
        for button in self.__buttons:
            button.config(state='disabled')
        self.__mavModel.registerCallback(
            rctCore.Events.Heartbeat, self.__updateStatus)
        self.__mavModel.registerCallback(
            rctCore.Events.Exception, self.__handleRemoteException)
        self.__mavModel.registerCallback(
            rctCore.Events.GetFreqs, self.__setFreqsFromRemote)

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
        self.__mavModel.getFreqs()

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
            self.__mavModel.GPS_STATES.fail: {
                'text': 'GPS: Failed!', 'bg': 'red'}
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
