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
# 02/18/21  ML  Refactored layer functions in map classes
# 02/11/21  ML  pruned imports
# 02/11/21  ML  Added heatmap display for live precision visualization
# 10/21/20  ML  Removed testing components
# 08/19/20  ML  Added config object to gcs, added appDirs for tiles output
# 08/14/20  ML  Removed excel sheet outputs
# 08/11/20  ML  Added export settings, pings, and vehicle path as json file
# 08/06/20  NH  Refactored map loading code for ease of debugging
# 07/31/20  ML  Added ability to export pings and vehicle paths as Shapefile
# 07/17/20  ML  Translated component status and upgrade displays into PyQt and
#               fixed CollapseFrame nesting issue
# 07/14/20  ML  Added ability to cache and load offline maps
# 07/09/20  ML  Refactored Map Classes to extend added MapWidget Class
# 07/09/20  ML  Converted Static Maps and WebMaps to QGIS
# 06/30/20  ML  Translated tkinter GUI into PyQt5
# 06/25/20  AG  Added more dictionaries to component status display.
# 06/19/20  AG  Added component status display and sub-display.
# 06/17/20  ML  Implemented ability to load webmap from OSM based on coordinates
# 05/29/20  ML  refactored MapControl 
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
import datetime as dt
import utm
import math
import time
import logging
import sys
import os
import os.path
import requests
import rctTransport
import rctComms
import rctCore
import PyQt5.QtCore
from PyQt5.QtWidgets import *
import PyQt5.QtGui
from qgis.core import *
import qgis.gui  
import qgis.utils
import configparser
import json
from threading import Thread
from appdirs import AppDirs
import queue as q
from qgis.core import QgsProject
import numpy as np
import csv
from PyQt5.Qt import QSvgWidget

class GCS(QMainWindow):
    '''
    Ground Control Station GUI
    '''

    SBWidth = 500

    defaultTimeout = 5
    
    sig = PyQt5.QtCore.pyqtSignal()

    def __init__(self, configObj: dict):
        '''
        Creates the GCS Application Object
        Args:
            configObj: a configparser object
        '''
        super().__init__()
        self.__log = logging.getLogger('rctGCS.GCS')
        self._rctPort = None
        self._mavReceiver = None
        self._mavModel = None
        self._buttons = []
        self._systemConnectionTab = None
        self.systemSettingWidget = None
        self.__missionStatusText = "Start Recording"
        self.innerFreqFrame = None
        self.freqElements = []
        self.targEntries = {}
        self.mapControl = None
        self.mapOptions = None
        self.mapDisplay = None
        self.mainThread = None
        self.testFrame = None
        self.config = configObj
        self.pingSheetCreated = False
        self.__createWidgets()
        for button in self._buttons:
            button.config(state='disabled')
                    
        self.queue = q.Queue()
        self.sig.connect(self.execute_inmain, PyQt5.QtCore.Qt.QueuedConnection)
        
    def execute_inmain(self):
        while not self.queue.empty():
            (fn, coord, frequency, numPings) = self.queue.get()
            fn(coord, frequency, numPings)

    def __registerModelCallbacks(self):
        self._mavModel.registerCallback(
            rctCore.Events.Heartbeat, self.__heartbeatCallback)
        self._mavModel.registerCallback(
            rctCore.Events.Exception, self.__handleRemoteException)
        self._mavModel.registerCallback(
            rctCore.Events.VehicleInfo, self.__handleVehicleInfo)
        self._mavModel.registerCallback(
            rctCore.Events.NewPing, self.__handleNewPing)
        self._mavModel.registerCallback(
            rctCore.Events.NewEstimate, self.__handleNewEstimate)

    def mainloop(self, n=0):
        '''
        Main Application Loop
        :param n:
        :type n:
        '''

    def __heartbeatCallback(self):
        '''
        Internal Heartbeat callback
        '''

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
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Critical)
        dialog.setText("No Heartbeats Received")
        dialog.addButton(QMessageBox.Ok)
        dialog.exec()
        
    def __handleNewEstimate(self):
        '''
        Internal callback to handle when a new estimate is received
        '''
        freqList = self._mavModel.EST_mgr.getFrequencies()
        for frequency in freqList:
            params, stale, res = self._mavModel.EST_mgr.getEstimate(frequency)
            
            zone, let = self._mavModel.EST_mgr.getUTMZone()
            coord = utm.to_latlon(params[0], params[1], zone, let)
            
            numPings = self._mavModel.EST_mgr.getNumPings(frequency)
            
            if self.mapDisplay is not None:
                self.mapDisplay.plotEstimate(coord, frequency)
                #self.queue.put( (self.mapDisplay.plotPrecision, coord, frequency, numPings) )
                #self.sig.emit()
                #self.mapDisplay.plotPrecision(coord, frequency, numPings)
                
            if self.mapOptions is not None:
                self.mapOptions.estDistance(coord, stale, res)


    def __handleNewPing(self):
        '''
        Internal callback to handle when a new ping is received
        '''
        freqList = self._mavModel.EST_mgr.getFrequencies()
        for frequency in freqList:
            last = self._mavModel.EST_mgr.getPings(frequency)[-1].tolist()
            zone, let = self._mavModel.EST_mgr.getUTMZone()
            u = (last[0], last[1], zone, let)
            coord = utm.to_latlon(*u)
            power = last[3]

            if self.mapDisplay is not None:
                self.mapDisplay.plotPing(coord, power)



    def __handleVehicleInfo(self):
        '''
        Internal Callback for Vehicle Info
        '''
        if self._mavModel == None:
            return
        last = list(self._mavModel.state['VCL_track'])[-1]
        coord = self._mavModel.state['VCL_track'][last]
        
        self._mavModel.EST_mgr.addVehicleLocation(coord)

        if self.mapDisplay is not None:
            self.mapDisplay.plotVehicle(coord)


    def __handleRemoteException(self):
        '''
        Internal callback for an exception message
        '''
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Critical)
        dialog.setText('An exception has occured!\n%s\n%s' % (
            self._mavModel.lastException[0], self._mavModel.lastException[1]))
        dialog.addButton(QMessageBox.Ok)
        dialog.exec()

    def __startStopMission(self):
        # State machine for start recording -> stop recording

        if self._mavModel == None:
            return

        if self.__missionStatusText == 'Start Recording':
            self.__missionStatusText ='Stop Recording'
            self._mavModel.startMission(timeout=self.defaultTimeout)
        else:
            self.__missionStatusText = 'Start Recording'
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
            
    def exportAll(self):
        '''
        Exports pings, vehcle path, and settings as json file
        '''
        final = {}
        
        if self.mapDisplay is not None:
            vPath = self._mavModel.EST_mgr.getVehiclePath()
            pingDict = {}
            vDict = {}
            indPing = 0
            indPath = 0
            freqList = self._mavModel.EST_mgr.getFrequencies()
            for frequency in freqList:
                pings = self._mavModel.EST_mgr.getPings(frequency)
                for pingArray in pings:
                    pingArr = pingArray.tolist()
                    zone, let = self._mavModel.EST_mgr.getUTMZone()
                    u = (pingArr[0], pingArr[1], zone, let)
                    coord = utm.to_latlon(*u)
                    amp = pingArr[3]
                    newPing = {}
                    newPing['Frequency'] = frequency
                    newPing['Coordinate'] = coord
                    newPing['Amplitude'] = amp
                    pingDict[indPing] = newPing
                    indPing = indPing + 1
            for coord in vPath:
                newCoord = {}
                newCoord['Coordinate'] = (coord[0], coord[1])
                vDict[indPath] = newCoord
                indPath = indPath + 1
                
            final['Pings'] = pingDict
            final['Vehicle Path'] = vDict
            
        if self.systemSettingsWidget is not None:
            optionVars = self.systemSettingsWidget.optionVars
            optionDict = {}
            for key in optionVars.keys():
                if key == "TGT_frequencies":
                    optionDict[key] = optionVars[key]
                elif optionVars[key] is not None:
                    optionDict[key] = optionVars[key].text()
                    
            final['System Settings'] = optionDict
          
        if self._mavModel is not None:      
            varDict = self._mavModel.state
            newVarDict = {}
            
            for key in varDict.keys():
                if ((key == 'STS_sdrStatus') or (key == 'STS_dirStatus') or 
                    (key == 'STS_gpsStatus') or (key == 'STS_sysStatus')):
                    temp = {}
                    temp['name'] = varDict[key].name
                    temp['value'] = varDict[key].value
                    newVarDict[key] = temp
                elif(key == 'VCL_track'):
                    pass
                else:
                    newVarDict[key] = varDict[key]
    
                
            final['States'] = newVarDict
            
        with open('data.json', 'w') as outfile:
            json.dump(final, outfile)
            


    def closeEvent(self, event):
        '''
        Internal callback for window close
        '''
        trans = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:3857"), 
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsProject.instance())
        if self.mapDisplay is not None:
            ext = trans.transformBoundingBox(self.mapDisplay.canvas.extent())
            lat1 = ext.yMaximum()
            lon1 = ext.xMinimum()
            lat2 = ext.yMinimum()
            lon2 = ext.xMaximum()
            
            config_path = 'gcsConfig.ini'   

            self.config['LastCoords'] = {}
            self.config['LastCoords']['Lat1'] = str(lat1)
            self.config['LastCoords']['Lon1'] = str(lon1)
            self.config['LastCoords']['Lat2'] = str(lat2)
            self.config['LastCoords']['Lon2'] = str(lon2)
            with open(config_path, 'w') as configFile:
                self.config.write(configFile)
            
        if self._mavModel is not None:
            self._mavModel.stop()
        super().closeEvent(event)
            

    def __handleConnectInput(self):
        '''
        Internal callback to open Connect Settings
        '''
        connectionDialog = ConnectionDialog(self)
        connectionDialog.exec_()


        self._rctPort = connectionDialog.comms
        self._mavReceiver = connectionDialog.comms
        self._mavModel = connectionDialog.model
        if self._mavModel is None:
            return

        self._systemConnectionTab.updateText("System: Connected")
        self.__registerModelCallbacks()
        self.systemSettingsWidget.updateGUIOptionVars()
        self.statusWidget.updateGUIOptionVars()

    def setMap(self, mapWidget):
        '''
        Function to set the mapDisplay widget
        Args:
            mapWidget: A MapWidget object
        '''
        self.mapDisplay = mapWidget

    def __createWidgets(self):
        '''
        Internal helper to make GUI widgets
        '''
        self.mainThread = PyQt5.QtCore.QThread.currentThread()

        holder = QGridLayout()
        centr_widget = QFrame()
        self.setCentralWidget(centr_widget)

        self.setWindowTitle('RCT GCS')
        frm_sideControl = QScrollArea()

        content = QWidget()
        frm_sideControl.setWidget(content)
        frm_sideControl.setWidgetResizable(True)

        #wlay is the layout that holds all tabs 
        wlay = QVBoxLayout(content)


        # SYSTEM TAB
        self._systemConnectionTab = CollapseFrame(title='System: No Connection')
        self._systemConnectionTab.resize(self.SBWidth, 400)
        lay_sys = QVBoxLayout()
        btn_connect = QPushButton("Connect")
        btn_connect.resize(self.SBWidth, 100)
        btn_connect.clicked.connect(lambda:self.__handleConnectInput())
        lay_sys.addWidget(btn_connect)
        self._systemConnectionTab.setContentLayout(lay_sys)

        # COMPONENTS TAB
        self.statusWidget = StatusDisplay(frm_sideControl, self)


        # DATA DISPLAY TOOLS
        self.mapOptions = MapOptions()
        self.mapOptions.resize(300, 100)
        self.mapControl = MapControl(frm_sideControl, holder, 
                self.mapOptions, self)

        # SYSTEM SETTINGS
        self.systemSettingsWidget = SystemSettingsControl(self)
        self.systemSettingsWidget.resize(self.SBWidth, 400)
        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setWidget(self.systemSettingsWidget)
        
        self.upgradeDisplay = UpgradeDisplay(content, self)
        self.upgradeDisplay.resize(self.SBWidth, 400)
        



        # START PAYLOAD RECORDING
        btn_startRecord = QPushButton(self.__missionStatusText)
        #                            textvariable=self.__missionStatusText, 
        btn_startRecord.clicked.connect(lambda:self.__startStopMission())
        
        btn_exportAll = QPushButton('Export Info')
        btn_exportAll.clicked.connect(lambda:self.exportAll())
        
        btn_precision = QPushButton('Do Precision')
        btn_precision.clicked.connect(lambda:self._mavModel.EST_mgr.doPrecisions(173500000))
        
        btn_heatMap = QPushButton('Display Heatmap')
        btn_heatMap.clicked.connect(lambda:self.mapDisplay.setupHeatMap())

        wlay.addWidget(self._systemConnectionTab)
        wlay.addWidget(self.statusWidget)
        wlay.addWidget(self.mapControl)
        wlay.addWidget(self.systemSettingsWidget)
        wlay.addWidget(self.upgradeDisplay)
        wlay.addWidget(btn_startRecord)
        wlay.addWidget(btn_exportAll)
        wlay.addWidget(btn_precision)
        wlay.addWidget(btn_heatMap)
        
        wlay.addStretch()
        content.resize(self.SBWidth, 400)
        frm_sideControl.setMinimumWidth(self.SBWidth)
        holder.addWidget(frm_sideControl, 0, 0, alignment=PyQt5.QtCore.Qt.AlignLeft)
        holder.addWidget(self.mapOptions, 0, 4, alignment=PyQt5.QtCore.Qt.AlignTop)
        centr_widget.setLayout(holder)
        self.resize(1800, 1100)
        self.show()

