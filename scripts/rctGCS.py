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
# 07/09/20  ML  Refactored Map Classes to extend added MapWidget Class
# 07/09/20  ML  Converted Static Maps and WebMaps to QGIS
# 06/30/20  ML  Translated tkinter GUI into PyQt5
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
import math
import time
import logging
import sys
from sys import argv
import os
import os.path
import requests
import rctTransport
import rctComms
import rctCore
from PyQt5.QtCore import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import QtNetwork
import qgis
from qgis.core import *    
from qgis.gui import *  
from qgis.utils import *
from qgis.core import QgsProject
from threading import Thread

class GCS(QMainWindow):
    '''
    Ground Control Station GUI
    '''

    SBWidth = 500

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
        self.systemSettingWidget = None
        #self.__missionStatusText = StringVar()
        #self.__missionStatusText.set("Start Recording")
        self.__missionStatusText = "Start Recording"
        self.innerFreqFrame = None
        self.freqElements = []
        self.targEntries = {}
        self.mapControl = None
        self.mapOptions = None
        self.testFrame = None
        self.__createWidgets()
        for button in self._buttons:
            button.config(state='disabled')
        #self.protocol('WM_DELETE_WINDOW', self.__windowClose)

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
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Critical)
        dialog.setText("No Heartbeats Received")
        dialog.addButton(QMessageBox.Ok)
        dialog.exec()

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
        '''
        if self.__missionStatusText.get() == 'Start Recording':
            self.__missionStatusText.set('Stop Recording')
            self._mavModel.startMission(timeout=self.defaultTimeout)
        else:
            self.__missionStatusText.set('Start Recording')
            self._mavModel.stopMission(timeout=self.defaultTimeout)
        '''
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


    def closeEvent(self, event):
        '''
        Internal callback for window close
        '''
        if self._mavModel is not None:
            self._mavModel.stop()
        super().closeEvent(event)
            
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
        connectionDialog.exec_()


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

        #def submit():


    def __createWidgets(self):
        '''
        Internal helper to make GUI widgets
        '''
        

        holder = QGridLayout()
        centr_widget = QFrame()
        self.setCentralWidget(centr_widget)

        self.setWindowTitle('RCT GCS')
        frm_sideControl = QScrollArea()
        frm_sideControl.resize(self.SBWidth, 400)

        content = QWidget()
        content.resize(self.SBWidth, 400)
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
        frm_components = CollapseFrame('Components')

        lay_comp = QVBoxLayout()
        lbl_componentNotif = QLabel('Vehicle not connected')
        lay_comp.addWidget(lbl_componentNotif)
        frm_components.setContentLayout(lay_comp)

        # DATA DISPLAY TOOLS
        self.mapOptions = MapOptions(holder)
        self.mapOptions.resize(300, 100)
        self.mapControl = MapControl(frm_sideControl, holder, 
                self.mapOptions, self)

        # SYSTEM SETTINGS
        self.systemSettingsWidget = SystemSettingsControl(self)
        scrollArea = QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setWidget(self.systemSettingsWidget)



        # START PAYLOAD RECORDING
        btn_startRecord = QPushButton(self.__missionStatusText)
        #                            textvariable=self.__missionStatusText, 
        btn_startRecord.clicked.connect(lambda:self.__startStopMission())

        wlay.addWidget(self._systemConnectionTab)
        wlay.addWidget(frm_components)
        wlay.addWidget(self.mapControl)
        wlay.addWidget(self.systemSettingsWidget)
        wlay.addWidget(btn_startRecord)
        wlay.addStretch()
        holder.addWidget(content, 0, 0, alignment=Qt.AlignLeft)
        holder.addWidget(self.mapOptions, 0, 4, alignment=Qt.AlignTop)
        centr_widget.setLayout(holder)
        self.resize(1800, 1100)
        self.show()

