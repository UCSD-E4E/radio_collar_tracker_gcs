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
        

        port = 'No Port Enterred'
        def submit():
            port = entr_port.get()
            print(port)
            conWindow.destroy()
            conWindow.update()

        btn_submit = tk.Button(frm_port, text='submit', command=submit)
        btn_submit.pack()


    def __mapWidgets(self, button):
        '''
        Internal helper to make GUI widgets for Map
        '''
        button.destroy()

        frm_mapGrid = tk.Frame(master=self)
        frm_mapGrid.pack(fill=tk.BOTH, side=tk.LEFT)
        frm_mapGrid.grid_columnconfigure(0, weight=1)
        frm_mapGrid.grid_rowconfigure(0, weight=1)

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

        frm_mapSpacer = tk.Frame(master=frm_mapGrid, bg='black', height=400, width=450)
        frm_mapSpacer.grid(column=1,row=1) 

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
        frm_system = CollapseFrame(frm_sideControl, 'System: No Connection') 
        frm_system.grid(row=0, column=0, sticky='new')
  
        btn_connect = Button(frm_system.frame, relief=tk.FLAT, width=SBWidth, text ="Connect", command=self.__handleConnectInput)
        btn_connect.grid(column=0, row=0, sticky='new')


        # COMPONENTS TAB
        frm_components = CollapseFrame(frm_sideControl, 'Components')
        frm_components.grid(column=0, row=1, sticky='new')

        lbl_componentNotif = tk.Label(frm_components.frame, width=SBWidth, text='Vehicle not connected')
        lbl_componentNotif.grid(column=0, row=0, sticky='new')


        # DATA DISPLAY TOOLS
        frm_displayTools = CollapseFrame(frm_sideControl, 'Data Display Tools')
        frm_displayTools.grid(column=0, row=2, sticky='n')

        btn_loadMap = Button(frm_displayTools.frame, relief=tk.FLAT, width=SBWidth, text ="Load Map")
        btn_loadMap.grid(column=0, row=0, sticky='new')

        btn_displayMap = Button(frm_displayTools.frame, relief=tk.FLAT, width=SBWidth, text ="Display Map")
        btn_displayMap['command'] = lambda binst=btn_displayMap: self.__mapWidgets(binst)
        btn_displayMap.grid(column=0, row=1, sticky='new')

        btn_export = Button(frm_displayTools.frame, relief=tk.FLAT, width=SBWidth, text ="Export")
        btn_export.grid(column=0, row=2, sticky='new')


        # SYSTEM SETTINGS
        frm_sysSettings = CollapseFrame(frm_sideControl, 'System Settings')
        frm_sysSettings.grid(column=0, row=3, sticky='new')

        lbl_targFreq = tk.Label(frm_sysSettings.frame, text='Target Frequency')
        lbl_targFreq.grid(row=0, column=0, sticky='new')

        lbl_cntrFreq = tk.Label(frm_sysSettings.frame, text='Center Frequency')
        lbl_cntrFreq.grid(row=1, column=0, sticky='new')

        lbl_sampFreq = tk.Label(frm_sysSettings.frame, text='Sampling Frequency')
        lbl_sampFreq.grid(row=2, column=0, sticky='new')

        lbl_sdrGrain = tk.Label(frm_sysSettings.frame, text='SDR Grain')
        lbl_sdrGrain.grid(row=3, column=0, sticky='new')
        
        entr_targFreq = tk.Entry(frm_sysSettings.frame, width=8)
        entr_targFreq.grid(row=0, column=1, sticky='new')
        
        entr_cntrFreq = tk.Entry(frm_sysSettings.frame, width=8)
        entr_cntrFreq.grid(row=1, column=1, sticky='new')
        
        entr_sampFreq = tk.Entry(frm_sysSettings.frame, width=8)
        entr_sampFreq.grid(row=2, column=1, sticky='new')
        
        entr_sdrGrain = tk.Entry(frm_sysSettings.frame, width=8)
        entr_sdrGrain.grid(row=3, column=1, sticky='new')

        btn_submit = tk.Button(frm_sysSettings.frame, text='Update')
        btn_submit.grid(column=1, row=4, sticky='new')

        btn_advSettings = tk.Button(frm_sysSettings.frame, 
                text='Expert & Debug Configuration', relief=tk.FLAT)
        btn_advSettings.grid(column=0, columnspan=2, row=5)


        # START PAYLOAD RECORDING
        btn_startRecord = tk.Button(frm_sideControl, width=SBWidth, text='Start Recording')
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