class CollapseFrame(QWidget):
    '''
    Custom Collapsible Widget - used to aid in 
    creating a collapsible field attached to a button
    '''
    def __init__(self, title="", parent=None):
        '''
        Creates a new CollapseFrame Object
        Args:
            title: String that will be the displayed label of the 
                   toggle button
            parent: The parent Widget of the CollapseFrame
        '''
        super(CollapseFrame, self).__init__(parent)

        self.content_height = 0
        self.toggle_button = QToolButton(
            text=title, checkable=True, checked=False
        )
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setToolButtonStyle(
            PyQt5.QtCore.Qt.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(PyQt5.QtCore.Qt.RightArrow)
        self.toggle_button.pressed.connect(self.on_pressed)

        self.content_area = QWidget()
        self.content_area.setVisible(False)

        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)


    def updateText(self, text):
        '''
        Public function to allow the label of the toggle button to bt
        changed.
        Args:
            text: A string that will be the new label text for the
                  toggle button
        '''
        self.toggle_button.setText(text)

    @PyQt5.QtCore.pyqtSlot()
    def on_pressed(self):
        '''
        Internal Callback to be called when the toggle button is 
        pressed. Facilitates the collapsing and displaying of the
        content_area contents
        '''
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(
            PyQt5.QtCore.Qt.DownArrow if not checked else PyQt5.QtCore.Qt.RightArrow
        )
        self.content_area.setVisible(not checked)

    def setContentLayout(self, layout):
        '''
        Public function to allow the content_area widget's layout to be
        set. This layout will contain the contents to be collapsed or 
        displayed
        Args:
            layout: A QLayout type object(QVBoxLayout, QGridLayout, etc.)
        '''
        lay = self.content_area.layout()
        del lay
        self.content_area.setLayout(layout)
        
class UpgradeDisplay(CollapseFrame):
    '''
    Custom CollapsFrame widget that is used to facilitate software 
    upgrades
    '''
    def __init__(self, parent, root: GCS):
        '''
        Creates a new UpgradeDisplay widget
        Args:
            parent: the parent QWidget
            root: the GCS application root
        '''
        CollapseFrame.__init__(self, title='Upgrade Software')
        
        self.__parent = parent
        self.__root = root

        self.__innerFrame = None

        self.filename = None
        
        self.__createWidget()
        
    def update(self):
        self.updateGUIOptionVars()
        
    def __createWidget(self):
        '''
        Inner function to create internal widgets
        '''
        self.__innerFrame = QGridLayout()
        
        file_lbl = QLabel('Selected File:')
        self.__innerFrame.addWidget(file_lbl, 1, 0)
        
        self.filename = QLineEdit()
        self.__innerFrame.addWidget(self.filename, 1, 1)

        browse_file_btn = QPushButton('Browse for Upgrade File')
        browse_file_btn.clicked.connect(lambda:self.fileDialogue())
        self.__innerFrame.addWidget(browse_file_btn, 2, 0)
        
        upgrade_btn = QPushButton('Upgrade')
        upgrade_btn.clicked.connect(lambda:self.sendUpgradeFile())
        self.__innerFrame.addWidget(upgrade_btn, 3, 0)

        
        self.setContentLayout(self.__innerFrame)
        
    def fileDialogue(self):
        '''
        Opens a dialog to allow the user to indicate a file
        '''
        filename = QFileDialog.getOpenFileName()
        if filename is None:
            return
        self.filename.setText(filename[0])
        
    def sendUpgradeFile(self):
        '''
        Inner function to send a user specified upgrade file to the mavModel
        '''
        file = open(self.filename.text(), "rb")
        byteStream = file.read()
        self.__root._mavModel.sendUpgradePacket(byteStream)
        
    def updateGUIOptionVars(self):
        pass



class StatusDisplay(CollapseFrame):
    '''
    Custom widget to display system status
    '''
    def __init__(self, parent, root: GCS):
        CollapseFrame.__init__(self, 'Components')
        
        self.__parent = parent
        self.__root = root
        self.componentStatusWidget = None

        self.__innerFrame = None

        self.statusLabel = None

        self.__createWidget()

    def update(self):
        CollapseFrame.update(self)
        self.updateGUIOptionVars()

    def __createWidget(self):
        '''
        Inner funciton to create internal widgets
        '''
        self.__innerFrame = QGridLayout()

        lbl_overall_status = QLabel('Status:')
        self.__innerFrame.addWidget(lbl_overall_status, 1, 0)

        entr_overall_status = QLabel('')
        self.__innerFrame.addWidget(entr_overall_status, 1, 1)
        
        self.componentStatusWidget = ComponentStatusDisplay(root=self.__root)
        h1 = self.componentStatusWidget.innerFrame.sizeHint().height()
        self.__innerFrame.addWidget(self.componentStatusWidget, 2, 0, 1, 2)

        self.statusLabel = entr_overall_status
        h2 = self.__innerFrame.sizeHint().height()
        h3 = self.toggle_button.sizeHint().height()


        self.content_height = h1 + h2 + h3 + h3
        self.setContentLayout(self.__innerFrame)

    def updateGUIOptionVars(self, scope=0):
        varDict = self.__root._mavModel.state

        sdr_status = varDict["STS_sdrStatus"]
        dir_status = varDict["STS_dirStatus"]
        gps_status = varDict["STS_gpsStatus"]
        sys_status = varDict["STS_sysStatus"]
        sw_status = varDict["STS_swStatus"]

        if sys_status == "RCT_STATES.finish":
            self.statusLabel.setText('Stopping')
            self.statusLabel.setStyleSheet("background-color: red")
        elif sdr_status == "SDR_INIT_STATES.fail" or dir_status == "OUTPUT_DIR_STATES.fail" or gps_status == "GPS_STATES.fail" or sys_status == "RCT_STATES.fail" or (sw_status != 0 and sw_status != 1):
            self.statusLabel.setText('Failed')
            self.statusLabel.setStyleSheet("background-color: red")
        elif sys_status == "RCT_STATES.start" or sys_status == "RCT_STATES.wait_end":
            self.statusLabel.setText('Running')
            self.statusLabel.setStyleSheet("background-color: green")
        elif sdr_status == "SDR_INIT_STATES.rdy" and dir_status == "OUTPUT_DIR_STATES.rdy" and gps_status == "EXTS_STATES.rdy" and sys_status == "RCT_STATES.wait_start" and sw_status == 1:
            self.statusLabel.setText('Idle')
            self.statusLabel.setStyleSheet("background-color: yellow")
        else:
            self.statusLabel.setText('Not Connected')
            self.statusLabel.setStyleSheet("background-color: yellow")
            
        self.componentStatusWidget.update()

class ComponentStatusDisplay(CollapseFrame):
    '''
    Custom widget class to display the current statuses of system
    components
    '''
    def __init__(self, root: GCS):
        '''
        Creates a ComponentStatusDisplay object
        Args:
            root: The application root
        '''
        CollapseFrame.__init__(self, 'Component Statuses')
        self.sdrMap = {
            "SDR_INIT_STATES.find_devices": {'text': 'SDR: Searching for devices', 'bg':'yellow'},
            "SDR_INIT_STATES.wait_recycle": {'text':'SDR: Recycling!', 'bg':'yellow'},
            "SDR_INIT_STATES.usrp_probe": {'text':'SDR: Initializing SDR', 'bg':'yellow'},
            "SDR_INIT_STATES.rdy": {'text':'SDR: Ready', 'bg':'green'},
            "SDR_INIT_STATES.fail": {'text':'SDR: Failed!', 'bg':'red'}
        }

        self.dirMap = {
            "OUTPUT_DIR_STATES.get_output_dir": {'text':'DIR: Searching', 'bg':'yellow'},
            "OUTPUT_DIR_STATES.check_output_dir": {'text':'DIR: Checking for mount', 'bg':'yellow'},
            "OUTPUT_DIR_STATES.check_space": {'text':'DIR: Checking for space', 'bg':'yellow'},
            "OUTPUT_DIR_STATES.wait_recycle": {'text':'DIR: Recycling!', 'bg':'yellow'},
            "OUTPUT_DIR_STATES.rdy": {'text':'DIR: Ready', 'bg':'green'},
            "OUTPUT_DIR_STATES.fail": {'text':'DIR: Failed!', 'bg':'red'},
        }

        self.gpsMap = {
            "EXTS_STATES.get_tty": {'text': 'GPS: Getting TTY Device', 'bg': 'yellow'},
            "EXTS_STATES.get_msg": {'text': 'GPS: Waiting for message', 'bg': 'yellow'},
            "EXTS_STATES.wait_recycle": {'text': 'GPS: Recycling', 'bg': 'yellow'},
            "EXTS_STATES.rdy": {'text': 'GPS: Ready', 'bg': 'green'},
            "EXTS_STATES.fail": {'text': 'GPS: Failed!', 'bg': 'red'}
        }

        self.sysMap = {
            "RCT_STATES.init": {'text': 'SYS: Initializing', 'bg': 'yellow'},
            "RCT_STATES.wait_init": {'text': 'SYS: Initializing', 'bg': 'yellow'},
            "RCT_STATES.wait_start": {'text': 'SYS: Ready for start', 'bg': 'green'},
            "RCT_STATES.start": {'text': 'SYS: Starting', 'bg': 'blue'},
            "RCT_STATES.wait_end": {'text': 'SYS: Running', 'bg': 'blue'},
            "RCT_STATES.finish": {'text': 'SYS: Stopping', 'bg': 'blue'},
            "RCT_STATES.fail": {'text': 'SYS: Failed!', 'bg': 'red'},
        }
        
        self.swMap = {
            '0': {'text': 'SW: OFF', 'bg': 'yellow'},
            '1': {'text': 'SW: ON', 'bg': 'green'},
        }
        
        self.compDicts = {
            "STS_sdrStatus": self.sdrMap,
            "STS_dirStatus": self.dirMap,
            "STS_gpsStatus": self.gpsMap,
            "STS_sysStatus": self.sysMap,
            "STS_swStatus": self.swMap,
        }
            
        #self.__parent = parent
        self.__root = root

        self.innerFrame = None

        self.statusLabels = {}

        self.__createWidget()

    def update(self):
        self.updateGUIOptionVars()

    def __createWidget(self):
        '''
        Inner Function to create internal widgets
        '''
        self.innerFrame = QGridLayout()

        lbl_sdr_status = QLabel('SDR Status')
        self.innerFrame.addWidget(lbl_sdr_status, 1, 0)

        lbl_dir_status = QLabel('Storage Status')
        self.innerFrame.addWidget(lbl_dir_status, 2, 0)

        lbl_gps_status = QLabel('GPS Status')
        self.innerFrame.addWidget(lbl_gps_status, 3, 0)

        lbl_sys_status = QLabel('System Status')
        self.innerFrame.addWidget(lbl_sys_status, 4, 0)

        lbl_sw_status = QLabel('Software Status')
        self.innerFrame.addWidget(lbl_sw_status, 5, 0)

        entr_sdr_status = QLabel('')
        self.innerFrame.addWidget(entr_sdr_status, 1, 1)

        entr_dir_status = QLabel('')
        self.innerFrame.addWidget(entr_dir_status, 2, 1)

        entr_gps_status = QLabel('')
        self.innerFrame.addWidget(entr_gps_status, 3, 1)

        entr_sys_status = QLabel('')
        self.innerFrame.addWidget(entr_sys_status, 4, 1)

        entr_sw_status = QLabel('')
        self.innerFrame.addWidget(entr_sw_status, 5, 1)

        self.statusLabels["STS_sdrStatus"] = entr_sdr_status
        self.statusLabels["STS_dirStatus"] = entr_dir_status
        self.statusLabels["STS_gpsStatus"] = entr_gps_status
        self.statusLabels["STS_sysStatus"] = entr_sys_status
        self.statusLabels["STS_swStatus"] = entr_sw_status
        self.setContentLayout(self.innerFrame)

    def updateGUIOptionVars(self, scope=0):
        varDict = self.__root._mavModel.state
        for varName, varValue in varDict.items():
            print(varName)
            try:
                configDict = self.compDicts[varName]
                configOpts = configDict[str(varValue)]
                self.statusLabels[varName].setText(configOpts['text'])
                style = "background-color: %s" % configOpts['bg']
                self.statusLabels[varName].setStyleSheet(style)
            except KeyError:
                continue

