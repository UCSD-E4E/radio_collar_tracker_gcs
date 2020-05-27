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
# 05/25/20  NH  Fixed validate frequency call
# 05/24/20  ML  Implemented ability to load map, refactored map functions
# 05/24/20  AG  Added error messages during target frequency validation.
# 05/20/20  NH  Fixed window close action, added function to handle registering
#                 callbacks when connection established, removed unused
#                 callbacks, added advanced settings dialog, fixed logging
# 05/19/20  NH  Removed PIL, rasterio, refactored options, connectionDialog,
#                 AddTargetDialog, SystemSettingsControl, fixed exit behavior,
# 05/18/20  NH  Updated API for core
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
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.basemap import Basemap
import math
import urllib.request
import io
import georaster

class GCS(tk.Tk):
    '''
    Ground Control Station GUI
    '''

    SBWidth = 25

    defaultTimeout = 5

    def __init__(self):
        '''
        Creates the GCS Application Object
        '''
        super().__init__()
        self.__log = logging.getLogger('rctGCS.GCS')
        self._rctPort = None
        self._mavReceiver = None
        self._mavModel = None
        self._buttons = []
        self._systemConnectionTab = None
        self.__missionStatusText = StringVar()
        self.__missionStatusText.set("Start Recording")
        self.innerFreqFrame = None
        self.freqElements = []
        self.cntrFreqEntry = StringVar()
        self.sampFreqEntry = StringVar()
        self.sdrGainEntry = StringVar()
        self.missionDisplay = StringVar()
        self.targEntries = {}
        self.__createWidgets()
        for button in self._buttons:
            button.config(state='disabled')
        self.__mavModel.registerCallback(
            rctCore.Events.Heartbeat, self.__updateStatus)
        self.__mavModel.registerCallback(
            rctCore.Events.Exception, self.__handleRemoteException)
        self.__mavModel.registerCallback(
            rctCore.Events.GetFreqs, self.__setFreqsFromRemote)
        self.__mavModel.registerCallback(
            rctCore.Events.Heartbeat, self.__heartbeatCallback)
        self.protocol('WM_DELETE_WINDOW', self.__windowClose)

    def __registerModelCallbacks(self):
        #         self._mavModel.registerCallback(
        #             rctCore.Events.Heartbeat, self.__updateStatus)
        self._mavModel.registerCallback(
            rctCore.Events.Exception, self.__handleRemoteException)

    def mainloop(self, n=0):
        '''
        Main Application Loop
        :param n:
        :type n:
        '''
        tk.Tk.mainloop(self, n=n)

    def __heartbeatCallback(self):
        if (self.__mavModel.swStatus != 0):
            self.missionDisplay.set('Start Recording')

    def __startCommand(self):
        '''
        Internal callback to send the start command
        '''

    def __stopCommand(self):
        '''
        Internal callback to send the stop command
        '''

    def __noHeartbeat(self):
        '''
        Internal callback for the no heartbeat state
        '''
        for button in self._buttons:
            button.config(state='disabled')
        tkm.showerror(
            title="RCT GCS", message="No Heartbeats Received")

    def __handleRemoteException(self):
        '''
        Internal callback for an exception message
        '''
        tkm.showerror(title='RCT GCS', message='An exception has occured!\n%s\n%s' % (
            self._mavModel.lastException[0], self._mavModel.lastException[1]))

    def __startStopMission(self):
        # State machine for start recording -> stop recording
        if self.__missionStatusText.get() == 'Start Recording':
            self.__missionStatusText.set('Stop Recording')
            self._mavModel.startMission(timeout=self.defaultTimeout)
        else:
            self.__missionStatusText.set('Start Recording')
            self._mavModel.stopMission(timeout=self.defaultTimeout)

    def __updateStatus(self):
        '''
        Internal callback for status variable update
        '''
        for button in self._buttons:
            button.config(state='normal')
        self.progressBar['value'] = 0
        sdrStatus = self._mavModel.STS_sdrStatus
        dirStatus = self._mavModel.STS_dirStatus
        gpsStatus = self._mavModel.STS_gpsStatus
        sysStatus = self._mavModel.STS_sysStatus
        swStatus = self._mavModel.STS_swStatus

        sdrMap = {
            self._mavModel.SDR_INIT_STATES.find_devices: ('SDR: Searching for devices', 'yellow'),
            self._mavModel.SDR_INIT_STATES.wait_recycle: ('SDR: Recycling!', 'yellow'),
            self._mavModel.SDR_INIT_STATES.usrp_probe: ('SDR: Initializing SDR', 'yellow'),
            self._mavModel.SDR_INIT_STATES.rdy: ('SDR: Ready', 'green'),
            self._mavModel.SDR_INIT_STATES.fail: ('SDR: Failed!', 'red')
        }

        try:
            self.sdrStatusLabel.config(
                text=sdrMap[sdrStatus][0], bg=sdrMap[sdrStatus][1])
        except KeyError:
            self.sdrStatusLabel.config(
                text='SDR: NULL', bg='red')

        dirMap = {
            self._mavModel.OUTPUT_DIR_STATES.get_output_dir: ('DIR: Searching', 'yellow'),
            self._mavModel.OUTPUT_DIR_STATES.check_output_dir: ('DIR: Checking for mount', 'yellow'),
            self._mavModel.OUTPUT_DIR_STATES.check_space: ('DIR: Checking for space', 'yellow'),
            self._mavModel.OUTPUT_DIR_STATES.wait_recycle: ('DIR: Recycling!', 'yellow'),
            self._mavModel.OUTPUT_DIR_STATES.rdy: ('DIR: Ready', 'green'),
            self._mavModel.OUTPUT_DIR_STATES.fail: ('DIR: Failed!', 'red'),
        }

        try:
            self.dirStatusLabel.config(
                text=dirMap[dirStatus][0], bg=dirMap[dirStatus][1])
        except KeyError:
            self.dirStatusLabel.config(text='DIR: NULL', bg='red')

        gpsMap = {
            self._mavModel.GPS_STATES.get_tty: {'text': 'GPS: Getting TTY Device', 'bg': 'yellow'},
            self._mavModel.GPS_STATES.get_msg: {'text': 'GPS: Waiting for message', 'bg': 'yellow'},
            self._mavModel.GPS_STATES.wait_recycle: {'text': 'GPS: Recycling', 'bg': 'yellow'},
            self._mavModel.GPS_STATES.rdy: {'text': 'GPS: Ready', 'bg': 'green'},
            self._mavModel.GPS_STATES.fail: {
                'text': 'GPS: Failed!', 'bg': 'red'}
        }

        try:
            self.gpsStatusLabel.config(**gpsMap[gpsStatus])
        except KeyError:
            self.gpsStatusLabel.config(text='GPS: NULL', bg='red')

        sysMap = {
            self._mavModel.RCT_STATES.init: {'text': 'SYS: Initializing', 'bg': 'yellow'},
            self._mavModel.RCT_STATES.wait_init: {'text': 'SYS: Initializing', 'bg': 'yellow'},
            self._mavModel.RCT_STATES.wait_start: {'text': 'SYS: Ready for start', 'bg': 'green'},
            self._mavModel.RCT_STATES.start: {'text': 'SYS: Starting', 'bg': 'blue'},
            self._mavModel.RCT_STATES.wait_end: {'text': 'SYS: Running', 'bg': 'blue'},
            self._mavModel.RCT_STATES.finish: {'text': 'SYS: Stopping', 'bg': 'blue'},
            self._mavModel.RCT_STATES.fail: {'text': 'SYS: Failed!', 'bg': 'red'},
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
        if self._mavModel is not None:
            self._mavModel.stop()
        self.destroy()
        self.quit()

    def __handleConnectInput(self):
        '''
        Internal callback to open Connect Settings
        '''
        connectionDialog = ConnectionDialog(self)

        self._rctPort = connectionDialog.comms
        self._mavReceiver = connectionDialog.comms
        self._mavModel = connectionDialog.model
        if self._mavModel is None:
            return

        self._systemConnectionTab.updateText("System: Connected")
        self.__registerModelCallbacks()
        self.systemSettingsWidget.updateGUIOptionVars()

    def __advancedSettings(self):
        '''
        Internal callback to open Connect Settings
        '''
        settingsWindow = tk.Toplevel(self)

        settingsWindow.title('Connect Settings')
        frm_advSettings = tk.Frame(master=settingsWindow)
        frm_advSettings.pack(fill=tk.BOTH)

        # EXPERT SETTINGS
        lbl_pingWidth = tk.Label(
            frm_advSettings, text='Expected Ping Width(ms)')
        lbl_pingWidth.grid(row=0, column=0, sticky='new')

        lbl_minWidthMult = tk.Label(
            frm_advSettings, text='Min. Width Multiplier')
        lbl_minWidthMult.grid(row=1, column=0, sticky='new')

        lbl_maxWidthMult = tk.Label(
            frm_advSettings, text='Max. Width Multiplier')
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

        entr_pingWidth = tk.Entry(
            frm_advSettings, textvariable=self.optionVars['DSP_pingWidth'], width=8)
        entr_pingWidth.grid(row=0, column=1, sticky='new')

        entr_minWidthMult = tk.Entry(
            frm_advSettings, textvariable=self.optionVars['DSP_pingMin'], width=8)
        entr_minWidthMult.grid(row=1, column=1, sticky='new')

        entr_maxWidthMult = tk.Entry(
            frm_advSettings, textvariable=self.optionVars['DSP_pingMax'], width=8)
        entr_maxWidthMult.grid(row=2, column=1, sticky='new')

        entr_minPingSNR = tk.Entry(
            frm_advSettings, textvariable=self.optionVars['DSP_pingSNR'], width=8)
        entr_minPingSNR.grid(row=3, column=1, sticky='new')

        entr_GPSPort = tk.Entry(
            frm_advSettings, textvariable=self.optionVars['GPS_device'], width=8)
        entr_GPSPort.grid(row=4, column=1, sticky='new')

        entr_GPSBaudRate = tk.Entry(
            frm_advSettings, textvariable=self.optionVars['GPS_baud'], width=8)
        entr_GPSBaudRate.grid(row=5, column=1, sticky='new')

        entr_outputDir = tk.Entry(
            frm_advSettings, textvariable=self.optionVars['SYS_outputDir'], width=8)
        entr_outputDir.grid(row=6, column=1, sticky='new')

        entr_GPSMode = tk.Entry(
            frm_advSettings, textvariable=self.optionVars['GPS_mode'], width=8)
        entr_GPSMode.grid(row=7, column=1, sticky='new')

        def submit():
            pingWidth = self.optionVars['DSP_pingWidth'].get()
            minWidthMult = self.optionVars['DSP_pingMin'].get()
            maxWidthMult = self.optionVars['DSP_pingMax'].get()
            minPingSNR = self.optionVars['DSP_pingSNR'].get()
            GPSPort = self.optionVars['GPS_device'].get()
            GPSBaud = self.optionVars['GPS_baud'].get()
            outputDir = self.optionVars['SYS_outputDir'].get()
            GPSMode = self.optionVars['GPS_mode'].get()
            optionsFlag = False  # set to true if setOptions is necessary

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
                self._mavModel.setOptions(setOptionsDict)

            options = self._mavModel.getOptions(5)

            # print statements for debugging purposes
            print("Done with getOptions call")
            print("Here are the options: ")
            for option in options:
                print(option + ':' + str(options[option]))

            if 'ping_width_ms' in options:
                self.optionVars['DSP_pingWidth'].set(
                    str(options['ping_width_ms']))
            if 'ping_min_len_mult' in options:
                self.optionVars['DSP_pingMin'].set(
                    str(options['ping_min_len_mult']))
            if 'ping_max_len_mult' in options:
                self.optionVars['DSP_pingMax'].set(
                    str(options['ping_max_len_mult']))
            if 'ping_min_snr' in options:
                self.optionVars['DSP_pingSNR'].set(
                    str(options['ping_min_snr']))
            if 'gps_target' in options:
                self.optionVars['GPS_device'].set(str(options['gps_target']))
            if 'output_dir' in options:
                self.optionVars['SYS_outputDir'].set(
                    str(options['output_dir']))
            if 'gps_mode' in options:
                self.optionVars['GPS_mode'].set(str(options['gps_mode']))

            settingsWindow.destroy()
            settingsWindow.update()

        btn_submit = tk.Button(settingsWindow, text='submit', command=submit)
        btn_submit.pack()

    def __loadMapFile(self, frm_mapSpacer):
        filename = askopenfilename()
        print(filename)
        fig = Figure(figsize=(5, 4), dpi=100)


        '''
        canvas1 = FigureCanvasTkAgg(fig, master=frm_mapSpacer)
        canvas1.draw()
        canvas1.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1, padx=10, pady=5)

        canvas1._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=1, padx=10, pady=5)
        '''
        fig = plt.figure(figsize=(5,5))

        f = Figure(figsize=(4,4), dpi=100)

        
        my_image = georaster.SingleBandRaster(filename, load_data=False)
        
        minx, maxx, miny, maxy = my_image.extent
        
        a = fig.add_subplot(111)

        mapSpace = 1

        m = Basemap( projection='cyl', \
                    llcrnrlon=minx-mapSpace, \
                    llcrnrlat=miny-mapSpace, \
                    urcrnrlon=maxx+mapSpace, \
                    urcrnrlat=maxy+mapSpace, \
                    resolution='h', ax=a)

        m.drawcoastlines(color="gray")
        m.fillcontinents(color='beige')
        m.shadedrelief()

        canvas = FigureCanvasTkAgg(fig, master=frm_mapSpacer)
        canvas.draw()
        canvas.get_tk_widget().pack(side='top', fill='both', expand=0)

        toolbar = NavigationToolbar2Tk( canvas, frm_mapSpacer )
        toolbar.update()
        canvas._tkcanvas.pack(side='top', fill='both', expand=0)

        
        image = georaster.SingleBandRaster( filename, \
                                load_data=(minx, maxx, miny, maxy), \
                                latlon=True)
    
        plt.imshow(image.r, extent=(minx, maxx, miny, maxy), zorder=10, alpha=0.8)


    def __createWidgets(self):
        '''
        Internal helper to make GUI widgets
        '''
        self.title('RCT GCS')

        frm_sideControl = tk.Frame(
            master=self, width=self.SBWidth, height=300, bg="dark gray")
        frm_sideControl.pack(anchor=tk.NW, side=tk.RIGHT)
        frm_sideControl.grid_columnconfigure(0, weight=1)
        frm_sideControl.grid_rowconfigure(0, weight=1)

        # SYSTEM TAB
        self._systemConnectionTab = CollapseFrame(
            frm_sideControl, 'System: No Connection')
        self._systemConnectionTab.grid(row=0, column=0, sticky='new')
        Button(self._systemConnectionTab.frame, relief=tk.FLAT, width=self.SBWidth,
               text="Connect", command=self.__handleConnectInput).grid(column=0, row=0, sticky='new')

        # COMPONENTS TAB
        frm_components = CollapseFrame(frm_sideControl, 'Components')
        frm_components.grid(column=0, row=1, sticky='new')

        lbl_componentNotif = tk.Label(
            frm_components.frame, width=self.SBWidth, text='Vehicle not connected')
        lbl_componentNotif.grid(column=0, row=0, sticky='new')

        # DATA DISPLAY TOOLS
        frm_mapGrid = tk.Frame(master=self)
        frm_mapGrid.pack(fill=tk.BOTH, side=tk.LEFT)
        frm_mapGrid.grid_columnconfigure(0, weight=1)
        frm_mapGrid.grid_rowconfigure(0, weight=1)
        frm_mapSpacer = tk.Frame(master=frm_mapGrid, bg='gray', height=548, width=800)
        frm_mapSpacer.pack_propagate(0)
        frm_mapSpacer.grid(column=1,row=1) 

        frm_displayTools = CollapseFrame(frm_sideControl, 'Data Display Tools')
        frm_displayTools.grid(column=0, row=2, sticky='n')



        btn_loadMap = Button(frm_displayTools.frame, command=lambda: self.__loadMapFile(frm_mapSpacer), 
                relief=tk.FLAT, width=SBWidth, text ="Load Map")
        btn_loadMap.grid(column=0, row=0, sticky='new')


        btn_export = Button(frm_displayTools.frame,
                            relief=tk.FLAT, width=self.SBWidth, text="Export")
        btn_export.grid(column=0, row=2, sticky='new')

        # MAP OPTIONS
        frm_mapOptions = tk.Frame(master=frm_mapGrid, width=self.SBWidth)
        frm_mapOptions.grid(column=0, row=0)

        lbl_mapOptions = tk.Label(
            frm_mapOptions, bg='gray', width=self.SBWidth, text='Map Options')
        lbl_mapOptions.grid(column=0, row=0, sticky='ew')

        btn_setSearchArea = tk.Button(frm_mapOptions,  bg='light gray', width=self.SBWidth,
                                      relief=tk.FLAT, text='Set Search Area')
        btn_setSearchArea.grid(column=0, row=1, sticky='ew')

        btn_cacheMap = tk.Button(frm_mapOptions, width=self.SBWidth,  bg='light gray',
                                 relief=tk.FLAT, text='Cache Map')
        btn_cacheMap.grid(column=0, row=2)

        # MAP LEGEND
        frm_mapLegend = tk.Frame(master=frm_mapGrid, width=self.SBWidth)
        frm_mapLegend.grid(column=0, row=2)

        lbl_legend = tk.Label(frm_mapLegend, width=self.SBWidth,
                              bg='gray', text='Map Legend')
        lbl_legend.grid(column=0, row=0, sticky='ew')

        lbl_legend = tk.Label(frm_mapLegend, width=self.SBWidth,
                              bg='light gray', text='Vehicle')
        lbl_legend.grid(column=0, row=1, sticky='ew')

        lbl_legend = tk.Label(frm_mapLegend, width=self.SBWidth,
                              bg='light gray', text='Target')
        lbl_legend.grid(column=0, row=2, sticky='ew')

        # SYSTEM SETTINGS
        self.systemSettingsWidget = SystemSettingsControl(
            frm_sideControl, self)
        self.systemSettingsWidget.grid(column=0, row=3, sticky='new')

        # START PAYLOAD RECORDING
        btn_startRecord = tk.Button(frm_sideControl, width=self.SBWidth,
                                    textvariable=self.__missionStatusText, command=self.__startStopMission)
        btn_startRecord.grid(column=0, row=4, sticky='nsew')

class CollapseFrame(ttk.Frame):
    '''
    Helper class to deal with collapsible GUI components
    '''

    def __init__(self, parent, labelText, width=25):

        ttk.Frame.__init__(self, parent)

        # These are the class variable
        # see a underscore in expanded_text and _collapsed_text
        # this means these are private to class
        self.parent = parent

        self.columnconfigure(0, weight=1)

        # Tkinter variable storing integer value
        self._variable = tk.IntVar()

        self._button = ttk.Checkbutton(self, width=width, variable=self._variable,
                                       command=self._activate, text=labelText, style="TMenubutton")
        self._button.grid(row=0, column=0, sticky="we")

        collapseStyle = ttk.Style()
        collapseStyle.configure("TFrame", background="dark gray")
        self.frame = ttk.Frame(self, style="TFrame")

        self._width = width

        # This will call activate function of class
        self._activate()

    def _activate(self):
        if not self._variable.get():

            self.frame.grid_forget()

        elif self._variable.get():
            # increasing the frame area so new widgets
            # could reside in this container
            self.frame.grid(row=1, column=0, columnspan=1)

    def toggle(self):
        """Switches the label frame to the opposite state."""
        self._variable.set(not self._variable.get())
        self._activate()

    def updateText(self, newText="label"):
        self._button.config(text=newText)

class SystemSettingsControl(CollapseFrame):
    def __init__(self, parent, root: GCS):
        CollapseFrame.__init__(self, parent, labelText='System Settings')
        self.__parent = parent
        self.__root = root

        self.__innerFrame = None
        self.frm_targHolder = None
        self.targEntries = {}

        self.optionVars = {
            "TGT_frequencies": [],
            "SDR_centerFreq": tk.IntVar(),
            "SDR_samplingFreq": tk.IntVar(),
            "SDR_gain": tk.DoubleVar(),
            "DSP_pingWidth": tk.DoubleVar(),
            "DSP_pingSNR": tk.DoubleVar(),
            "DSP_pingMax": tk.DoubleVar(),
            "DSP_pingMin": tk.DoubleVar(),
            "GPS_mode": tk.IntVar(),
            "GPS_device": tk.StringVar(),
            "GPS_baud": tk.IntVar(),
            "SYS_outputDir": tk.StringVar(),
            "SYS_autostart": tk.BooleanVar(),
        }
        self.__createWidget()

    def update(self):
        CollapseFrame.update(self)
        self.__createWidget()

    def __createWidget(self):
        if self.__innerFrame:
            self.__innerFrame.destroy()
        self.__innerFrame = tk.Frame(self.frame)
        self.__innerFrame.grid(row=0, column=0, sticky='nesw')

        lbl_cntrFreq = tk.Label(self.__innerFrame, text='Center Frequency')
        lbl_cntrFreq.grid(row=1, column=0, sticky='new')

        lbl_sampFreq = tk.Label(self.__innerFrame,
                                text='Sampling Frequency')
        lbl_sampFreq.grid(row=2, column=0, sticky='new')

        lbl_sdrGain = tk.Label(self.__innerFrame, text='SDR Gain')
        lbl_sdrGain.grid(row=3, column=0, sticky='new')

        entr_cntrFreq = tk.Entry(
            self.__innerFrame, textvariable=self.optionVars['SDR_centerFreq'], width=8)
        entr_cntrFreq.grid(row=1, column=1, sticky='new')

        entr_sampFreq = tk.Entry(
            self.__innerFrame, textvariable=self.optionVars['SDR_samplingFreq'], width=8)
        entr_sampFreq.grid(row=2, column=1, sticky='new')

        entr_sdrGain = tk.Entry(self.__innerFrame,
                                textvariable=self.optionVars['SDR_gain'], width=8)
        entr_sdrGain.grid(row=3, column=1, sticky='new')

        self.frm_targHolder = tk.Frame(
            self.__innerFrame, width=self._width - 2)
        self.frm_targHolder.grid(row=4, column=0, columnspan=2, sticky='new')

        btn_addTarget = tk.Button(self.__innerFrame, relief=tk.FLAT, text='Add Target',
                                  command=self.addTarget)
        btn_addTarget.grid(row=0, columnspan=2, sticky='new')

        rowIdx = 0
        self.targEntries = {}
        if self.__root._mavModel is not None:
            for freq in self.__root._mavModel.getFrequencies(self.__root.defaultTimeout):
                freqLabel = tk.Label(self.frm_targHolder,
                                     text='Target %d' % (rowIdx + 1))
                freqLabel.grid(row=rowIdx, column=0, sticky='ew')
                freqVariable = tk.IntVar()
                freqVariable.set(freq)
                freqEntry = tk.Entry(self.frm_targHolder,
                                     textvariable=freqVariable, validate='focusout',
                                     validatecommand=lambda sv=freqVariable: self.validateFrequency(sv))
                freqEntry.grid(row=rowIdx, column=1, sticky='ew')
                self.targEntries[freq] = [freqVariable]
                rowIdx += 1

        btn_clearTargs = tk.Button(
            self.__innerFrame, text='Clear Targets', command=self.clearTargets)
        btn_clearTargs.grid(column=0, row=5, sticky='new')

        btn_submit = tk.Button(self.__innerFrame,
                               text='Update', command=self._updateButtonCallback)
        btn_submit.grid(column=1, row=5, sticky='new')

        btn_advSettings = tk.Button(self.__innerFrame,
                                    text='Expert & Debug Configuration', relief=tk.FLAT, command=self.__advancedSettings)
        btn_advSettings.grid(column=0, columnspan=2, row=6)

        # START PAYLOAD RECORDING
        self.missionDisplay.set(str("Not Connected"))
        btn_startRecord = tk.Button(frm_sideControl, width=SBWidth, text=self.missionDisplay.get())
        btn_startRecord.grid(column=0, row=4, sticky='nsew')

    def clearTargets(self):
        self.__root._mavModel.setFrequencies(
            [], timeout=self.__root.defaultTimeout)
        self.update()

    def __advancedSettings(self):
        ExpertSettingsDialog(self, self.optionVars)

    def validateFrequency(self, var: tk.IntVar):
        cntrFreq = self.__root._mavModel.getOption('SDR_centerFreq')
        sampFreq = self.__root._mavModel.getOption('SDR_samplingFreq')
        if abs(var.get() - cntrFreq) > sampFreq:
            return False
        return True

    def _updateButtonCallback(self):
        cntrFreq = self.optionVars['SDR_centerFreq'].get()
        sampFreq = self.optionVars['SDR_samplingFreq'].get()

        targetFrequencies = []
        for targetName in self.targEntries:
            if not self.validateFrequency(self.targEntries[targetName][0]):
                tkm.showerror(
                title="Invalid Target Frequency", message="Target frequency " + str(self.targEntries[targetName][0].get()) + " is invalid. Please enter another value.")
                return
            targetFreq = self.targEntries[targetName][0].get()
            targetFrequencies.append(targetFreq)

        self.__root._mavModel.setFrequencies(
            targetFrequencies, self.__root.defaultTimeout)

        if cntrFreq != '':
            lastCntrFreq = self.__root._mavModel.getOption('SDR_centerFreq')
            if int(cntrFreq) != lastCntrFreq:
                self.clearTargets()
        if sampFreq != '':
            lastSampFreq = self.__root._mavModel.getOption(
                'SDR_samplingFreq')
            if int(sampFreq) != lastSampFreq:
                self.clearTargets()

        self.submitGUIOptionVars(0x00)

        self.updateGUIOptionVars()

    def updateGUIOptionVars(self, scope=0):
        optionDict = self.__root._mavModel.getOptions(
            scope, timeout=self.__root.defaultTimeout)
        for optionName, optionValue in optionDict.items():
            self.optionVars[optionName].set(optionValue)
        self.update()

    def submitGUIOptionVars(self, scope: int):
        __baseOptionKeywords = ['SDR_centerFreq',
                                'SDR_samplingFreq', 'SDR_gain']
        __expOptionKeywords = ['DSP_pingWidth', 'DSP_pingSNR',
                               'DSP_pingMax', 'DSP_pingMin', 'SYS_outputDir']
        __engOptionKeywords = ['GPS_mode',
                               'GPS_baud', 'GPS_device', 'SYS_autostart']

        acceptedKeywords = []
        if scope >= 0x00:
            acceptedKeywords.extend(__baseOptionKeywords)
        if scope >= 0x01:
            acceptedKeywords.extend(__expOptionKeywords)
        if scope >= 0xFF:
            acceptedKeywords.extend(__engOptionKeywords)

        options = {keyword: self.optionVars[keyword].get(
        ) for keyword in acceptedKeywords}
        self.__root._mavModel.setOptions(
            timeout=self.__root.defaultTimeout, **options)

    def addTarget(self):
        cntrFreq = self.optionVars['SDR_centerFreq'].get()
        sampFreq = self.optionVars['SDR_samplingFreq'].get()
        addTargetWindow = AddTargetDialog(self, cntrFreq, sampFreq)

        # TODO: remove name
        name = addTargetWindow.name
        freq = addTargetWindow.freq

        if freq is None:
            return

        self.__root._mavModel.addFrequency(freq, self.__root.defaultTimeout)
        self.update()

class ExpertSettingsDialog(tk.Toplevel):
    def __init__(self, parent: SystemSettingsControl, optionVars: dict):
        tk.Toplevel.__init__(self, parent)
        self.__parent = parent
        self.optionVars = optionVars

        # Configure member vars here
        self.__parent.updateGUIOptionVars(0xFF)
        # Modal window
        self.transient(parent)
        self.__createWidget()
        self.wait_window(self)

    def __createWidget(self):
        self.title('Expert/Engineering Settings')
        expSettingsFrame = tk.Frame(self)
        expSettingsFrame.pack(fill=tk.BOTH)

        lbl_pingWidth = tk.Label(
            expSettingsFrame, text='Expected Ping Width(ms)')
        lbl_pingWidth.grid(row=0, column=0, sticky='new')

        lbl_minWidthMult = tk.Label(
            expSettingsFrame, text='Min. Width Multiplier')
        lbl_minWidthMult.grid(row=1, column=0, sticky='new')

        lbl_maxWidthMult = tk.Label(
            expSettingsFrame, text='Max. Width Multiplier')
        lbl_maxWidthMult.grid(row=2, column=0, sticky='new')

        lbl_minPingSNR = tk.Label(expSettingsFrame, text='Min. Ping SNR(dB)')
        lbl_minPingSNR.grid(row=3, column=0, sticky='new')

        lbl_GPSPort = tk.Label(expSettingsFrame, text='GPS Port')
        lbl_GPSPort.grid(row=4, column=0, sticky='new')

        lbl_GPSBaudRate = tk.Label(expSettingsFrame, text='GPS Baud Rate')
        lbl_GPSBaudRate.grid(row=5, column=0, sticky='new')

        lbl_outputDir = tk.Label(expSettingsFrame, text='Output Directory')
        lbl_outputDir.grid(row=6, column=0, sticky='new')

        lbl_GPSMode = tk.Label(expSettingsFrame, text='GPS Mode')
        lbl_GPSMode.grid(row=7, column=0, sticky='new')

        entr_pingWidth = tk.Entry(
            expSettingsFrame, textvariable=self.optionVars['DSP_pingWidth'], width=8)
        entr_pingWidth.grid(row=0, column=1, sticky='new')

        entr_minWidthMult = tk.Entry(
            expSettingsFrame, textvariable=self.optionVars['DSP_pingMin'], width=8)
        entr_minWidthMult.grid(row=1, column=1, sticky='new')

        entr_maxWidthMult = tk.Entry(
            expSettingsFrame, textvariable=self.optionVars['DSP_pingMax'], width=8)
        entr_maxWidthMult.grid(row=2, column=1, sticky='new')

        entr_minPingSNR = tk.Entry(
            expSettingsFrame, textvariable=self.optionVars['DSP_pingSNR'], width=8)
        entr_minPingSNR.grid(row=3, column=1, sticky='new')

        entr_GPSPort = tk.Entry(
            expSettingsFrame, textvariable=self.optionVars['GPS_device'], width=8)
        entr_GPSPort.grid(row=4, column=1, sticky='new')

        entr_GPSBaudRate = tk.Entry(
            expSettingsFrame, textvariable=self.optionVars['GPS_baud'], width=8)
        entr_GPSBaudRate.grid(row=5, column=1, sticky='new')

        entr_outputDir = tk.Entry(
            expSettingsFrame, textvariable=self.optionVars['SYS_outputDir'], width=8)
        entr_outputDir.grid(row=6, column=1, sticky='new')

        entr_GPSMode = tk.Entry(
            expSettingsFrame, textvariable=self.optionVars['GPS_mode'], width=8)
        entr_GPSMode.grid(row=7, column=1, sticky='new')

        btn_submit = tk.Button(self, text='submit', command=self.submit)
        btn_submit.pack()

    def validateParameters(self):
        return True

    def submit(self):
        if not self.validateParameters():
            return
        self.__parent.submitGUIOptionVars(0xFF)

        self.cancel()

    def cancel(self):
        self.__parent.focus_set()
        self.destroy()
        self.__parent.update()

class AddTargetDialog(tk.Toplevel):
    def __init__(self, parent, centerFrequency: int, samplingFrequency: int):
        tk.Toplevel.__init__(self, parent)
        self.__parent = parent
        self.targNameEntry = tk.StringVar()
        self.targFreqEntry = tk.IntVar()

        self.__centerFreq = centerFrequency
        self.__samplingFreq = samplingFrequency

        self.name = None
        self.freq = None

        self.transient(parent)

        self.__createWidget()

        self.wait_window(self)

    def __createWidget(self):
        self.title('Add Target')
        frm_targetSettings = tk.Frame(self)
        frm_targetSettings.pack(fill=tk.BOTH)

        lbl_targetName = tk.Label(frm_targetSettings, text='Target Name:')
        lbl_targetName.grid(row=0, column=0, sticky='new')

        entr_targetName = tk.Entry(
            frm_targetSettings, textvariable=self.targNameEntry)
        entr_targetName.grid(row=0, column=1, sticky='new')

        lbl_targetFreq = tk.Label(
            frm_targetSettings, text='Target Frequency:')
        lbl_targetFreq.grid(row=1, column=0, sticky='new')

        entr_targetFreq = tk.Entry(
            frm_targetSettings, textvariable=self.targFreqEntry)
        entr_targetFreq.grid(row=1, column=1, sticky='new')

        btn_submit = tk.Button(self, text='submit', command=self.submit)
        btn_submit.pack()

        self.bind('<Escape>', self.cancel)

    def validate(self):
        return abs(self.targFreqEntry.get() - self.__centerFreq) <= self.__samplingFreq

    def submit(self):
        if not self.validate():
            tkm.showerror(
            title="Invalid Target Frequency", message="You have entered an invalid target frequency. Please try again.")
            return
        self.name = self.targNameEntry.get()
        self.freq = self.targFreqEntry.get()
        self.cancel()

    def cancel(self):
        self.__parent.focus_set()
        self.destroy()

class ConnectionDialog(tk.Toplevel):
    def __init__(self, parent):
        tk.Toplevel.__init__(self, parent)
        self.__parent = parent
        self.__portEntry = tk.IntVar()
        self.__portEntry.set(9000)  # default value
        self.port = None
        self.comms = None
        self.model = None

        self.transient(parent)

        self.__createWidget()

        self.wait_window(self)

    def __createWidget(self):
        self.title('Connect Settings')

        frm_conType = tk.Frame(master=self, width=350,
                               height=400, bg='light gray')
        frm_conType.pack(fill=tk.Y, side=tk.LEFT)

        lbl_conType = tk.Label(frm_conType, text='Connection Type:')
        lbl_conType.pack(fill=tk.X)

        btn_TCP = tk.Checkbutton(frm_conType, text='TCP')
        btn_TCP.pack(fill=tk.X)

        frm_port = tk.Frame(master=self, width=500, height=400, bg='dark gray')
        frm_port.pack(fill=tk.BOTH, side=tk.RIGHT)

        lbl_port = tk.Label(frm_port, text='Port')
        lbl_port.pack(fill=tk.BOTH)

        entr_port = tk.Entry(frm_port, textvariable=self.__portEntry)
        entr_port.pack(fill=tk.BOTH)

        btn_submit = tk.Button(frm_port, text='Submit', command=self.__submit)
        btn_submit.pack()

        self.bind('<Escape>', self.__cancel)

    def __submit(self):
        try:
            self.port = rctTransport.RCTTCPClient(
                addr='127.0.0.1', port=self.__portEntry.get())
            self.comms = rctComms.gcsComms(self.port)
            self.model = rctCore.MAVModel(self.comms)
            self.model.start()
            self.__cancel()
        except:
            return

    def __cancel(self):
        self.__parent.focus_set()
        self.destroy()

if __name__ == '__main__':
    logName = dt.datetime.now().strftime('%Y.%m.%d.%H.%M.%S_gcs.log')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d: %(levelname)s:%(name)s: %(message)s', datefmt='%Y-%M-%d %H:%m:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ch = logging.FileHandler(logName)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    app = GCS()
    app.mainloop()
    app.quit()