class CollapseFrame(QWidget):
    def __init__(self, title="", parent=None):
        super(CollapseFrame, self).__init__(parent)

        self.toggle_button = QToolButton(
            text=title, checkable=True, checked=False
        )
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(Qt.RightArrow)
        self.toggle_button.pressed.connect(self.on_pressed)

        self.toggle_animation = QParallelAnimationGroup(self)

        self.content_area = QScrollArea(
            maximumHeight=0, minimumHeight=0
        )
        self.content_area.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self.content_area.setFrameShape(QFrame.NoFrame)

        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.toggle_animation.addAnimation(
            QPropertyAnimation(self, b"minimumHeight")
        )
        self.toggle_animation.addAnimation(
            QPropertyAnimation(self, b"maximumHeight")
        )
        self.toggle_animation.addAnimation(
            QPropertyAnimation(self.content_area, b"maximumHeight")
        )

    def updateText(self, text):
        self.toggle_button.setText(text)

    @pyqtSlot()
    def on_pressed(self):
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(
            Qt.DownArrow if not checked else Qt.RightArrow
        )
        self.toggle_animation.setDirection(
            QAbstractAnimation.Forward
            if not checked
            else QAbstractAnimation.Backward
        )
        self.toggle_animation.start()

    def setContentLayout(self, layout):
        lay = self.content_area.layout()
        del lay
        self.content_area.setLayout(layout)
        collapsed_height = (
            self.sizeHint().height() - self.content_area.maximumHeight()
        )
        content_height = layout.sizeHint().height()
        for i in range(self.toggle_animation.animationCount()):
            animation = self.toggle_animation.animationAt(i)
            animation.setDuration(500)
            animation.setStartValue(collapsed_height)
            animation.setEndValue(collapsed_height + content_height)

        content_animation = self.toggle_animation.animationAt(
            self.toggle_animation.animationCount() - 1
        )
        content_animation.setDuration(500)
        content_animation.setStartValue(0)
        content_animation.setEndValue(content_height)

class SystemSettingsControl(CollapseFrame):
    def __init__(self, root):
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
        self.__updateWidget() #add updated values

        # Repaint widgets and layouts
        self.widg_targHolder.repaint()
        self.scroll_targHolder.repaint()
        self.frm_targHolder.activate()
        CollapseFrame.repaint(self)
        self.__innerFrame.activate()
        

    def __updateWidget(self):
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
            #time.sleep(0.5)
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
        openSettings = ExpertSettingsDialog(self, self.optionVars)
        openSettings.exec_()

    def validateFrequency(self, var: int):
        cntrFreq = self.__root._mavModel.getOption('SDR_centerFreq')
        sampFreq = self.__root._mavModel.getOption('SDR_samplingFreq')
        if abs(var - cntrFreq) > sampFreq:
            return False
        return True

    def _updateButtonCallback(self):
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

    def updateGUIOptionVars(self, scope=0):
        optionDict = self.__root._mavModel.getOptions(
            scope, timeout=self.__root.defaultTimeout)
        for optionName, optionValue in optionDict.items():
            self.optionVars[optionName].setText(str(optionValue))
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
    def __init__(self, parent, optionVars):
        super(ExpertSettingsDialog, self).__init__()
        self.parent = parent
        self.addPage(ExpertSettingsDialogPage(self, optionVars))
        self.setWindowTitle('Expert/Engineering Settings')
        self.resize(640,480)

class ExpertSettingsDialogPage(QWizardPage):
    def __init__(self, parent=None, optionVars=None):
        super(ExpertSettingsDialogPage, self).__init__(parent)
        self.__parent = parent
        self.optionVars = optionVars

        # Configure member vars here
        self.__parent.parent.updateGUIOptionVars(0xFF)
        self.__createWidget()

    def __createWidget(self):
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
        return True

    def submit(self):
        if not self.validateParameters():
            return
        self.__parent.parent.submitGUIOptionVars(0xFF)



class AddTargetDialog(QWizard):
    def __init__(self, parent, centerFrequency: int, samplingFrequency: int):
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
        return abs(int(self.page.targFreqEntry.text()) - self.centerFrequency) <= self.samplingFrequency


    def submit(self):
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
    def __init__(self, parent, centerFrequency: int, samplingFrequency: int):
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
    def __init__(self, parent):
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
    def __init__(self, parent):
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
        btn_export = QPushButton(" Export")
        controlPanel.addWidget(btn_export)


        
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
        
    def __loadWebMap(self):
        p1lat = float(self.__p1latEntry.text())
        p1lon = float(self.__p1lonEntry.text())
        p2lat = float(self.__p2latEntry.text())
        p2lon = float(self.__p2lonEntry.text())
        self.__mapFrame.setParent(None)
        self.__mapFrame = WebMap(self.__holder, p1lat, p1lon, 
                p2lat, p2lon, False)
        self.__mapFrame.resize(800, 500)
        self.__mapOptions.setMap(self.__mapFrame, True)

    def __loadCachedMap(self):
        p1lat = float(self.__p1latEntry.text())
        p1lon = float(self.__p1lonEntry.text())
        p2lat = float(self.__p2latEntry.text())
        p2lon = float(self.__p2lonEntry.text())
        self.__mapFrame.setParent(None)
        self.__mapFrame = WebMap(self.__holder, p1lat, p1lon, 
                p2lat, p2lon, True)
        self.__mapFrame.resize(800, 500)
        self.__mapOptions.setMap(self.__mapFrame, True)

    def __loadMapFile(self):
        self.__mapFrame.setParent(None)
        self.__mapFrame = StaticMap(self.__holder)
        self.__mapFrame.resize(800, 500)
        self.__mapOptions.setMap(self.__mapFrame, False)