class SystemSettingsControl(CollapseFrame):
    '''
    This class provides for a custom widget that facilitates 
    configuring system settings for the drone
    '''
    def __init__(self, root):
        '''
        Creates a SystemSettingsControl Widget
        Args:
            root: rctGCS instance
        '''
        CollapseFrame.__init__(self, title='System Settings')
        #self.__parent = parent
        self.__root = root

        self.__innerFrame = None
        self.frm_targHolder = None
        self.scroll_targHolder = None
        self.widg_targHolder = None
        self.targEntries = {}

        self.optionVars = {
            "TGT_frequencies": [],
            "SDR_centerFreq": None,
            "SDR_samplingFreq": None,
            "SDR_gain": None,
            "DSP_pingWidth": None,
            "DSP_pingSNR": None,
            "DSP_pingMax": None,
            "DSP_pingMin": None,
            "GPS_mode": None,
            "GPS_device": None,
            "GPS_baud": None,
            "SYS_outputDir": None,
            "SYS_autostart": None,
        }
        self.__createWidget()

    def update(self):
        '''
        Function to facilitate the updating of internal widget 
        displays
        '''
        self.__updateWidget() #add updated values

        # Repaint widgets and layouts
        self.widg_targHolder.repaint()
        self.scroll_targHolder.repaint()
        self.frm_targHolder.activate()
        CollapseFrame.repaint(self)
        self.__innerFrame.activate()
        

    def __updateWidget(self):
        '''
        Function to update displayed values of target widgets
        '''
        if self.frm_targHolder:
            while (self.frm_targHolder.count() > 0):
                child = self.frm_targHolder.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        rowIdx = 0
        self.targEntries = {}
        if self.__root._mavModel is not None:
            cntrFreq = self.__root._mavModel.getOption('SDR_centerFreq')
            sampFreq = self.__root._mavModel.getOption('SDR_samplingFreq')
            self.optionVars["SDR_centerFreq"].setText(str(cntrFreq))
            self.optionVars["SDR_samplingFreq"].setText(str(sampFreq))
            self.frm_targHolder.setVerticalSpacing(0)
            time.sleep(0.5)
            for freq in self.__root._mavModel.getFrequencies(self.__root.defaultTimeout):
                #Put in frm_targHolder
                new = QHBoxLayout()
                freqLabel = QLabel('Target %d' % (rowIdx + 1))
                freqVariable = freq
                freqEntry = QLineEdit()
                val = QIntValidator(cntrFreq-sampFreq, cntrFreq+sampFreq)                            
                freqEntry.setValidator(val)
                freqEntry.setText(str(freqVariable))

                # Add new target to layout
                new.addWidget(freqLabel)
                new.addWidget(freqEntry)
                newWidg = QWidget()
                newWidg.setLayout(new)
                self.frm_targHolder.addRow(newWidg)

                
                self.targEntries[freq] = [freq]
                rowIdx += 1

    def __createWidget(self):
        '''
        Inner function to create widgets in the System Settings tab
        '''
        self.__innerFrame = QGridLayout()

        lbl_cntrFreq = QLabel('Center Frequency')

        lbl_sampFreq = QLabel('Sampling Frequency')

        lbl_sdrGain = QLabel('SDR Gain')

        self.optionVars['SDR_centerFreq'] = QLineEdit()


        self.optionVars['SDR_samplingFreq'] = QLineEdit()

        self.optionVars['SDR_gain'] = QLineEdit()

        self.frm_targHolder = QFormLayout() # Layout that holds target widgets
        self.widg_targHolder = QWidget()
        self.scroll_targHolder = QScrollArea()
        self.scroll_targHolder.setWidgetResizable(True)
        self.scroll_targHolder.setWidget(self.widg_targHolder)
        self.widg_targHolder.setLayout(self.frm_targHolder)

        rowIdx = 0
        self.targEntries = {}
        if self.__root._mavModel is not None:
            for freq in self.__root._mavModel.getFrequencies(self.__root.defaultTimeout):
                #Put in frm_targHolder
                new = QHBoxLayout()
                freqLabel = QLabel('Target %d' % (rowIdx + 1))
                freqVariable = freq
                freqEntry = QLineEdit()
                cntrFreq = self.__root._mavModel.getOption('SDR_centerFreq')
                sampFreq = self.__root._mavModel.getOption('SDR_samplingFreq')
                val = QIntValidator(cntrFreq-sampFreq, cntrFreq+sampFreq)                            
                freqEntry.setValidator(val)
                freqEntry.setText(freqVariable)
                
                new.addWidget(freqLabel)
                new.addWidget(freqEntry)
                newWidg = QWidget()
                newWidg.setLayout(new)
                self.frm_targHolder.addRow(newWidg)
                self.targEntries[freq] = [freq]
                rowIdx += 1

        # Add widgets to main layout: self.__innerFrame
        self.__innerFrame.addWidget(self.scroll_targHolder, 4, 0, 1, 2)
        self.__innerFrame.addWidget(lbl_cntrFreq, 1, 0)
        self.__innerFrame.addWidget(lbl_sampFreq, 2, 0)
        self.__innerFrame.addWidget(lbl_sdrGain, 3, 0)
        self.__innerFrame.addWidget(self.optionVars['SDR_centerFreq'], 1, 1)
        self.__innerFrame.addWidget(self.optionVars['SDR_samplingFreq'], 2, 1)
        self.__innerFrame.addWidget(self.optionVars['SDR_gain'], 3, 1)

        btn_addTarget = QPushButton('Add Target')
        btn_addTarget.clicked.connect(lambda:self.addTarget())
        self.__innerFrame.addWidget(btn_addTarget, 0, 0, 1, 2)
        btn_clearTargs = QPushButton('Clear Targets')
        btn_clearTargs.clicked.connect(lambda:self.clearTargets())
        self.__innerFrame.addWidget(btn_clearTargs, 5, 0)

        btn_submit = QPushButton('Update')
        btn_submit.clicked.connect(lambda:self._updateButtonCallback())
        self.__innerFrame.addWidget(btn_submit, 5, 1)

        btn_advSettings = QPushButton('Expert & Debug Configuration')
        btn_advSettings.clicked.connect(lambda:self.__advancedSettings())
        self.__innerFrame.addWidget(btn_advSettings, 6, 0, 1, 2)

        self.setContentLayout(self.__innerFrame)


    def clearTargets(self):
        '''
        Helper function to clear target frequencies from UI and 
        MavMode
        '''
        self.__root._mavModel.setFrequencies(
            [], timeout=self.__root.defaultTimeout)
        self.update()

    def __advancedSettings(self):
        '''
        Helper function to open an ExpertSettingsDialog widget
        '''
        openSettings = ExpertSettingsDialog(self, self.optionVars)
        openSettings.exec_()

    def validateFrequency(self, var: int):
        '''
        Helper function to ensure frequencies are within an appropriate
        range
        Args:
            var: An integer value that is the frequency to be validated
        '''
        cntrFreq = self.__root._mavModel.getOption('SDR_centerFreq')
        sampFreq = self.__root._mavModel.getOption('SDR_samplingFreq')
        if abs(var - cntrFreq) > sampFreq:
            return False
        return True

    def _updateButtonCallback(self):
        '''
        Internal callback to be called when the update button is
        pressed
        '''
        cntrFreq = int(self.optionVars['SDR_centerFreq'].text())
        sampFreq = int(self.optionVars['SDR_samplingFreq'].text())

        targetFrequencies = []
        for targetName in self.targEntries:
            if not self.validateFrequency(self.targEntries[targetName][0]):
                dialog = QMessageBox()
                dialog.setIcon(QMessageBox.Critical)
                dialog.setText("Target frequency " + 
                        str(self.targEntries[targetName][0]) + 
                        " is invalid. Please enter another value.")
                dialog.addButton(QMessageBox.Ok)
                dialog.exec()
                return
            targetFreq = self.targEntries[targetName][0]
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

    def updateGUIOptionVars(self, scope=0, options=None):
        if options is not None:
            self.optionVars = options
        optionDict = self.__root._mavModel.getOptions(
            scope, timeout=self.__root.defaultTimeout)
        for optionName, optionValue in optionDict.items():
            try:
                self.optionVars[optionName].setText(str(optionValue))
            except AttributeError:
                print(optionName)
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

        options = {}
        
        for keyword in acceptedKeywords:
            try:
                options[keyword] = int(self.optionVars[keyword].text())
            except ValueError:
                options[keyword] = float(self.optionVars[keyword].text())
        self.__root._mavModel.setOptions(
            timeout=self.__root.defaultTimeout, **options)

    def addTarget(self):
        '''
        Internal function to facilitate users adding target frequencies
        '''
        cntrFreq = int(self.optionVars['SDR_centerFreq'].text())
        sampFreq = int(self.optionVars['SDR_samplingFreq'].text())
        addTargetWindow = AddTargetDialog(self.frm_targHolder, cntrFreq, sampFreq)
        addTargetWindow.exec_()

        # TODO: remove name
        name = addTargetWindow.name
        freq = addTargetWindow.freq

        if freq is None:
            return

        self.__root._mavModel.addFrequency(freq, self.__root.defaultTimeout)

        self.update()



class ExpertSettingsDialog(QWizard):
    '''
    A Custom Dialog Widget to facilitate user input for expert 
    settings
    '''
    def __init__(self, parent, optionVars):
        '''
        Creates a new ExpertSettingsDialog
        Args:
            parent: the parent widget of the dialog
            optionVars: Dictionary object of option variables
        '''
        super(ExpertSettingsDialog, self).__init__(parent)
        self.parent = parent
        self.addPage(ExpertSettingsDialogPage(self, optionVars))
        self.setWindowTitle('Expert/Engineering Settings')
        self.resize(640,480)

