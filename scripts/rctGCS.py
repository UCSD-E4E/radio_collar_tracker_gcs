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
# 05/17/20  AG  Finished implementing start/stop recording button
# 05/17/20  AG  Added setting target frequencies and system connection text updates.
# 05/13/20  AG  Added ability to set and receive expert debug options
# 05/09/20  ML  Added ability to add/clear target frequencies
# 05/05/20  AG  Tied options entries to string vars
# 05/03/20  ML  Added Expert Settings popup, Added the ability to load TIFF img
# 05/03/20  AG  Added TCP connection and update options functionalities
# 04/26/20  NH  Updated API, switched from UDP to TCP
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
from tkinter import *
import rctTransport
import rctComms
import rctCore
from tkinter.filedialog import askopenfilename
import os
from PIL import Image, ImageTk
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.backend_bases import key_press_handler
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import rasterio as rio
from rasterio.plot import show

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
        self.__rctPort = rctTransport.RCTTCPClient(addr='127.0.0.1', port=9000)
        self.__mavReceiver = rctComms.MAVReceiver(self.__rctPort)
        self.__mavModel = rctCore.MAVModel(self.__mavReceiver)
        self.__buttons = []
        self.__systemConnectionTab = None
        self.__missionStatusText = StringVar()
        self.__missionStatusText.set("Start Recording")
        self.innerFreqFrame = None
        self.freqElements = []
        self.targEntries = {}
        self.targNameEntry = StringVar()
        self.targFreqEntry = StringVar()
        self.cntrFreqEntry = StringVar()
        self.sampFreqEntry = StringVar()
        self.sdrGainEntry = StringVar()
        self.pingWidthEntry = StringVar()
        self.minWidthMultEntry = StringVar()
        self.maxWidthMultEntry = StringVar()
        self.minPingSNREntry = StringVar()
        self.GPSPortEntry = StringVar()
        self.GPSBaudEntry = StringVar()
        self.outputDirEntry = StringVar()
        self.GPSModeEntry = StringVar()
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
        '''
        self.progressBar['maximum'] = 30
        try:
            self.__mavModel.start(self.progressBar.step)
        except RuntimeError:
            self.__noHeartbeat()
        '''

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
        self.__mavModel.getFrequencies()

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

    def __startStopMission(self):
        #State machine for start recording -> stop recording
        if self.__missionStatusText.get() == 'Start Recording':
            self.__missionStatusText.set('Stop Recording')
            self.__mavModel.startMission()
        else:
            self.__missionStatusText.set('Start Recording')
            self.__mavModel.stopMission()

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

    def __handleConnectInput(self):
        '''
        Internal callback to open Connect Settings
        '''
        conWindow = tk.Toplevel(self)

        conWindow.title('Connect Settings')

        frm_conType = tk.Frame(master=conWindow, width=350, height=400, bg="light gray")
        frm_conType.pack(fill=tk.Y, side=tk.LEFT)

        lbl_conType = tk.Label(frm_conType, text='Connection Type:')
        lbl_conType.pack(fill=tk.X)

        btn_TCP = tk.Checkbutton(frm_conType, text='TCP')
        btn_TCP.pack(fill=tk.X)

        frm_port = tk.Frame(master=conWindow, width=500, height=400, bg="dark gray")
        frm_port.pack(fill=tk.BOTH, side=tk.RIGHT)

        lbl_port = tk.Label(frm_port, text='Port')
        lbl_port.pack(fill=tk.BOTH)

        entr_port = tk.Entry(frm_port)
        entr_port.pack(fill=tk.BOTH)

        port = 'No Port Entered'
        def submit():
            port = entr_port.get()
            print(port)
            port = int(port)
            if port != 9000:
                self.__rctPort = rctTransport.RCTTCPClient(addr='127.0.0.1', port=port)
                self.__mavReceiver = rctComms.MAVReceiver(self.__rctPort)
                self.__mavModel = rctCore.MAVModel(self.__mavReceiver)
            self.__mavModel.start()
            self.__systemConnectionTab.updateText("System: Connected")
            options = self.__mavModel.getOptions(5)
            print("Done with getOptions call")
            print("Here are the options: ")
            for option in options:
                print(option + ':' + str(options[option]))
            if 'center_freq' in options:
                self.cntrFreqEntry.set(str(options['center_freq']))
            if 'sampling_freq' in options:
                self.sampFreqEntry.set(str(options['sampling_freq']))
            if 'sdrGain' in options:
                self.sdrGainEntry.set(str(options['sdrGain']))
            conWindow.destroy()
            conWindow.update()

        btn_submit = tk.Button(frm_port, text='submit', command=submit)
        btn_submit.pack()

    def __advancedSettings(self):
        '''
        Internal callback to open Connect Settings
        '''
        settingsWindow = tk.Toplevel(self)

        settingsWindow.title('Connect Settings')
        frm_advSettings = tk.Frame(master=settingsWindow)
        frm_advSettings.pack(fill=tk.BOTH)

        # EXPERT SETTINGS
        lbl_pingWidth = tk.Label(frm_advSettings, text='Expected Ping Width(ms)')
        lbl_pingWidth.grid(row=0, column=0, sticky='new')

        lbl_minWidthMult = tk.Label(frm_advSettings, text='Min. Width Multiplier')
        lbl_minWidthMult.grid(row=1, column=0, sticky='new')

        lbl_maxWidthMult = tk.Label(frm_advSettings, text='Max. Width Multiplier')
        lbl_maxWidthMult.grid(row=2, column=0, sticky='new')

        lbl_minPingSNR = tk.Label(frm_advSettings, text='Min. Ping SNR(dB)')
        lbl_minPingSNR.grid(row=3, column=0, sticky='new')

        lbl_GPSPort = tk.Label(frm_advSettings, text='GPS Port')
        lbl_GPSPort.grid(row=4, column=0, sticky='new')

        lbl_GPSBaudRate = tk.Label(frm_advSettings, text='GPS Baud Rate')
        lbl_GPSBaudRate.grid(row=5, column=0, sticky='new')

        lbl_outputDir = tk.Label(frm_advSettings, text='Output Directory')
        lbl_outputDir.grid(row=6, column=0, sticky='new')

        lbl_GPSMode = tk.Label(frm_advSettings, text='GPS Mode')
        lbl_GPSMode.grid(row=7, column=0, sticky='new')

        entr_pingWidth = tk.Entry(frm_advSettings, textvariable=self.pingWidthEntry, width=8)
        entr_pingWidth.grid(row=0, column=1, sticky='new')

        entr_minWidthMult = tk.Entry(frm_advSettings, textvariable=self.minWidthMultEntry, width=8)
        entr_minWidthMult.grid(row=1, column=1, sticky='new')

        entr_maxWidthMult = tk.Entry(frm_advSettings, textvariable=self.maxWidthMultEntry, width=8)
        entr_maxWidthMult.grid(row=2, column=1, sticky='new')

        entr_minPingSNR = tk.Entry(frm_advSettings, textvariable=self.minPingSNREntry, width=8)
        entr_minPingSNR.grid(row=3, column=1, sticky='new')

        entr_GPSPort = tk.Entry(frm_advSettings, textvariable=self.GPSPortEntry, width=8)
        entr_GPSPort.grid(row=4, column=1, sticky='new')

        entr_GPSBaudRate = tk.Entry(frm_advSettings, textvariable=self.GPSBaudEntry, width=8)
        entr_GPSBaudRate.grid(row=5, column=1, sticky='new')

        entr_outputDir = tk.Entry(frm_advSettings, textvariable=self.outputDirEntry, width=8)
        entr_outputDir.grid(row=6, column=1, sticky='new')

        entr_GPSMode = tk.Entry(frm_advSettings, textvariable=self.GPSModeEntry, width=8)
        entr_GPSMode.grid(row=7, column=1, sticky='new')

        def submit():
            pingWidth = self.pingWidthEntry.get()
            minWidthMult = self.minWidthMultEntry.get()
            maxWidthMult = self.maxWidthMultEntry.get()
            minPingSNR = self.minPingSNREntry.get()
            GPSPort = self.GPSPortEntry.get()
            GPSBaud = self.GPSBaudEntry.get()
            outputDir = self.outputDirEntry.get()
            GPSMode = self.GPSModeEntry.get()
            optionsFlag = False #set to true if setOptions is necessary

            setOptionsDict = {}
            if pingWidth != '':
                optionsFlag = True
                setOptionsDict['ping_width_ms'] = int(pingWidth)
            if minWidthMult != '':
                optionsFlag = True
                setOptionsDict['ping_min_len_mult'] = float(minWidthMult)
            if maxWidthMult != '':
                optionsFlag = True
                setOptionsDict['ping_max_len_mult'] = float(maxWidthMult)
            if minPingSNR != '':
                optionsFlag = True
                setOptionsDict['ping_min_snr'] = float(minPingSNR)
            if GPSPort != '':
                optionsFlag = True
                setOptionsDict['gps_target'] = GPSPort
            if outputDir != '':
                optionsFlag = True
                setOptionsDict['output_dir'] = outputDir
            if GPSMode != '':
                optionsFlag = True
                setOptionsDict['gps_mode'] = bool(GPSMode)
            if optionsFlag:
                self.__mavModel.setOptions(setOptionsDict)

            options = self.__mavModel.getOptions(5)

            # print statements for debugging purposes
            print("Done with getOptions call")
            print("Here are the options: ")
            for option in options:
                print(option + ':' + str(options[option]))
        
            if 'ping_width_ms' in options:
                self.pingWidthEntry.set(str(options['ping_width_ms']))
            if 'ping_min_len_mult' in options:
                self.minWidthMultEntry.set(str(options['ping_min_len_mult']))
            if 'ping_max_len_mult' in options:
                self.maxWidthMultEntry.set(str(options['ping_max_len_mult']))
            if 'ping_min_snr' in options:
                self.minPingSNREntry.set(str(options['ping_min_snr']))
            if 'gps_target' in options:
                self.GPSPortEntry.set(str(options['gps_target']))
            if 'output_dir' in options:
                self.outputDirEntry.set(str(options['output_dir']))
            if 'gps_mode' in options:
                self.GPSModeEntry.set(str(options['gps_mode']))

            settingsWindow.destroy()
            settingsWindow.update()

        btn_submit = tk.Button(settingsWindow, text='submit', command=submit)
        btn_submit.pack()

    def __createWidgets(self):
        '''
        Internal helper to make GUI widgets
        '''
        self.title('RCT GCS')

        frm_sideControl = tk.Frame(master=self, width=SBWidth, height=300, bg="dark gray")
        frm_sideControl.pack(anchor=tk.NW, side=tk.RIGHT)
        frm_sideControl.grid_columnconfigure(0, weight=1)
        frm_sideControl.grid_rowconfigure(0, weight=1)

        # SYSTEM TAB
        self.__systemConnectionTab = CollapseFrame(frm_sideControl, 'System: No Connection')
        self.__systemConnectionTab.grid(row=0, column=0, sticky='new')

        btn_connect = Button(self.__systemConnectionTab.frame, relief=tk.FLAT, width=SBWidth, text ="Connect", command=self.__handleConnectInput)
        btn_connect.grid(column=0, row=0, sticky='new')

        # COMPONENTS TAB
        frm_components = CollapseFrame(frm_sideControl, 'Components')
        frm_components.grid(column=0, row=1, sticky='new')

        lbl_componentNotif = tk.Label(frm_components.frame, width=SBWidth, text='Vehicle not connected')
        lbl_componentNotif.grid(column=0, row=0, sticky='new')

        # DATA DISPLAY TOOLS
        frm_mapGrid = tk.Frame(master=self)
        frm_mapGrid.pack(fill=tk.BOTH, side=tk.LEFT)
        frm_mapGrid.grid_columnconfigure(0, weight=1)
        frm_mapGrid.grid_rowconfigure(0, weight=1)
        frm_mapSpacer = tk.Frame(master=frm_mapGrid, bg='gray', height=400, width=450)
        frm_mapSpacer.grid(column=1,row=1)
        dirName = os.path.dirname(__file__)
        path=os.path.join(dirName, '../../map.jpg')
        '''
        load = Image.open(path)
        render = ImageTk.PhotoImage(load)
        img = Label(frm_mapSpacer, image=render)
        img.image = render
        img.pack(fill=tk.BOTH, expand=1)
        '''

        frm_displayTools = CollapseFrame(frm_sideControl, 'Data Display Tools')
        frm_displayTools.grid(column=0, row=2, sticky='n')

        def __selectMapFile():
            img.destroy()
            filename = askopenfilename()
            print(filename)
            fig = Figure(figsize=(5, 4), dpi=100)

            canvas1 = FigureCanvasTkAgg(fig, master=frm_mapSpacer)
            canvas1.draw()
            canvas1.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1, padx=10, pady=5)

            canvas1._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=1, padx=10, pady=5)

            ax = fig.add_subplot(111)

            with rio.open(filename) as src_plot:
                show(src_plot, ax=ax, cmap='gist_gray')
                plt.close()
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.spines["left"].set_visible(False)
                ax.spines["bottom"].set_visible(False)
                canvas1.draw()

        btn_loadMap = Button(frm_displayTools.frame, command=__selectMapFile, relief=tk.FLAT, width=SBWidth, text ="Load Map")
        btn_loadMap.grid(column=0, row=0, sticky='new')

        btn_export = Button(frm_displayTools.frame, relief=tk.FLAT, width=SBWidth, text ="Export")
        btn_export.grid(column=0, row=2, sticky='new')

        # MAP OPTIONS
        frm_mapOptions = tk.Frame(master=frm_mapGrid, width=SBWidth)
        frm_mapOptions.grid(column=0, row=0)

        lbl_mapOptions = tk.Label(frm_mapOptions, bg='gray', width=SBWidth, text='Map Options')
        lbl_mapOptions.grid(column=0, row=0, sticky='ew')

        btn_setSearchArea = tk.Button(frm_mapOptions,  bg='light gray', width=SBWidth,
                relief=tk.FLAT, text='Set Search Area')
        btn_setSearchArea.grid(column=0, row=1, sticky='ew')

        btn_cacheMap = tk.Button(frm_mapOptions, width=SBWidth,  bg='light gray',
                relief=tk.FLAT, text='Cache Map')
        btn_cacheMap.grid(column=0, row=2)

        # MAP LEGEND
        frm_mapLegend = tk.Frame(master=frm_mapGrid, width=SBWidth)
        frm_mapLegend.grid(column=0, row=2)

        lbl_legend = tk.Label(frm_mapLegend, width=SBWidth,  bg='gray', text='Map Legend')
        lbl_legend.grid(column=0, row=0, sticky='ew')

        lbl_legend = tk.Label(frm_mapLegend, width=SBWidth,  bg='light gray', text='Vehicle')
        lbl_legend.grid(column=0, row=1, sticky='ew')

        lbl_legend = tk.Label(frm_mapLegend, width=SBWidth,  bg='light gray', text='Target')
        lbl_legend.grid(column=0, row=2, sticky='ew')

        # SYSTEM SETTINGS
        frm_sysSettings = CollapseFrame(frm_sideControl, 'System Settings')
        frm_sysSettings.grid(column=0, row=3, sticky='new')

        frm_targHolder = tk.Frame(master=frm_sysSettings.frame, width=SBWidth-2)
        frm_targHolder.grid(row=4, column=0, columnspan=2, sticky='new')

        def addTarget():
            addTargetWindow = tk.Toplevel(self)

            addTargetWindow.title('Add Target')
            frm_targetSettings = tk.Frame(master=addTargetWindow)
            frm_targetSettings.pack(fill=tk.BOTH)

            lbl_targetName = tk.Label(frm_targetSettings, text='Target Name:')
            lbl_targetName.grid(row=0, column=0, sticky='new')

            entr_targetName = tk.Entry(frm_targetSettings, textvariable=self.targNameEntry, width = SBWidth)
            entr_targetName.grid(row=0, column=1, sticky='new')

            lbl_targetFreq = tk.Label(frm_targetSettings, text='Target Frequency:')
            lbl_targetFreq.grid(row=1, column=0, sticky='new')

            entr_targetFreq = tk.Entry(frm_targetSettings, textvariable=self.targFreqEntry, width = SBWidth)
            entr_targetFreq.grid(row=1, column=1, sticky='new')

            def submit():
                name = self.targNameEntry.get()
                freq = self.targFreqEntry.get()
                lbl_newTarget = tk.Label(frm_targHolder, text=name, width=17)
                lbl_newTarget.grid(row=len(self.targEntries), column=0)
                newTargFreqEntry = StringVar()
                newTargFreqEntry.set(freq)
                entr_newTarget = tk.Entry(frm_targHolder, textvariable=newTargFreqEntry, width=8)
                entr_newTarget.grid(row=len(self.targEntries), column=1)

                self.targEntries[name] = newTargFreqEntry
                frm_targHolder.grid(row=4, column=0, columnspan=2, sticky='new')
                addTargetWindow.destroy()
                addTargetWindow.update()

            btn_submit = tk.Button(addTargetWindow, text='submit', command=submit)
            btn_submit.pack()

        btn_addTarget = tk.Button(frm_sysSettings.frame, relief=tk.FLAT, text='Add Target',
                command=addTarget)
        btn_addTarget.grid(row=0, columnspan=2, sticky='new')

        lbl_cntrFreq = tk.Label(frm_sysSettings.frame, text='Center Frequency')
        lbl_cntrFreq.grid(row=1, column=0, sticky='new')

        lbl_sampFreq = tk.Label(frm_sysSettings.frame, text='Sampling Frequency')
        lbl_sampFreq.grid(row=2, column=0, sticky='new')

        lbl_sdrGain = tk.Label(frm_sysSettings.frame, text='SDR Gain')
        lbl_sdrGain.grid(row=3, column=0, sticky='new')

        entr_cntrFreq = tk.Entry(frm_sysSettings.frame, textvariable=self.cntrFreqEntry, width=8)
        entr_cntrFreq.grid(row=1, column=1, sticky='new')

        entr_sampFreq = tk.Entry(frm_sysSettings.frame, textvariable=self.sampFreqEntry, width=8)
        entr_sampFreq.grid(row=2, column=1, sticky='new')

        entr_sdrGain = tk.Entry(frm_sysSettings.frame, textvariable=self.sdrGainEntry, width=8)
        entr_sdrGain.grid(row=3, column=1, sticky='new')

        def update():
            cntrFreq = self.cntrFreqEntry.get()
            sampFreq = self.sampFreqEntry.get()
            optionsFlag = False #set to true if setOptions is necessary

            setOptionsDict = {}
            setOptionsDict['frequencies'] = []
            for targetName in self.targEntries:
                targetFreq = self.targEntries[targetName]
                if(targetFreq.get() != ''):
                    optionsFlag = True
                    setOptionsDict['frequencies'].append(int(targetFreq.get()))
            if cntrFreq != '':
                optionsFlag = True
                setOptionsDict['center_freq'] = int(cntrFreq)
                lastCntrFreq = self.__mavModel.options['center_freq']
                if int(cntrFreq) != lastCntrFreq:
                    setOptionsDict['frequencies'] = []
                    clearTargs()
            if sampFreq != '':
                optionsFlag = True
                setOptionsDict['sampling_freq'] = int(sampFreq)
                lastSampFreq = self.__mavModel.options['sampling_freq']
                if int(sampFreq) != lastSampFreq:
                    setOptionsDict['frequencies'] = []
                    clearTargs()
            if optionsFlag:
                self.__mavModel.setOptions(setOptionsDict)

            options = self.__mavModel.getOptions(5)
            print("Done with getOptions call")
            print("Here are the options: ")
            for option in options:
                print(option + ':' + str(options[option]))
            if 'center_freq' in options:
                self.cntrFreqEntry.set(str(options['center_freq']))
            if 'sampling_freq' in options:
                self.sampFreqEntry.set(str(options['sampling_freq']))
            if 'sdrGain' in options:
                self.sdrGainEntry.set(str(options['sdrGain']))

            '''
            for targetName, targetFreq in targEntries:
                if targetName in options:
                    targetFreq.delete(0,END)
                    targetFreq.insert(0, str(options[targetName]))
            '''

        def clearTargs():
            for i in frm_targHolder.grid_slaves():
                i.grid_forget()
            frm_targHolder.grid_forget()
            setOptionsDict = {}
            setOptionsDict['frequencies'] = []
            self.__mavModel.setOptions(setOptionsDict)
            self.targEntries = {}

        btn_clearTargs = tk.Button(frm_sysSettings.frame, text='Clear Targets', command=clearTargs)
        btn_clearTargs.grid(column=0, row=5, sticky='new')

        btn_submit = tk.Button(frm_sysSettings.frame, text='Update', command=update)
        btn_submit.grid(column=1, row=5, sticky='new')

        btn_advSettings = tk.Button(frm_sysSettings.frame,
                text='Expert & Debug Configuration', relief=tk.FLAT, command=self.__advancedSettings)
        btn_advSettings.grid(column=0, columnspan=2, row=6)

        # START PAYLOAD RECORDING
        btn_startRecord = tk.Button(frm_sideControl, width=SBWidth, textvariable=self.__missionStatusText, command=self.__startStopMission)
        btn_startRecord.grid(column=0, row=4, sticky='nsew')