class RectangleMapTool(QgsMapToolEmitPoint):
  def __init__(self, canvas):
    self.canvas = canvas
    QgsMapToolEmitPoint.__init__(self, self.canvas)
    self.rubberBand = QgsRubberBand(self.canvas, True)
    self.rubberBand.setColor(QColor(0,255,255,125))
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
    self.showRect(self.startPoint, self.endPoint)

  def canvasReleaseEvent(self, e):
    self.isEmittingPoint = False

  def canvasMoveEvent(self, e):
    if not self.isEmittingPoint:
      return

    self.endPoint = self.toMapCoordinates(e.pos())
    self.showRect(self.startPoint, self.endPoint)

  def showRect(self, startPoint, endPoint):
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
    if self.startPoint is None or self.endPoint is None:
      return None
    elif (self.startPoint.x() == self.endPoint.x() or \
          self.startPoint.y() == self.endPoint.y()):
      return None

    return QgsRectangle(self.startPoint, self.endPoint)

  def deactivate(self):
    QgsMapTool.deactivate(self)
    self.deactivated.emit()


class MapWidget(QWidget):

    def __init__(self, root):
        QWidget.__init__(self)
        self.holder = QVBoxLayout()
        self.layer = None
        self.toolbar = QToolBar()
        self.canvas = QgsMapCanvas()
        self.canvas.setCanvasColor(Qt.white)


    def adjustCanvas(self):
        self.canvas.setExtent(self.layer.extent())  
        self.canvas.setLayers([self.layer]) 
        self.canvas.zoomToFullExtent()   
        self.canvas.freeze(True)  
        self.canvas.show()     
        self.canvas.refresh()       
        self.canvas.freeze(False)    
        self.canvas.repaint()

    def addToolBar(self):
        self.actionZoomIn = QAction("Zoom in", self)
        self.actionZoomOut = QAction("Zoom out", self)
        self.actionPan = QAction("Pan", self)

        self.actionZoomIn.setCheckable(True)
        self.actionZoomOut.setCheckable(True)
        self.actionPan.setCheckable(True)

        self.actionZoomIn.triggered.connect(self.zoomIn)
        self.actionZoomOut.triggered.connect(self.zoomOut)
        self.actionPan.triggered.connect(self.pan)

        self.toolbar.addAction(self.actionZoomIn)
        self.toolbar.addAction(self.actionZoomOut)
        self.toolbar.addAction(self.actionPan)

        # create the map tools
        self.toolPan = QgsMapToolPan(self.canvas)
        self.toolPan.setAction(self.actionPan)
        self.toolZoomIn = QgsMapToolZoom(self.canvas, False) # false = in
        self.toolZoomIn.setAction(self.actionZoomIn)
        self.toolZoomOut = QgsMapToolZoom(self.canvas, True) # true = out
        self.toolZoomOut.setAction(self.actionZoomOut)



    def zoomIn(self):
        self.canvas.setMapTool(self.toolZoomIn)

    def zoomOut(self):
        self.canvas.setMapTool(self.toolZoomOut)

    def pan(self):
        self.canvas.setMapTool(self.toolPan)
        
class MapOptions(QWidget):

    def __init__(self, holder):
        QWidget.__init__(self)

        self.mapWidget = None
        self.btn_cacheMap = None
        self.isWebMap = False
        self.__createWidgets()
        


    def __createWidgets(self):
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

        self.setLayout(lay_mapOptions)


        '''
        # MAP LEGEND
        frm_mapLegend = tk.Frame(master=frm_mapGrid, width=self.SBWidth)
        frm_mapLegend.pack(side=tk.BOTTOM)

        lbl_legend = tk.Label(frm_mapLegend, width=self.SBWidth,
                              bg='gray', text='Map Legend')
        lbl_legend.grid(column=0, row=0, sticky='ew')

        lbl_legend = tk.Label(frm_mapLegend, width=self.SBWidth,
                              bg='light gray', text='Vehicle')
        lbl_legend.grid(column=0, row=1, sticky='ew')

        lbl_legend = tk.Label(frm_mapLegend, width=self.SBWidth,
                              bg='light gray', text='Target')
        lbl_legend.grid(column=0, row=2, sticky='ew')
        '''
    def __cacheMap(self):
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
        self.isWebMap = isWebMap
        self.mapWidget = mapWidg
        
        self.btn_cacheMap.setEnabled(isWebMap)