class ExpertSettingsDialogPage(QWizardPage):
    '''
    Custom DialogPage widget to facilitate user configured
    expert settings
    '''
    def __init__(self, parent=None, optionVars=None):
        '''
        Creates a new ExpertSettingsDialogPage object
        Args:
            parent: An ExpertSettingsDialog object
            optionVars: Dictionary object of option variables
        '''
        super(ExpertSettingsDialogPage, self).__init__(parent)
        self.__parent = parent
        self.optionVars = optionVars

        self.__createWidget()
        # Configure member vars here
        self.__parent.parent.updateGUIOptionVars(0xFF, self.optionVars)

    def __createWidget(self):
        '''
        Internal function to create widgets
        '''
        expSettingsFrame = QGridLayout()

        lbl_pingWidth = QLabel('Expected Ping Width(ms)')
        expSettingsFrame.addWidget(lbl_pingWidth, 0, 0)

        lbl_minWidthMult = QLabel('Min. Width Multiplier')
        expSettingsFrame.addWidget(lbl_minWidthMult, 1, 0)

        lbl_maxWidthMult = QLabel('Max. Width Multiplier')
        expSettingsFrame.addWidget(lbl_maxWidthMult, 2, 0)

        lbl_minPingSNR = QLabel('Min. Ping SNR(dB)')
        expSettingsFrame.addWidget(lbl_minPingSNR, 3, 0)

        lbl_GPSPort = QLabel('GPS Port')
        expSettingsFrame.addWidget(lbl_GPSPort, 4, 0)

        lbl_GPSBaudRate = QLabel('GPS Baud Rate')
        expSettingsFrame.addWidget(lbl_GPSBaudRate, 5, 0)

        lbl_outputDir = QLabel('Output Directory')
        expSettingsFrame.addWidget(lbl_outputDir, 6, 0)

        lbl_GPSMode = QLabel('GPS Mode')
        expSettingsFrame.addWidget(lbl_GPSMode, 7, 0)

        self.optionVars['DSP_pingWidth'] = QLineEdit()
        expSettingsFrame.addWidget(self.optionVars['DSP_pingWidth'], 0, 1)

        self.optionVars['DSP_pingMin'] = QLineEdit()
        expSettingsFrame.addWidget(self.optionVars['DSP_pingMin'], 1, 1)

        self.optionVars['DSP_pingMax'] = QLineEdit()
        expSettingsFrame.addWidget(self.optionVars['DSP_pingMax'], 2, 1)

        self.optionVars['DSP_pingSNR'] = QLineEdit()
        expSettingsFrame.addWidget(self.optionVars['DSP_pingSNR'], 3, 1)

        self.optionVars['GPS_device'] = QLineEdit()
        expSettingsFrame.addWidget(self.optionVars['GPS_device'], 4, 1)

        self.optionVars['GPS_baud'] = QLineEdit()
        expSettingsFrame.addWidget(self.optionVars['GPS_baud'], 5, 1)

        self.optionVars['SYS_outputDir'] = QLineEdit()
        expSettingsFrame.addWidget(self.optionVars['SYS_outputDir'], 6, 1)

        self.optionVars['GPS_mode'] = QLineEdit()
        expSettingsFrame.addWidget(self.optionVars['GPS_mode'], 7, 1)

        btn_submit = QPushButton('submit')
        btn_submit.clicked.connect(lambda:self.submit())
        expSettingsFrame.addWidget(btn_submit, 8, 0, 1, 2)

        self.setLayout(expSettingsFrame)

    def validateParameters(self):
        '''
        Inner function to validate parameters set
        '''
        return True

    def submit(self):
        '''
        Inner function to submit enterred information
        '''
        if not self.validateParameters():
            return
        self.__parent.parent.submitGUIOptionVars(0xFF)



class AddTargetDialog(QWizard):
    '''
    A Custom Dialog Widget to facilitate user-added target frequencies
    '''
    def __init__(self, parent, centerFrequency: int, samplingFrequency: int):
        '''
        Creates a new AddTargetDialog
        Args:
            parent: the parent widget of the AddTargetDialog
            centerFrequency: an integer frequency value
            samplingFrequency: an integer value to indicate sampling
                               range
        '''
        QWizardPage.__init__(self)
        self.__parent = parent
        self.name = "filler"
        self.freq = 0
        self.centerFrequency = centerFrequency
        self.samplingFrequency = samplingFrequency
        self.page = AddTargetDialogPage(self, centerFrequency, samplingFrequency)
        self.addPage(self.page)
        self.setWindowTitle('Add Target')
        self.resize(640,480)
        self.button(QWizard.FinishButton).clicked.connect(self.submit)

    def validate(self):
        '''
        Helper Method ot validate input frequency
        '''
        return abs(int(self.page.targFreqEntry.text()) - self.centerFrequency) <= self.samplingFrequency


    def submit(self):
        '''
        Internal function to submit newly added target frequency 
        '''
        if not self.validate():
            dialog = QMessageBox()
            dialog.setIcon(QMessageBox.Critical)
            dialog.setText("You have entered an invalid target frequency. Please try again.")
            dialog.addButton(QMessageBox.Ok)
            dialog.exec()
            return
        self.name = self.page.targNameEntry.text()
        self.freq = int(self.page.targFreqEntry.text())


class AddTargetDialogPage(QWizardPage):
    '''
    Custom DialogPage widget to facilitate user-added target
    frequencies
    '''
    def __init__(self, parent, centerFrequency: int, samplingFrequency: int):
        '''
        Creates a new AddTargetDialog
        Args:
            parent: the parent widget of the AddTargetDialog
            centerFrequency: an integer frequency value
            samplingFrequency: an integer value to indicate sampling
                               range
        '''
        QWizardPage.__init__(self, parent)
        self.__parent = parent
        self.targNameEntry = None
        self.targFreqEntry = None

        self.__centerFreq = centerFrequency
        self.__samplingFreq = samplingFrequency

        self.name = None
        self.freq = None

        self.__createWidget()


    def __createWidget(self):
        '''
        Internal function to create widgets
        '''
        rx  = QRegExp("[0-9]{30}")                           
        val = QRegExpValidator(rx)                            
        frm_targetSettings = QGridLayout()

        lbl_targetName = QLabel('Target Name:')
        frm_targetSettings.addWidget(lbl_targetName, 0, 0)

        #entr_targetName = QLineEdit()
        self.targNameEntry = QLineEdit()
        frm_targetSettings.addWidget(self.targNameEntry, 0, 1)

        lbl_targetFreq = QLabel('Target Frequency:')
        frm_targetSettings.addWidget(lbl_targetFreq, 1, 0)

        self.targFreqEntry = QLineEdit()
        self.targFreqEntry.setValidator(val)
        frm_targetSettings.addWidget(self.targFreqEntry, 1, 1)

        '''
        btn_submit = QPushButton('submit')
        btn_submit.clicked.connect(lambda:self.submit())
        frm_targetSettings.addWidget(btn_submit, 2, 0, 1, 2)
        '''
        self.setLayout(frm_targetSettings)




class ConnectionDialog(QWizard):
    '''
    Custom Dialog widget to facilitate connecting to the drone
    '''
    def __init__(self, parent):
        '''
        Creates new ConnectionDialog widget
        Args:
            parent: the parent widget of this object
        '''
        super(ConnectionDialog, self).__init__()
        self.__parent = parent
        self.setWindowTitle('Connect Settings')
        self.page = ConnectionDialogPage(self)
        self.addPage(self.page)
        self.port = None
        self.comms = None
        self.model = None
        self.resize(640,480)
        self.button(QWizard.FinishButton).clicked.connect(lambda:self.submit())

    def submit(self):
        '''
        Internal Function to submit user inputted connection settings
        '''
        try:
            print(self.page.portEntry.text())
            self.port = rctTransport.RCTTCPClient(
                addr='127.0.0.1', port=int(self.page.portEntry.text()))
            self.comms = rctComms.gcsComms(self.port)
            self.model = rctCore.MAVModel(self.comms)
            self.model.start()
        except:
            return

class ConnectionDialogPage(QWizardPage):
    '''
    Custom DialogPage widget - Allows the user to configure 
    settings to connect to the drone
    '''
    def __init__(self, parent):
        '''
        Creates a new AddTargetDialog
        Args:
            parent: The parent ConnectionDialog widget
        '''
        super(ConnectionDialogPage, self).__init__(parent)
        self.__parent = parent
        #self.__portEntry = tk.IntVar()
        #self.__portEntry.set(9000)  # default value
        self.__portEntryVal = 9000 # default value
        self.portEntry = None # default value
        self.port = None
        self.comms = None
        self.model = None


        self.__createWidget()


    def __createWidget(self):
        '''
        Internal function to create widgets
        '''
        frm_holder = QHBoxLayout()
        frm_holder.addStretch(1)
        frm_conType = QVBoxLayout()
        frm_conType.addStretch(1)

        lbl_conType = QLabel('Connection Type:')
        frm_conType.addWidget(lbl_conType)

        btn_TCP = QCheckBox('TCP')
        frm_conType.addWidget(btn_TCP)

        frm_port = QVBoxLayout()
        frm_port.addStretch(1)

        lbl_port = QLabel('Port')
        frm_port.addWidget(lbl_port)

        self.portEntry = QLineEdit() #textvariable=self.__portEntry)
        self.portEntry.setText(str(self.__portEntryVal))
        frm_port.addWidget(self.portEntry)



        frm_holder.addLayout(frm_conType)
        frm_holder.addLayout(frm_port)
        self.setLayout(frm_holder)





class MapControl(CollapseFrame): 
    '''
    Custom Widget Class to facilitate Map Loading
    '''   
    def __init__(self, parent, holder, mapOptions, root: GCS):
        CollapseFrame.__init__(self, title='Map Display Tools')
        self.__parent = parent
        self.__root = root
        self.__mapOptions = mapOptions
        self.__holder = holder
        self.__mapFrame = None
        self.__latEntry = None
        self.__lonEntry = None
        self.__zoomEntry = None

        self.__createWidgets()



    def __createWidgets(self):
        '''
        Internal function to create widgets
        '''
        controlPanelHolder = QScrollArea()
        content = QWidget()

        controlPanelHolder.setWidget(content)
        controlPanelHolder.setWidgetResizable(True)

        controlPanel = QVBoxLayout(content)

        controlPanel.addStretch()

        self.__mapFrame = QWidget()
        self.__mapFrame.resize(800, 500)
        self.__holder.addWidget(self.__mapFrame, 0, 0, 1, 3)
        btn_loadMap = QPushButton('Load Map')
        btn_loadMap.clicked.connect(lambda:self.__loadMapFile())
        controlPanel.addWidget(btn_loadMap)


        
        frm_loadWebMap = QLabel('Load WebMap')
        controlPanel.addWidget(frm_loadWebMap)
        lay_loadWebMap = QGridLayout()
        lay_loadWebMapHolder = QVBoxLayout()
        lay_loadWebMapHolder.addStretch()


        lbl_p1 = QLabel('Lat/Long NW Point')
        lay_loadWebMap.addWidget(lbl_p1, 0, 0)

        self.__p1latEntry = QLineEdit()
        lay_loadWebMap.addWidget(self.__p1latEntry, 0, 1)
        self.__p1lonEntry = QLineEdit()
        lay_loadWebMap.addWidget(self.__p1lonEntry, 0, 2)

        lbl_p2 = QLabel('Lat/Long SE Point')
        lay_loadWebMap.addWidget(lbl_p2, 1, 0)

        self.__p2latEntry = QLineEdit()
        lay_loadWebMap.addWidget(self.__p2latEntry, 1, 1)
        self.__p2lonEntry = QLineEdit()
        lay_loadWebMap.addWidget(self.__p2lonEntry, 1, 2)

        
        btn_loadWebMap = QPushButton('Load from Web') 
        btn_loadWebMap.clicked.connect(lambda:self.__loadWebMap())
        lay_loadWebMap.addWidget(btn_loadWebMap, 3, 1, 1, 2)
        
        btn_loadCachedMap = QPushButton('Load from Cache') 
        btn_loadCachedMap.clicked.connect(lambda:self.__loadCachedMap())
        lay_loadWebMap.addWidget(btn_loadCachedMap, 4, 1, 1, 2)

        controlPanel.addWidget(frm_loadWebMap)
        controlPanel.addLayout(lay_loadWebMap)


        self.setContentLayout(controlPanel)
        
    def __coordsFromConf(self):
        '''
        Internal function to pull past coordinates from the config
        file if they exist
        '''

        try:
            lat1 = self.__root.config['LastCoords']['lat1']
            lon1 = self.__root.config['LastCoords']['lon1']
            lat2 = self.__root.config['LastCoords']['lat2']
            lon2 = self.__root.config['LastCoords']['lon2']
            return lat1, lon1, lat2, lon2
        except KeyError:
            return None, None, None, None
            
        
    def __loadWebMap(self):
        '''
        Internal function to load map from web 
        '''
        lat1 = self.__p1latEntry.text()
        lon1 = self.__p1lonEntry.text()
        lat2 = self.__p2latEntry.text()
        lon2 = self.__p2lonEntry.text()
        
        
        
        if (lat1 == '') or (lon1 == '') or (lat2 == '') or (lon2 == ''):
            lat1, lon1, lat2, lon2 = self.__coordsFromConf()
            
            self.__p1latEntry.setText(lat1)
            self.__p1lonEntry.setText(lon1)
            self.__p2latEntry.setText(lat2)
            self.__p2lonEntry.setText(lon2)
        
        if lat1 is None or lat2 is None or lon1 is None or lon2 is None:
            lat1 = 90
            lat2 = -90
            lon1 = -180
            lon2 = 180
            self.__p1latEntry.setText(lat1)
            self.__p1lonEntry.setText(lon1)
            self.__p2latEntry.setText(lat2)
            self.__p2lonEntry.setText(lon2)
        p1lat = float(lat1)
        p1lon = float(lon1)
        p2lat = float(lat2)
        p2lon = float(lon2)
        
        try:
            temp = WebMap(self.__holder, p1lat, p1lon, 
                    p2lat, p2lon, False)
        except RuntimeError:
            return
        self.__mapFrame.setParent(None)
        self.__mapFrame = temp
        self.__mapFrame.resize(800, 500)
        self.__mapOptions.setMap(self.__mapFrame, True)
        self.__root.setMap(self.__mapFrame)

    def __loadCachedMap(self):
        '''
        Internal function to load map from cached tiles
        '''
        lat1 = self.__p1latEntry.text()
        lon1 = self.__p1lonEntry.text()
        lat2 = self.__p2latEntry.text()
        lon2 = self.__p2lonEntry.text()
        
        if (lat1 == '') or (lon1 == '') or (lat2 == '') or (lon2 == ''):
            lat1, lon1, lat2, lon2 = self.__coordsFromConf()
            
            self.__p1latEntry.setText(lat1)
            self.__p1lonEntry.setText(lon1)
            self.__p2latEntry.setText(lat2)
            self.__p2lonEntry.setText(lon2)
        
        if lat1 is None or lat2 is None or lon1 is None or lon2 is None:
            lat1 = 90
            lat2 = -90
            lon1 = -180
            lon2 = 180
            self.__p1latEntry.setText(lat1)
            self.__p1lonEntry.setText(lon1)
            self.__p2latEntry.setText(lat2)
            self.__p2lonEntry.setText(lon2)
        p1lat = float(lat1)
        p1lon = float(lon1)
        p2lat = float(lat2)
        p2lon = float(lon2)
        
        self.__mapFrame.setParent(None)
        self.__mapFrame = WebMap(self.__holder, p1lat, p1lon, 
                p2lat, p2lon, True)
        self.__mapFrame.resize(800, 500)
        self.__mapOptions.setMap(self.__mapFrame, True)
        self.__root.setMap(self.__mapFrame)

    def __loadMapFile(self):
        '''
        Internal function to load user-specified raster file
        '''
        self.__mapFrame.setParent(None)
        self.__mapFrame = StaticMap(self.__holder)
        self.__mapFrame.resize(800, 500)
        self.__mapOptions.setMap(self.__mapFrame, False)
        self.__root.setMap(self.__mapFrame)