SBWidth=25

class CollapseFrame(ttk.Frame):
    '''
    Helper class to deal with collapsible GUI components
    '''
    def __init__(self, parent, labelText="label"):

        ttk.Frame.__init__(self, parent)

        # These are the class variable
        # see a underscore in expanded_text and _collapsed_text
        # this means these are private to class
        self.parent = parent

        self.columnconfigure(0, weight = 1)

        # Tkinter variable storing integer value
        self._variable = tk.IntVar()

        self._button = ttk.Checkbutton(self, width=SBWidth, variable = self._variable,
                            command = self._activate, text=labelText, style ="TMenubutton")
        self._button.grid(row = 0, column = 0, sticky = "we")

        collapseStyle = ttk.Style()
        collapseStyle.configure("TFrame", background="dark gray")
        self.frame = ttk.Frame(self, style="TFrame")

        # This will call activate function of class
        self._activate()

    def _activate(self):
        if not self._variable.get():

            self.frame.grid_forget()

        elif self._variable.get():
            # increasing the frame area so new widgets
            # could reside in this container
            self.frame.grid(row = 1, column = 0, columnspan = 1)

    def toggle(self):
        """Switches the label frame to the opposite state."""
        self._variable.set(not self._variable.get())
        self._activate()

    def updateText(self, newText="label"):
        self._button.config(text=newText)

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