'''
    Helper Class to facilititate displaying online web maps
'''
class WebMap(MapWidget):

    def __init__(self, root, p1lat, p1lon, p2lat, p2lon, loadCached):
        # Initialize WebMapFrame
        MapWidget.__init__(self, root)

        self.loadCached = loadCached

        self.transformToWeb = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsCoordinateReferenceSystem("EPSG:3857"), 
                QgsProject.instance())
        self.transform = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:3857"), 
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance())

        
        self.addLayers()
        self.adjustCanvas()
        r = QgsRectangle(p1lon, p2lat, p2lon, p1lat)
        rect = self.transformToWeb.transformBoundingBox(r)
        self.canvas.zoomToFeatureExtent(rect)

        self.addToolBar()
        self.addRectTool()
        self.pan()

        self.holder.addWidget(self.toolbar)
        self.holder.addWidget(self.canvas)
        self.setLayout(self.holder)

        root.addWidget(self, 0, 1, 1, 2)
        self.root = root

    def addLayers(self):
        if self.loadCached:
            direct = QDir()
            path = direct.currentPath()
            urlWithParams = 'type=xyz&url=file:///'+ path+'/tiles/%7Bz%7D/%7Bx%7D/%7By%7D.png'
        else:
            urlWithParams = 'type=xyz&url=http://a.tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0&crs=EPSG3857'    
        self.layer = QgsRasterLayer(urlWithParams, 'OpenStreetMap', 'wms') 
        if self.layer.isValid():   
            crs = self.layer.crs()
            crs.createFromString("EPSG:3857")  
            self.layer.setCrs(crs)
            QgsProject.instance().addMapLayer(self.layer)
            print('valid layer')
        else:
            print('invalid layer')

    def addRectTool(self):
        self.rectAction = QAction("Rect", self)
        self.rectAction.setCheckable(True)
        self.rectAction.triggered.connect(self.rect)
        self.toolbar.addAction(self.rectAction)
        self.toolRect = RectangleMapTool(self.canvas)
        self.toolRect.setAction(self.rectAction)

    def rect(self):
        self.canvas.setMapTool(self.toolRect)

    def deg2num(self, lat_deg, lon_deg, zoom):
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        x = int((lon_deg + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x,y)
        

    def cacheMap(self):
        if (self.toolRect.rectangle() == None):
            return
        else:
            rect = self.toolRect.rectangle()
            r = self.transform.transformBoundingBox(self.toolRect.rectangle(), 
                                QgsCoordinateTransform.ForwardTransform, True)
            print("Rectangle:", r.xMinimum(),
                    r.yMinimum(), r.xMaximum(), r.yMaximum()
                 )
            m1 = QgsVertexMarker(self.canvas)
            m1.setCenter(QgsPointXY(rect.xMinimum(),rect.yMinimum()))
            m1.setColor(QColor(255,0, 0)) #(R,G,B)
            m1.setIconSize(10)
            m1.setIconType(QgsVertexMarker.ICON_X)
            m1.setPenWidth(3)
            m1.show()
            
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
                print(":(")
            
    def downloadTile(self, xtile, ytile, zoom):
        
        url = "http://c.tile.openstreetmap.org/%d/%d/%d.png" % (zoom, xtile, ytile)
        dir_path = "tiles/%d/%d/" % (zoom, xtile)
        download_path = "tiles/%d/%d/%d.png" % (zoom, xtile, ytile)
        
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
    def __init__(self, root):
        MapWidget.__init__(self, root)

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
        self.fileName = QFileDialog.getOpenFileName()      

    def __addLayers(self):
        if(self.fileName == None):
            return
        self.layer = QgsRasterLayer(self.fileName[0], "SRTM layer name")
        if self.layer.isValid():   
            QgsProject.instance().addMapLayer(self.layer)
            print('valid layer')
        else:
            print('invalid layer')

def configSetup():
    config_path = 'gcsConfig.ini'
    if(not os.path.isfile(config_path)):
        prefix_path = QFileDialog.getExistingDirectory(None, 
                'Select the Qgis directory')
        if ("qgis" in prefix_path):            
            config = configparser.ConfigParser()
            config['FilePaths'] = {}
            config['FilePaths']['PrefixPath'] = prefix_path
            with open(config_path, 'w') as configFile:
                config.write(configFile)
                return prefix_path
                print("here")
        else:
            msg = QMessageBox()
            msg.setText("Wrong file. Choose qgis file")
            msg.setWindowTitle("Alert")
            msg.setIcon(QMessageBox.Critical)
            msg.exec_()
            configSetup()
    else:
        config = configparser.ConfigParser()
        config.read(config_path)
        prefix_path = config['FilePaths']['PrefixPath']
        return prefix_path
   


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
    prefix_path = configSetup() 
    #prefix_path = config['FilePaths']['PrefixPath']
    app.setPrefixPath(prefix_path, True) 
    app.initQgis()

    ex = GCS()
    ex.show()

    exitcode = app.exec_()
    QgsApplication.exitQgis()
    sys.exit(exitcode)