class PolygonMapTool(qgis.gui.QgsMapToolEmitPoint):
    def __init__(self, canvas):
        self.canvas = canvas
        qgis.gui.QgsMapToolEmitPoint.__init__(self, self.canvas)
        #Creating a list for all vertex coordinates
        self.vertices = []
        self.rubberBand = qgis.gui.QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setColor(PyQt5.QtCore.Qt.red)
        self.rubberBand.setWidth(1)
        self.reset()

    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(True)

    def canvasPressEvent(self, e):
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint
        self.isEmittingPoint = True
        self.addVertex(self.startPoint, self.canvas)
        self.showLine(self.startPoint, self.endPoint)
        self.showPolygon()

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())
        self.showLine(self.startPoint, self.endPoint)

    def addVertex(self, selectPoint, canvas):
        vertex = QgsPointXY(selectPoint)
        self.vertices.append(vertex)

    def showPolygon(self):
        if (len(self.vertices) > 1):
            self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
            r = len(self.vertices) - 1
            for i in range(r):
                self.rubberBand.addPoint(self.vertices[i], False)
            self.rubberBand.addPoint(self.vertices[r], True)
            self.rubberBand.show()

    def showLine(self, startPoint, endPoint):
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return
        
        point1 = QgsPointXY(startPoint.x(), startPoint.y())

        self.rubberBand.addPoint(point1, True)

        self.rubberBand.show()

    def deactivate(self):
        qgis.gui.QgsMapTool.deactivate(self)
        self.deactivated.emit()


class RectangleMapTool(qgis.gui.QgsMapToolEmitPoint):
    '''
    Custom qgis.gui.QgsMapTool to select a rectangular area of a QgsMapCanvas
    '''
    def __init__(self, canvas):
        '''
        Creates a RectangleMapTool object
        Args:
            canvas: the QgsMapCanvas that the RectangleMapTool will be 
                    attached to
        '''
        self.canvas = canvas
        qgis.gui.QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberBand = qgis.gui.QgsRubberBand(self.canvas, True)
        self.rubberBand.setColor(PyQt5.QtGui.QColor(0,255,255,125))
        self.rubberBand.setWidth(1)
        self.reset()

    def reset(self):
        '''
        '''
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(True)

    def canvasPressEvent(self, e):
        '''
        Internal callback to be called when the user's mouse 
        presses the canvas
        Args:
            e: The press event
        '''
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint
        self.isEmittingPoint = True
        self.showRect(self.startPoint, self.endPoint)

    def canvasReleaseEvent(self, e):
        '''
        Internal callback called when the user's mouse releases 
        over the canvas
        Args:
            e: The release event
        '''
        self.isEmittingPoint = False

    def canvasMoveEvent(self, e):
        '''
        Internal callback called when the user's mouse moves 
        over the canvas
        Args:
            e: The move event
        '''
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())
        self.showRect(self.startPoint, self.endPoint)

    def showRect(self, startPoint, endPoint):
        '''
        Internal function to display the rectangle being 
        specified by the user
        '''
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return
    
        point1 = QgsPointXY(startPoint.x(), startPoint.y())
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = QgsPointXY(endPoint.x(), endPoint.y())
        point4 = QgsPointXY(endPoint.x(), startPoint.y())
    
        self.rubberBand.addPoint(point1, False)
        self.rubberBand.addPoint(point2, False)
        self.rubberBand.addPoint(point3, False)
        self.rubberBand.addPoint(point4, True)    # true to update canvas
        self.rubberBand.show()

    def rectangle(self):
        '''
        function to return the rectangle that has been selected
        '''
        if self.startPoint is None or self.endPoint is None:
            return None
        elif (self.startPoint.x() == self.endPoint.x() or \
              self.startPoint.y() == self.endPoint.y()):
            return None
    
        return QgsRectangle(self.startPoint, self.endPoint)

    def deactivate(self):
        '''
        Function to deactivate the map tool
        '''
        qgis.gui.QgsMapTool.deactivate(self)
        self.deactivated.emit()


class MapWidget(QWidget):
    '''
    Custom Widget that is used to display a map
    '''
    def __init__(self, root, isWeb):
        '''
        Creates a MapWidget
        Args:
            root: The root widget of the application
        '''
        QWidget.__init__(self)
        self.holder = QVBoxLayout()
        self.groundTruth = None
        self.mapLayer = None
        self.vehicle = None
        self.vehiclePath = None
        self.precision = None
        self.lastLoc = None
        self.pingLayer = None
        self.pingRenderer = None
        self.estimate = None
        self.toolPolygon = None
        self.polygonLayer = None
        self.polygonAction = None
        self.heatMap = None
        self.pingMin = 800
        self.pingMax = 0
        self.indPing = 0
        self.ind = 0
        self.indEst = 0
        self.toolbar = QToolBar()
        self.canvas = qgis.gui.QgsMapCanvas()
        self.canvas.setCanvasColor(PyQt5.QtCore.Qt.white)
        self.isWeb = isWeb

        self.transformToMap = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsCoordinateReferenceSystem("EPSG:3857"), 
                QgsProject.instance())
        self.transform = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:3857"), 
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance())
        
    
    def setupHeatMap(self):
        '''
        Sets up the heatMap maplayer
        Args:
        '''
        fileName = QFileDialog.getOpenFileName()
        print(fileName[0])
        if self.heatMap is not None:
            QgsProject.instance().removeMapLayer(self.heatMap)
        if fileName is not None:
            self.heatMap = QgsRasterLayer(fileName[0], "heatMap")   
            
            stats = self.heatMap.dataProvider().bandStatistics(1)
            maxVal = stats.maximumValue
            print(maxVal)
            fcn = QgsColorRampShader()
            fcn.setColorRampType(QgsColorRampShader.Interpolated)
            lst = [ QgsColorRampShader.ColorRampItem(0, PyQt5.QtGui.QColor(0,0,0)), QgsColorRampShader.ColorRampItem(maxVal, PyQt5.QtGui.QColor(255,255,255)) ]
            fcn.setColorRampItemList(lst)
            shader = QgsRasterShader()
            shader.setRasterShaderFunction(fcn)
            
            renderer = QgsSingleBandPseudoColorRenderer(self.heatMap.dataProvider(), 1, shader)
            self.heatMap.setRenderer(renderer)
            
            QgsProject.instance().addMapLayer(self.heatMap)
            destCrs = self.mapLayer.crs()
            rasterCrs = self.heatMap.crs()
            
            self.heatMap.setCrs(rasterCrs)
            self.canvas.setDestinationCrs(destCrs)
            

            self.canvas.setLayers([self.heatMap, self.estimate, self.groundTruth,
                               self.vehicle, self.pingLayer, 
                               self.vehiclePath, self.mapLayer]) 
            
            
    def plotPrecision(self, coord, freq, numPings):
        data_dir = 'holder'
        outputFileName = '/%s/PRECISION_%03.3f_%d_heatmap.tiff' % (data_dir, freq / 1e7, numPings)
        fileName = QDir().currentPath() + outputFileName
        print(fileName)
        print(outputFileName)

        
        if self.heatMap is not None:
            QgsProject.instance().removeMapLayer(self.heatMap)
        if fileName is not None:
            self.heatMap = QgsRasterLayer(fileName, "heatMap")   
            
            
            stats = self.heatMap.dataProvider().bandStatistics(1)
            maxVal = stats.maximumValue
            print(maxVal)
            fcn = QgsColorRampShader()
            fcn.setColorRampType(QgsColorRampShader.Interpolated)
            lst = [ QgsColorRampShader.ColorRampItem(0, PyQt5.QtGui.QColor(0,0,0)), QgsColorRampShader.ColorRampItem(maxVal, PyQt5.QtGui.QColor(255,255,255)) ]
            fcn.setColorRampItemList(lst)
            shader = QgsRasterShader()
            shader.setRasterShaderFunction(fcn)
            
            renderer = QgsSingleBandPseudoColorRenderer(self.heatMap.dataProvider(), 1, shader)
            self.heatMap.setRenderer(renderer)
            
            
            QgsProject.instance().addMapLayer(self.heatMap)
            destCrs = self.mapLayer.crs()
            rasterCrs = self.heatMap.crs()
            
            self.heatMap.setCrs(rasterCrs)
            self.canvas.setDestinationCrs(destCrs)
            self.heatMap.renderer().setOpacity(0.7)
            

            self.canvas.setLayers([self.heatMap, self.estimate, self.groundTruth,
                               self.vehicle, self.pingLayer, 
                               self.vehiclePath, self.mapLayer]) 

        
    def adjustCanvas(self):
        '''
        Helper function to set and adjust the camvas' layers
        '''
        self.canvas.setExtent(self.mapLayer.extent())  
        self.canvas.setLayers([self.precision, self.estimate, self.groundTruth, 
                               self.vehicle, self.pingLayer, 
                               self.vehiclePath, self.polygonLayer,
                               self.mapLayer])

        self.canvas.zoomToFullExtent()
        self.canvas.freeze(True)  
        self.canvas.show()     
        self.canvas.refresh()       
        self.canvas.freeze(False)    
        self.canvas.repaint()

    def addToolBar(self):
        '''
        Internal function to add tools to the map toolbar
        '''
        # create the map tools
        self.actionZoomIn = QAction("Zoom in", self)
        self.actionZoomIn.setCheckable(True)
        self.actionZoomIn.triggered.connect(self.zoomIn)
        self.toolbar.addAction(self.actionZoomIn)
        self.toolZoomIn = qgis.gui.QgsMapToolZoom(self.canvas, False) # false = in
        self.toolZoomIn.setAction(self.actionZoomIn)

        self.actionZoomOut = QAction("Zoom out", self)
        self.actionZoomOut.setCheckable(True)
        self.actionZoomOut.triggered.connect(self.zoomOut)
        self.toolbar.addAction(self.actionZoomOut)
        self.toolZoomOut = qgis.gui.QgsMapToolZoom(self.canvas, True) # true = out
        self.toolZoomOut.setAction(self.actionZoomOut)

        self.actionPan = QAction("Pan", self)
        self.actionPan.setCheckable(True)
        self.actionPan.triggered.connect(self.pan)
        self.toolbar.addAction(self.actionPan)
        self.toolPan = qgis.gui.QgsMapToolPan(self.canvas)
        self.toolPan.setAction(self.actionPan)

        self.polygonAction = QAction("Polygon", self)
        self.polygonAction.setCheckable(True)
        self.polygonAction.triggered.connect(self.polygon)
        self.toolbar.addAction(self.polygonAction)
        self.toolPolygon = PolygonMapTool(self.canvas)
        self.toolPolygon.setAction(self.polygonAction)

    def polygon(self):
        '''
        Helper function to set polygon tool when it is selected from 
        the toolbar
        '''
        self.canvas.setMapTool(self.toolPolygon)
        
    def zoomIn(self):
        '''
        Helper function to set the zoomIn map tool when it is selected
        '''
        self.canvas.setMapTool(self.toolZoomIn)

    def zoomOut(self):
        '''
        Helper function to set the zoomOut map tool when it is selected
        '''
        self.canvas.setMapTool(self.toolZoomOut)

    def pan(self):
        '''
        Helper function to set the pan map tool when it is selected
        '''
        self.canvas.setMapTool(self.toolPan)

    def plotVehicle(self, coord):
        '''
        Function to plot the vehicle's current location on the vehicle 
        map layer
        Args:
            coord: A tuple of float values indicating an EPSG:4326 lat/Long 
                   coordinate pair
        '''
        lat = coord[0]
        lon = coord[1]
        point = self.transformToMap.transform(QgsPointXY(lon, lat))

        if self.vehicle is None:
            return
        else:
            if self.ind > 0:
                lpr = self.vehiclePath.dataProvider()
                lin = QgsGeometry.fromPolylineXY([self.lastLoc, point])
                lineFeat = QgsFeature()
                lineFeat.setGeometry(lin)
                lpr.addFeatures([lineFeat])
                vpr = self.vehicle.dataProvider()
                self.vehicle.startEditing()
                self.vehicle.deleteFeature(self.ind)
                self.vehicle.commitChanges()
            
            self.lastLoc = point
            vpr = self.vehicle.dataProvider()
            pnt = QgsGeometry.fromPointXY(point)
            f = QgsFeature()
            f.setGeometry(pnt)
            vpr.addFeatures([f])
            self.vehicle.updateExtents()
            self.ind = self.ind + 1

    def plotPing(self, coord, power):
        '''
        Function to plot a new ping on the ping map layer
        Args:
            coord: A tuple of float values indicating an EPSG:4326 lat/Long 
                   coordinate pair
            amp: The amplitude of the ping
        '''
        lat = coord[0]
        lon = coord[1]
        
        
        change = False
        point = self.transformToMap.transform(QgsPointXY(lon, lat))
        if self.pingLayer is None:
            return

        else:
            if power < self.pingMin:
                change = True
                self.pingMin = power
            if power > self.pingMax:
                change = True
                self.pingMax = power
            if (self.pingMax == self.pingMin):
                self.pingMax = self.pingMax + 1
            if change:
                r = self.pingMax - self.pingMin
                first = r * 0.14
                second = r * 0.28
                third = r * 0.42
                fourth = r * 0.56
                fifth = r * 0.7
                sixth = r * 0.84
                
                for i, rangeObj in enumerate(self.pingRenderer.ranges()):
                    if rangeObj.label() == 'Blue':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + first)
                    if rangeObj.label() == 'Cyan':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin + first)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + second)
                    if rangeObj.label() == 'Green':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin + second)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + third)
                    if rangeObj.label() == 'Yellow':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin + third)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + fourth)
                    if rangeObj.label() == 'Orange':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin +fourth)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + fifth)
                    if rangeObj.label() == 'ORed':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin +fifth)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + sixth)
                    if rangeObj.label() == 'Red':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin + sixth)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMax)

            vpr = self.pingLayer.dataProvider()
            
            #Create new ping point
            pnt = QgsGeometry.fromPointXY(point)
            f = QgsFeature()
            f.setFields(self.pingLayer.fields())
            f.setGeometry(pnt)
            f.setAttribute(0, power)
            vpr.addFeatures([f])
            self.pingLayer.updateExtents()
            
    def plotEstimate(self, coord, frequency):
        '''
        Function to plot the current estimate point on the estimate map layer
        Args:
            coord: A tuple of float values indicating an EPSG:4326 lat/Long 
                   coordinate pair
            frequency: the frequency that this estimate corresponds to
        '''
        lat = coord[0]
        lon = coord[1]
        
        
        point = self.transformToMap.transform(QgsPointXY(lon, lat))
        if self.estimate is None:
            return
        else:
            if self.indEst > 0:
                self.estimate.startEditing()
                self.estimate.deleteFeature(self.indEst)
                self.estimate.commitChanges()
            
            vpr = self.estimate.dataProvider()
            pnt = QgsGeometry.fromPointXY(point)
            f = QgsFeature()
            f.setGeometry(pnt)
            vpr.addFeatures([f])
            self.estimate.updateExtents()
            self.indEst = self.indEst + 1
            
    def setupVehicleLayers(self, uri, uriLine):
        '''
        Sets up the vehicle and vehicle path layers
        Args:
        '''
        vehicleLayer = QgsVectorLayer(uri, 'Vehicle', "memory")
        vehiclePathlayer = QgsVectorLayer(uriLine, 'VehiclePath', "memory")
        
        # Set drone image for marker symbol
        path = PyQt5.QtCore.QDir().filePath('../resources/vehicleSymbol.svg')
        symbolSVG = QgsSvgMarkerSymbolLayer(path)
        symbolSVG.setSize(4)
        symbolSVG.setFillColor(PyQt5.QtGui.QColor('#0000ff'))
        symbolSVG.setStrokeColor(PyQt5.QtGui.QColor('#ff0000'))
        symbolSVG.setStrokeWidth(1)
        vehicleLayer.renderer().symbol().changeSymbolLayer(0, symbolSVG)
        
        #set autorefresh
        vehicleLayer.setAutoRefreshInterval(500)
        vehicleLayer.setAutoRefreshEnabled(True)
        vehiclePathlayer.setAutoRefreshInterval(500)
        vehiclePathlayer.setAutoRefreshEnabled(True)
        return vehicleLayer, vehiclePathlayer


    def setupPingLayer(self, uri):
        '''
        Sets up the ping layer and renderer.
        Args:
        '''
        ranges = []
        
        layer = QgsVectorLayer(uri, 'Pings', 'memory')
        
        
        # make symbols
        symbolBlue = QgsSymbol.defaultSymbol(layer.geometryType())
        symbolBlue.setColor(PyQt5.QtGui.QColor('#0000FF'))
        symbolCyan = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolCyan.setColor(PyQt5.QtGui.QColor('#00FFFF'))
        symbolGreen = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolGreen.setColor(PyQt5.QtGui.QColor('#00FF00'))
        symbolYellow = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolYellow.setColor(PyQt5.QtGui.QColor('#FFFF00'))
        symbolOrange = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolOrange.setColor(PyQt5.QtGui.QColor('#FFC400'))
        symbolORed = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolORed.setColor(PyQt5.QtGui.QColor('#FFA000'))
        symbolRed = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolRed.setColor(PyQt5.QtGui.QColor('#FF0000'))
    
        # make ranges
        rBlue = QgsRendererRange(0, 10, symbolBlue, 'Blue')
        rCyan = QgsRendererRange(10, 20, symbolCyan, 'Cyan')
        rGreen = QgsRendererRange(20, 40, symbolGreen, 'Green')
        rYellow = QgsRendererRange(40, 60, symbolYellow, 'Yellow')
        rOrange = QgsRendererRange(60, 80, symbolOrange, 'Orange')
        rORed = QgsRendererRange(80, 90, symbolORed, 'ORed')
        rRed = QgsRendererRange(90, 100, symbolRed, 'Red')
        ranges.append(rBlue)
        ranges.append(rCyan)
        ranges.append(rGreen)
        ranges.append(rYellow)
        ranges.append(rOrange)
        ranges.append(rORed)
        ranges.append(rRed)

        # set renderer to set symbol based on amplitude
        pingRenderer = QgsGraduatedSymbolRenderer('Amp', ranges)

        style = QgsStyle().defaultStyle()
        defaultColorRampNames = style.colorRampNames()
        ramp = style.colorRamp(defaultColorRampNames[22])
        pingRenderer.setSourceColorRamp(ramp)
        pingRenderer.setSourceSymbol( QgsSymbol.defaultSymbol(layer.geometryType()))
        pingRenderer.sortByValue()
        
        
        vpr = layer.dataProvider()
        vpr.addAttributes([QgsField(name='Amp', type=PyQt5.QtCore.PyQt5.QtCore.QVariant.Double, len=30)])
        layer.updateFields()
    
        # set the renderer and allow the mapLayer to auto refresh
        layer.setRenderer(pingRenderer)
        layer.setAutoRefreshInterval(500)
        layer.setAutoRefreshEnabled(True)
        
        return layer, pingRenderer
    
    def setupEstimate(self, uri):
        '''
        Sets up the Estimate mapLayer
        Args:
        '''
        layer = QgsVectorLayer(uri, 'Estimate', "memory")
        symbol = QgsMarkerSymbol.createSimple({'name':'diamond', 
                'color':'blue'})
        layer.renderer().setSymbol(symbol)
        layer.setAutoRefreshInterval(500)
        layer.setAutoRefreshEnabled(True)
        
        return layer

        
class MapOptions(QWidget):
    '''
    Custom Widget facilitate map caching and exporting map layers
    '''
    def __init__(self):
        '''
        Creates a MapOptions widget
        '''
        QWidget.__init__(self)

        self.mapWidget = None
        self.btn_cacheMap = None
        self.isWebMap = False
        self.__createWidgets()
        self.created = False
        self.writer = None
        self.hasPoint = False
        


    def __createWidgets(self):
        '''
        Inner function to create internal widgets
        '''
        # MAP OPTIONS
        lay_mapOptions = QVBoxLayout()

        lbl_mapOptions = QLabel('Map Options')
        lay_mapOptions.addWidget(lbl_mapOptions)

        self.btn_setSearchArea = QPushButton('Set Search Area')
        self.btn_setSearchArea.setEnabled(False)
        lay_mapOptions.addWidget(self.btn_setSearchArea)

        self.btn_cacheMap = QPushButton('Cache Map')
        self.btn_cacheMap.clicked.connect(lambda:self.__cacheMap())
        self.btn_cacheMap.setEnabled(False)
        lay_mapOptions.addWidget(self.btn_cacheMap)

        self.btn_clearMap = QPushButton('Clear Map');
        self.btn_clearMap.clicked.connect(self.clear)
        self.btn_clearMap.setEnabled(False)
        lay_mapOptions.addWidget(self.btn_clearMap)

        
        exportTab = CollapseFrame('Export')
        btn_pingExport = QPushButton('Pings')
        btn_pingExport.clicked.connect(lambda:self.exportPing())
        btn_vehiclePathExport = QPushButton('Vehicle Path')
        btn_vehiclePathExport.clicked.connect(lambda:self.exportVehiclePath())

        btn_polygonExport = QPushButton('Polygon')
        btn_polygonExport.clicked.connect(lambda:self.exportPolygon())
        
        lay_export = QVBoxLayout()
        lay_export.addWidget(btn_pingExport)
        lay_export.addWidget(btn_vehiclePathExport)
        lay_export.addWidget(btn_polygonExport)
        exportTab.setContentLayout(lay_export)
        
        lay_mapOptions.addWidget(exportTab)    
        
        
        

        self.setLayout(lay_mapOptions)

    def clear(self):
        '''
        Helper function to clear selected map areas 
        '''
        self.mapWidget.toolPolygon.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        self.mapWidget.toolRect.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        self.mapWidget.toolPolygon.vertices.clear()

    def __cacheMap(self):
        '''
        Inner function to facilitate map caching
        '''
        if self.isWebMap:
            if (self.mapWidget.toolRect.rectangle() == None):
                msg = QMessageBox()
                msg.setText("No specified area to cache!")
                msg.setWindowTitle("Alert")
                msg.setInformativeText("Use the rect tool to choose an area on the map to cache")
                msg.setIcon(QMessageBox.Critical)
                msg.exec_()
                self.mapWidget.rect()
            else:
                cacheThread = Thread(target=self.mapWidget.cacheMap)
                cacheThread.start()
                self.mapWidget.canvas.refresh()
        else:
            print("alert")

    def setMap(self, mapWidg: MapWidget, isWebMap):
        '''
        Function to set the MapWidget that this object will use
        Args:
            mapWidg: A MapWidget object
            isWebMap: A boolean indicating whether or not the mapWidget 
                      is a WebMap
        '''
        self.isWebMap = isWebMap
        self.mapWidget = mapWidg
        self.addLegend()
        
        self.btn_cacheMap.setEnabled(isWebMap)
        self.btn_clearMap.setEnabled(isWebMap)
        
    def addLegend(self):
        '''
        Function to add Map Legend widget when map is loaded
        '''
        mapLegend = MapLegend()
        self.layout().addWidget(mapLegend)

    def estDistance(self, coord, stale, res):

        lat1 = coord[0]
        lon1 = coord[1]
        lat2 = 32.885889
        lon2 = -117.234028
        
        if not self.hasPoint:
            point = self.mapWidget.transformToWeb.transform(QgsPointXY(lon2, lat2))
            vpr = self.mapWidget.groundTruth.dataProvider()
            pnt = QgsGeometry.fromPointXY(point)
            f = QgsFeature()
            f.setGeometry(pnt)
            vpr.addFeatures([f])
            self.mapWidget.groundTruth.updateExtents()
            self.hasPoint = True

        
        dist = self.distance(lat1, lat2, lon1, lon2)
        
        if not self.created:
            with open('results.csv', 'w', newline='') as csvfile:
                fieldnames = ['Distance', 'res.x', 'residuals']
                self.writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                self.writer.writeheader()
                self.created = True
                self.writer.writerow({'Distance': str(dist), 'res.x': str(res.x), 'residuals': str(res.fun)})
        else:
            with open('results.csv', 'a+', newline='') as csvfile:
                fieldnames = ['Distance', 'res.x', 'residuals']
                self.writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                self.writer.writerow({'Distance': str(dist), 'res.x': str(res.x), 'residuals': str(res.fun)})
                
       
        
        d = '%.3f'%(dist)

        self.lbl_dist.setText(d + '(m.)')
        
    def distance(self, lat1, lat2, lon1, lon2): 
        '''
        Helper function to calculate distance. For testing only
        Args:
            lat1: float value indicating the lat value of a point
            lat2: float value indicating the lat value of a second point
            lon1: float value indicating the long value of a point
            lon2: float value indicating the long value of a second point
        '''
        lon1 = math.radians(lon1) 
        lon2 = math.radians(lon2) 
        lat1 = math.radians(lat1) 
        lat2 = math.radians(lat2) 
           
        # Haversine formula  
        dlon = lon2 - lon1  
        dlat = lat2 - lat1 
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
      
        c = 2 * math.asin(math.sqrt(a))  
         
        # Radius of earth in kilometers. Use 3956 for miles 
        r = 6371
           
        return(c * r * 1000)

        
    
    def exportPing(self):
        '''
        Method to export a MapWidget's pingLayer to a shapefile
        '''
        folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        file = folder + '/pings.shp'
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"

        QgsVectorFileWriter.writeAsVectorFormatV2(self.mapWidget.pingLayer, 
                                        file, 
                                        QgsCoordinateTransformContext(), options)
        
    def exportVehiclePath(self):
        '''
        Method to export a MapWidget's vehiclePath to a shapefile
        '''
        folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        file = folder + '/vehiclePath.shp'
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"

        QgsVectorFileWriter.writeAsVectorFormatV2(self.mapWidget.vehiclePath, 
                                        file, 
                                        QgsCoordinateTransformContext(), options)

    def exportPolygon(self):
        '''
        Method to export MapWidget's Polygon shape to a shapefile
        '''
        vpr = self.mapWidget.polygonLayer.dataProvider()
        self.generateWaypoints()
        if self.mapWidget.toolPolygon is None:
            return
        elif len(self.mapWidget.toolPolygon.vertices) == 0:
            return
        else:
            
            pts = self.mapWidget.toolPolygon.vertices
            print(type(pts[0]))
            polyGeom = QgsGeometry.fromPolygonXY([pts])
            
            feature = QgsFeature()
            feature.setGeometry(polyGeom)
            vpr.addFeatures([feature])
            self.mapWidget.polygonLayer.updateExtents()


            folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
            file = folder + '/polygon.shp'
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "ESRI Shapefile"
            
            QgsVectorFileWriter.writeAsVectorFormatV2(self.mapWidget.polygonLayer, file, 
                                                    QgsCoordinateTransformContext(), options)
            
            
            
    def generateWaypoints(self):
        '''
        Method to retrieve waypoints based on polygon vertices
        '''
        width = 30
        path = []
        points = self.mapWidget.toolPolygon.vertices
        newPoints = []
        for point in points:
            toAdd = self.mapWidget.transform.transform(point)
            easting, northing, num, zone = utm.from_latlon(toAdd[1], toAdd[0])
            newPoint = QgsPointXY(easting, northing)
            newPoints.append(newPoint)
        
        polyGeom = QgsGeometry.fromPolygonXY([newPoints])
        
        points = np.array(newPoints)
        maxX = points[:,0].max()
        minX = points[:,0].min()
        maxY = points[:,1].max()
        minY = points[:,1].min()
        
        yRange = maxY-minY
        
        numRows = math.floor(yRange/width)
        
        topTwoInd = np.argsort(points[:,1], axis=0)[-2:][::-1]
        topTwo = points[topTwoInd]
        topTwo = topTwo[np.argsort(topTwo[:,0], axis=0)]
        path.append(topTwo[0])
        path.append(topTwo[1])
        
        splitLines = []
        
        for i in range(numRows):
            newY = minY + (i*width)
            if(i > 0):
                if((i%2)==0):
                    splitLines.append(QgsPointXY(minX-1, newY))
                    splitLines.append(QgsPointXY(maxX+1, newY))
                else:
                    splitLines.append(QgsPointXY(maxX+1, newY))
                    splitLines.append(QgsPointXY(minX-1, newY))
        
        
        x = 0
        added = 0
        while(x < len(splitLines)):
            ind = x
            split = QgsGeometry.fromPolylineXY([splitLines[ind], splitLines[ind+1]]).intersection(polyGeom).asPolyline()
            if(len(path) > 1):
                added = added + 1
                path.append(split[0])
                path.append(split[1])
            x = x + 2
                
                
        botTwoInd = np.argsort(points[:,1], axis=0)[2:]
        botTwo = points[botTwoInd]
        botTwo = botTwo[np.argsort(topTwo[:,0], axis=0)]
        
        if((added%2)==0):
            path.append(botTwo[0])
            path.append(botTwo[1])
        else:
            path.append(botTwo[1])
            path.append(botTwo[0])
            
                
        print(path)
            
           



class WebMap(MapWidget):
    '''
    Custom MapWidget to facilititate displaying online or offline 
    web maps
    '''
    def __init__(self, root, p1lat, p1lon, p2lat, p2lon, loadCached):
        '''
        Creates a WebMap widget
        Args:
            root: the root widget of the Application
            p1lat: float lat value
            p1lon: float lon value
            p2lat: float lat value
            p2lon: float lon value
            loadCached: boolean value to indicate tile source
        '''
        # Initialize WebMapFrame
        MapWidget.__init__(self, root, True)

        self.loadCached = loadCached

        
        self.addLayers()
           
        self.adjustCanvas()
        r = QgsRectangle(p1lon, p2lat, p2lon, p1lat)
        rect = self.transformToMap.transformBoundingBox(r)
        self.canvas.zoomToFeatureExtent(rect)

        self.addToolBar()
        self.addRectTool()
        self.pan()

        self.holder.addWidget(self.toolbar)
        self.holder.addWidget(self.canvas)
        self.setLayout(self.holder)

        root.addWidget(self, 0, 1, 1, 2)
        self.root = root

    
    def setupGroundTruth(self):
        '''
        Sets up the groundTruth maplayer
        Args:
        '''
        uri = "Point?crs=epsg:3857"
        layer = QgsVectorLayer(uri, 'Estimate', "memory")
        symbol = QgsMarkerSymbol.createSimple({'name':'square', 
                'color':'cyan'})
        layer.renderer().setSymbol(symbol)
        
        return layer

   


    def setupPingLayer(self):
        '''
        Sets up the ping layer and renderer.
        Args:
        '''
        ranges = []
        uri = "Point?crs=epsg:3857"
        layer = QgsVectorLayer(uri, 'Pings', 'memory')
        
        
        # make symbols
        symbolBlue = QgsSymbol.defaultSymbol(layer.geometryType())
        symbolBlue.setColor(PyQt5.QtGui.QColor('#0000FF'))
        symbolCyan = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolCyan.setColor(PyQt5.QtGui.QColor('#00FFFF'))
        symbolGreen = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolGreen.setColor(PyQt5.QtGui.QColor('#00FF00'))
        symbolYellow = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolYellow.setColor(PyQt5.QtGui.QColor('#FFFF00'))
        symbolOrange = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolOrange.setColor(PyQt5.QtGui.QColor('#FFC400'))
        symbolORed = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolORed.setColor(PyQt5.QtGui.QColor('#FFA000'))
        symbolRed = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolRed.setColor(PyQt5.QtGui.QColor('#FF0000'))
    
        # make ranges
        rBlue = QgsRendererRange(0, 10, symbolBlue, 'Blue')
        rCyan = QgsRendererRange(10, 20, symbolCyan, 'Cyan')
        rGreen = QgsRendererRange(20, 40, symbolGreen, 'Green')
        rYellow = QgsRendererRange(40, 60, symbolYellow, 'Yellow')
        rOrange = QgsRendererRange(60, 80, symbolOrange, 'Orange')
        rORed = QgsRendererRange(80, 90, symbolORed, 'ORed')
        rRed = QgsRendererRange(90, 100, symbolRed, 'Red')
        ranges.append(rBlue)
        ranges.append(rCyan)
        ranges.append(rGreen)
        ranges.append(rYellow)
        ranges.append(rOrange)
        ranges.append(rORed)
        ranges.append(rRed)

        # set renderer to set symbol based on amplitude
        pingRenderer = QgsGraduatedSymbolRenderer('Amp', ranges)
        
        
        style = QgsStyle().defaultStyle()
        defaultColorRampNames = style.colorRampNames()
        ramp = style.colorRamp(defaultColorRampNames[22])
        pingRenderer.setSourceColorRamp(ramp)
        pingRenderer.setSourceSymbol( QgsSymbol.defaultSymbol(layer.geometryType()))
        pingRenderer.sortByValue()
        
        
        vpr = layer.dataProvider()
        vpr.addAttributes([QgsField(name='Amp', type=PyQt5.QtCore.QVariant.Double, len=30)])
        layer.updateFields()
    
        # set the renderer and allow the mapLayer to auto refresh
        layer.setRenderer(pingRenderer)
        layer.setAutoRefreshInterval(500)
        layer.setAutoRefreshEnabled(True)
        
        return layer, pingRenderer
    
    def setupPrecisionLayer(self):
        path = QDir().currentPath()
        uri = 'file:///' + path + '/holder/query.csv?encoding=%s&delimiter=%s&xField=%s&yField=%s&crs=%s&value=%s' % ("UTF-8",",", "easting", "northing","epsg:32611", "value")
        
        csv_layer= QgsVectorLayer(uri, "query", "delimitedtext")
        
        csv_layer.setOpacity(0.5)
        
        heatmap = QgsHeatmapRenderer()
        heatmap.setWeightExpression('value')
        heatmap.setRadiusUnit(QgsUnitTypes.RenderUnit.RenderMetersInMapUnits)
        heatmap.setRadius(3)
        csv_layer.setRenderer(heatmap)
        
        csv_layer.setAutoRefreshInterval(500)
        csv_layer.setAutoRefreshEnabled(True)
        
        return csv_layer

    def setUpPolygonLayer(self):
        uri = "Polygon?crs=epsg:3857"
        polygonPointLayer = QgsVectorLayer(uri, 'Polygon', "memory")
        return polygonPointLayer

    def addLayers(self):
        '''
        Helper method to add map layers to map canvas
        '''
        uri = "Point?crs=epsg:3857"
        if self.estimate is None:
            self.estimate = self.setupEstimate(uri)
            
            
        if self.vehicle is None:
            vPathURI = "Linestring?crs=epsg:3857"
            self.vehicle, self.vehiclePath = self.setupVehicleLayers(uri, vPathURI)
            
        if self.pingLayer is None:
            self.pingLayer, self.pingRenderer = self.setupPingLayer()
            
        if self.groundTruth is None:
            self.groundTruth = self.setupGroundTruth()
            
        
        
        if self.polygonLayer is None:
            self.polygonLayer = self.setUpPolygonLayer()
            
        #load from cached tiles if true, otherwise loads from web    
        if self.loadCached:
            dirs = AppDirs("GCS", "E4E")
            path = dirs.site_data_dir.replace("\\", "/")
            urlWithParams = 'type=xyz&url=file:///'+ path+'/tiles/%7Bz%7D/%7Bx%7D/%7By%7D.png'
        else:
            urlWithParams = 'type=xyz&url=http://a.tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0&crs=EPSG3857'    
        self.mapLayer = QgsRasterLayer(urlWithParams, 'OpenStreetMap', 'wms') 
        '''
        if self.precision is None:
            self.precision = self.setupPrecisionLayer()
            destCrs = self.mapLayer.crs()
            rasterCrs = self.precision.crs()
            self.precision.setCrs(rasterCrs)
            self.canvas.setDestinationCrs(destCrs)
        ''' 
        if self.mapLayer.isValid():   
            crs = self.mapLayer.crs()
            crs.createFromString("EPSG:3857")  
            self.mapLayer.setCrs(crs)
            
            #add all layers to map
            QgsProject.instance().addMapLayer(self.mapLayer)
            QgsProject.instance().addMapLayer(self.groundTruth)
            QgsProject.instance().addMapLayer(self.estimate)
            QgsProject.instance().addMapLayer(self.vehicle)
            QgsProject.instance().addMapLayer(self.vehiclePath)
            QgsProject.instance().addMapLayer(self.pingLayer)
            #QgsProject.instance().addMapLayer(self.precision)
            print('valid mapLayer')
        else:
            print('invalid mapLayer')
            raise RuntimeError



    def addRectTool(self):
        '''
        Helper function to add the rectangle tool to the toolbar
        '''
        self.rectAction = QAction("Rect", self)
        self.rectAction.setCheckable(True)
        self.rectAction.triggered.connect(self.rect)
        self.toolbar.addAction(self.rectAction)
        self.toolRect = RectangleMapTool(self.canvas)
        self.toolRect.setAction(self.rectAction)

    def rect(self):
        '''
        Helper function to set rect tool when it is selected from 
        the toolbar
        '''
        self.canvas.setMapTool(self.toolRect)

    def deg2num(self, lat_deg, lon_deg, zoom):
        '''
        Helper function to calculate the map tile number for a given 
        location
        Args:
            lat_deg: float latitude value
            lon_deg: float longitude value
            zoom: integer zoom value
        '''
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        x = int((lon_deg + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x,y)
        

    def cacheMap(self):
        '''
        Function to facilitate caching map tiles
        '''
        if (self.toolRect.rectangle() == None):
            return
        else:
            rect = self.toolRect.rectangle()
            r = self.transform.transformBoundingBox(self.toolRect.rectangle(), 
                                QgsCoordinateTransform.ForwardTransform, True)
            print("Rectangle:", r.xMinimum(),
                    r.yMinimum(), r.xMaximum(), r.yMaximum()
                 )
            '''
            if (r != None):
                zoomStart = 17
                tilecount = 0
                for zoom in range(zoomStart, 19, 1):
                    xmin, ymin = self.deg2num(float(r.yMinimum()),float(r.xMinimum()),zoom)
                    xmax, ymax = self.deg2num(float(r.yMaximum()),float(r.xMaximum()),zoom)
                    print("Zoom:", zoom)
                    print(xmin, xmax, ymin, ymax)
                    for x in range(xmin, xmax+1, 1):
                        for y in range(ymax, ymin+1, 1):
                            if (tilecount < 200):
                                time.sleep(1)
                                downloaded = self.downloadTile(x,y,zoom)
                                if downloaded:
                                    tilecount = tilecount + 1
                            else:
                                print("tile count exceeded, pls try again in a few minutes")
                                return
                print("Download Complete")
            else:
                print("Download Failed")
            '''
            
    def downloadTile(self, xtile, ytile, zoom):
        '''
        Helper Function to facilitate the downloading of web tiles
        '''
        url = "http://c.tile.openstreetmap.org/%d/%d/%d.png" % (zoom, xtile, ytile)
        dirs = AppDirs("GCS", "E4E")
        cachePath = dirs.site_data_dir.replace('\\', '/')
         
        tilePath = '/tiles/%d/%d/' % (zoom, xtile)
        dir_path = cachePath + tilePath
        download_path = cachePath +"/tiles/%d/%d/%d.png" % (zoom, xtile, ytile)
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        
        if(not os.path.isfile(download_path)):
            print("downloading %r" % url)
            source = requests.get(url, headers = {'User-agent': 'Mozilla/5.0'})
            cont = source.content
            source.close()
            destination = open(download_path,'wb')
            destination.write(cont)
            destination.close()
            return True
        else: 
            print("skipped %r" % url)
            return False

        return True


class StaticMap(MapWidget):
    '''
    Custom MapWidget to facilititate displaying a static raster file
    '''
    def __init__(self, root):
        '''
        Creates a StaticMap object
        Args:
            root: the root widget of the application
        '''
        MapWidget.__init__(self, root, False)

        self.fileName = None

        self.__getFileName()
        self.__addLayers()

        self.adjustCanvas()
        self.addToolBar()
        self.pan()

        self.holder.addWidget(self.toolbar)
        self.holder.addWidget(self.canvas)
        self.setLayout(self.holder)

        root.addWidget(self, 0, 1, 1, 2)
        self.root = root


    def __getFileName(self):
        '''
        inner function to retrieve a user specified raster file
        '''
        self.fileName = QFileDialog.getOpenFileName()      

    def __addLayers(self):
        '''
        Helper funciton to add layers to the map canvas
        '''
        uri = "Point?crs=epsg:4326"
        uriLine = "Linestring?crs=epsg:4326"
        
        if(self.fileName == None):
            return
        
        if self.estimate is None:
            self.estimate = self.setupEstimate(uri)
            
        if self.vehicle is None:
            self.vehicle, self.vehiclePath = self.setupVehicleLayers(uri, uriLine)
            
        if self.pingLayer is None:
            self.pingLayer, self.pingRenderer = self.setupPingLayer(uri)

        self.mapLayer = QgsRasterLayer(self.fileName[0], "SRTM layer name")
        print(self.mapLayer.crs())
        crs = self.mapLayer.crs()
        
        self.transformToMap = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:4326"),
                crs, 
                QgsProject.instance())
        self.transform = QgsCoordinateTransform(
                crs, 
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance())



        
        if self.mapLayer.isValid():   
            QgsProject.instance().addMapLayer(self.mapLayer)
            QgsProject.instance().addMapLayer(self.estimate)
            QgsProject.instance().addMapLayer(self.vehicle)
            QgsProject.instance().addMapLayer(self.vehiclePath)
            QgsProject.instance().addMapLayer(self.pingLayer)
            print('valid layer')
        else:
            print('invalid layer')
            
    

class MapLegend(QWidget):
    '''
    Custom widget to display map legend
    '''
    def __init__(self):
            QWidget.__init__(self)

            self.__createWidget()

    def __createWidget(self):
        '''
        Helper function that creates layout of legend
        '''

        self.__layMapLegend = QGridLayout()
        self.setLayout(self.__layMapLegend)
        self.__layMapLegend.setSpacing(10)

        #Creating the labels for legend
        lbl_vehicleSymb = QLabel('Vehicle Location', self)
        lbl_vehicleTravel = QLabel('Vehicle Path', self)
        lbl_symbolBlue = QLabel('Weakest', self)
        lbl_symbolGreen = QLabel('Weak', self)
        lbl_symbolYellow = QLabel('Neutral', self)
        lbl_symbolOrange = QLabel('Strong', self)
        lbl_symbolRed = QLabel('Strongest', self)
        lbl_estimatePoint = QLabel('Estimated point', self)


        #Adds vehicle locations icon
        img_vehicleSymb = QSvgWidget('../resources/vehicleSymbol.svg', self)
        img_vehicleSymb.load('../resources/vehicleSymbol.svg')
        img_vehicleSymb.setFixedWidth(50)
        img_vehicleSymb.setFixedHeight(50)

        #Adding weakest ping
        img_symbolBlue = QSvgWidget('../resources/symbBlue.svg', self)
        img_symbolBlue.load('../resources/symbBlue.svg')
        img_symbolBlue.setFixedWidth(50)
        img_symbolBlue.setFixedHeight(50)

        #Adding weak ping
        img_symbolGreen = QSvgWidget('../resources/symbGreen.svg', self)
        img_symbolGreen.load('../resources/symbGreen.svg')
        img_symbolGreen.setFixedWidth(50)
        img_symbolGreen.setFixedHeight(50)

        #Adding Neutral ping
        img_symbolYellow = QSvgWidget('../resources/symbYellow.svg', self)
        img_symbolYellow.load('../resources/symbYellow.svg')
        img_symbolYellow.setFixedWidth(50)
        img_symbolYellow.setFixedHeight(50)

        #Adding Strong ping
        img_symbolOrange = QSvgWidget('../resources/symbOrange.svg', self)
        img_symbolOrange.load('../resources/symbOrange.svg')
        img_symbolOrange.setFixedWidth(50)
        img_symbolOrange.setFixedHeight(50)           

        #Adding Strongest ping
        img_symbolRed = QSvgWidget('../resources/symbRed.svg', self)
        img_symbolRed.load('../resources/symbRed.svg')
        img_symbolRed.setFixedWidth(50)
        img_symbolRed.setFixedHeight(50)

        #Adding Estimated Point
        img_symbolEstPoint = QSvgWidget('../resources/symbEstPoint.svg', self)
        img_symbolEstPoint.load('../resources/symbEstPoint.svg')
        img_symbolEstPoint.setFixedWidth(50)
        img_symbolEstPoint.setFixedHeight(50)

        #Adding Vehicle Path
        img_symbolVPath = QSvgWidget('../resources/symbVehiclePath.svg', self)
        img_symbolVPath.load('../resources/symbVehiclePath.svg')
        img_symbolVPath.setFixedWidth(50)
        img_symbolVPath.setFixedHeight(50)


        #Adding Labels to the layout
        self.__layMapLegend.addWidget(lbl_estimatePoint, 1, 1)
        self.__layMapLegend.addWidget(lbl_vehicleSymb, 2, 1)
        self.__layMapLegend.addWidget(lbl_vehicleTravel, 3, 1)
        self.__layMapLegend.addWidget(lbl_symbolBlue, 4, 1)
        self.__layMapLegend.addWidget(lbl_symbolGreen, 5, 1)
        self.__layMapLegend.addWidget(lbl_symbolYellow, 6, 1)
        self.__layMapLegend.addWidget(lbl_symbolOrange, 7, 1)
        self.__layMapLegend.addWidget(lbl_symbolRed, 8, 1)

        #Adding label images to the layout
        self.__layMapLegend.addWidget(img_symbolEstPoint, 1, 2)
        self.__layMapLegend.addWidget(img_vehicleSymb,2,2)
        self.__layMapLegend.addWidget(img_symbolVPath,3,2)
        self.__layMapLegend.addWidget(img_symbolBlue,4,2)
        self.__layMapLegend.addWidget(img_symbolGreen,5,2)
        self.__layMapLegend.addWidget(img_symbolYellow,6,2)
        self.__layMapLegend.addWidget(img_symbolOrange, 7, 2)
        self.__layMapLegend.addWidget(img_symbolRed,8,2)

def configSetup():
    '''
    Helper function to set up paths to QGIS lbrary files, and 
    config file
    '''
    config_path = 'gcsConfig.ini'
    if(not os.path.isfile(config_path)):
        prefix_path = QFileDialog.getExistingDirectory(None, 'Select the Qgis directory')          
        config = configparser.ConfigParser()
        config['FilePaths'] = {}
        config['FilePaths']['PrefixPath'] = prefix_path
        if ("qgis" not in prefix_path):
            msg = QMessageBox()
            msg.setText("Warning, incorrect file chosen. Map tools may not function as expected")
            msg.setWindowTitle("Alert")
            msg.setIcon(QMessageBox.Critical)
            msg.exec_()
        with open(config_path, 'w') as configFile:
            config.write(configFile)
            return config, prefix_path
    else:
        config = configparser.ConfigParser()
        config.read(config_path)
        prefix_path = config['FilePaths']['PrefixPath']
        return config, prefix_path

   


if __name__ == '__main__':
    logName = dt.datetime.now().strftime('%Y.%m.%d.%H.%M.%S_gcs.log')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d: %(levelname)s:%(name)s: %(message)s', 
        datefmt='%Y-%M-%d %H:%m:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ch = logging.FileHandler(logName)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
  
    app = QgsApplication([], True)
    
    configObj, prefix_path = configSetup()
    
    QgsApplication.setPrefixPath(prefix_path)

    app.initQgis()

    ex = GCS(configObj)
    ex.show()

    exitcode = app.exec_()
    app.exitQgis()
    sys.exit(exitcode)
