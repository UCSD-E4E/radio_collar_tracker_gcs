import configparser
import json
import logging
import queue as q
from functools import partial
from pathlib import Path
import config

import rctCore
import utm
from config import get_instance
from PyQt5.QtWidgets import (QFileDialog, QGridLayout, QLabel, QMainWindow,
                             QPushButton, QScrollArea, QVBoxLayout, QWidget)
from RCTComms.transport import RCTTCPServer
from ui.controls import *
from ui.map import *
from functools import partial
from RCTComms.transport import RCTTCPServer, RCTAbstractTransport

class GCS(QMainWindow):
    '''
    Ground Control Station GUI
    '''

    SBWidth = 500

    defaultTimeout = 5

    defaultPortVal = 9000

    sig = pyqtSignal()

    connectSignal = pyqtSignal(int)
    disconnectSignal = pyqtSignal(int)

    mavEventSignal = pyqtSignal(rctCore.Events, int)

    def __init__(self):
        '''
        Creates the GCS Application Object
        '''
        super().__init__()
        self.__log = logging.getLogger('rctGCS.GCS')
        self.portVal = self.defaultPortVal
        self._transport = None
        self._mavModels = {}
        self._mavModel = None
        self._buttons = []
        self._systemConnectionTab = None
        self.systemSettingsWidget = None
        self.__missionStatusText = "Start Recording"
        self.__missionStatusBtn = None
        self.innerFreqFrame = None
        self.freqElements = []
        self.targEntries = {}
        self.mapControl = None
        self.mapOptions = None
        self.mapDisplay = None
        self.mainThread = None
        self.testFrame = None
        self.pingSheetCreated = False

        self.config = config.Configuration(Path('gcsConfig.ini'))
        self.config.load()

        self.__createWidgets()
        for button in self._buttons:
            button.config(state='disabled')

        self.queue = q.Queue()
        self.sig.connect(self.execute_inmain, Qt.QueuedConnection)

        self.connectSignal.connect(self.connectionSlot)
        self.disconnectSignal.connect(self.disconnectSlot)

    def execute_inmain(self):
        while not self.queue.empty():
            (fn, coord, frequency, numPings) = self.queue.get()
            fn(coord, frequency, numPings)

    def __mavEventHandler(self, event, id):
        if event == rctCore.Events.Heartbeat:
            self.__heartbeatCallback(id)
        if event == rctCore.Events.Exception:
            self.__handleRemoteException(id)
        if event == rctCore.Events.VehicleInfo:
            self.__handleVehicleInfo(id)
        if event == rctCore.Events.NewPing:
            self.__handleNewPing(id)
        if event == rctCore.Events.NewEstimate:
            self.__handleNewEstimate(id)
        if event == rctCore.Events.ConeInfo:
            self.__handleNewCone(id)

    def __registerModelCallbacks(self, id):
        mavModel = self._mavModels[id]
        eventTypes = [rctCore.Events.Heartbeat, rctCore.Events.Exception,
        rctCore.Events.VehicleInfo, rctCore.Events.NewPing,
        rctCore.Events.NewEstimate, rctCore.Events.ConeInfo]
        for eventType in eventTypes:
            mavModel.registerCallback(eventType,
            partial(self.mavEventSignal.emit, eventType, id))

    def __startTransport(self):
        if self._transport is not None and self._transport.isOpen():
            self._transport.close()
        self.mavEventSignal.connect(self.__mavEventHandler)
        if self.config.connection_mode == config.ConnectionMode.TOWER:
            self._transport = RCTTCPServer(self.portVal, self.connectionHandler)
            self._transport.open()
        else:
            try:
                self._transport = RCTTCPClient(addr=self.addrVal, port=self.portVal)
                self.connectionHandler(self._transport, 0)
            except ConnectionRefusedError:
                WarningMessager.showWarning("Failure to connect:\nPlease ensure server is running.")
                self._transport.close()
                return

    def connectionHandler(self, connection, id):
        comms = gcsComms(connection, partial(self.__disconnectHandler, id))
        model = rctCore.MAVModel(comms)
        model.start()
        self._mavModels[id] = model
        if self._mavModel is None:
            self._mavModel = model
            self.__registerModelCallbacks(id)

        self.connectSignal.emit(id)

    def connectionSlot(self, id):
        '''
        Handle GUI updates in main thread by connecting pyqt signal to the
        remaining connection work
        '''
        self.updateConnectionsLabel()
        self.systemSettingsWidget.connectionMade()
        self.__missionStatusBtn.setEnabled(True)
        self.__btn_exportAll.setEnabled(True)
        self.__btn_precision.setEnabled(True)
        self.__btn_heatMap.setEnabled(True)
        self.__log.info('Connected {}'.format(id))

    def __disconnectHandler(self, id):
        mavModel = self._mavModels[id]
        del self._mavModels[id]
        if mavModel == self._mavModel:
            self._mavModel = None

        self.disconnectSignal.emit(id)

    def disconnectSlot(self, id):
        '''
        Handle GUI updates in main thread by connecting pyqt signal to the
        remaining disconnection work
        '''
        if len(self._mavModels) == 0:
            self.systemSettingsWidget.disconnected()
            self.__missionStatusBtn.setEnabled(False)
            self.__btn_exportAll.setEnabled(False)
            self.__btn_precision.setEnabled(False)
            self.__btn_heatMap.setEnabled(False)
        self.updateConnectionsLabel()
        self.__log.info('Disconnected {}'.format(id))

    def updateConnectionsLabel(self):
        numConnections = len(self._mavModels)
        label = "System: No Connection"
        if numConnections == 1:
            label = "System: 1 Connection"
        elif numConnections > 1:
            label = "System: {} Connections".format(numConnections)
        self._systemConnectionTab.updateText(label)

    def __changeModel(self, id):
        '''
        Changing the selected _mavModel
        '''
        self._mavModel = self._mavModels[id]
        self.systemSettingsWidget.connectionMade()

    def __changeModelByIndex(self, index):
        '''
        Changing the selected _mavModel by index
        '''
        if index < 0 or index > len(self._mavModels):
            return
        try:
            self.__changeModel(list(self._mavModels.keys())[index])
        except:
            print('Failed to change Model to {}'.format(index))
            self.__useDefaultModel()

    def __useDefaultModel(self):
        '''
        Using the first model as the default if possible
        '''
        try:
            if len(self._mavModels) > 0:
                self.__changeModel(list(self._mavModels.keys())[0])
        except:
            self._mavModel = None

    def mainloop(self, n=0):
        '''
        Main Application Loop
        :param n:
        :type n:
        '''

    def __heartbeatCallback(self, id):
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
        WarningMessager.showWarning("No Heartbeats Received")

    def __handleNewEstimate(self, id):
        '''
        Internal callback to handle when a new estimate is received
        '''
        mavModel = self._mavModels[id]
        freqList = mavModel.EST_mgr.getFrequencies()
        for frequency in freqList:
            params, stale, res = mavModel.EST_mgr.getEstimate(frequency)

            zone, let = mavModel.EST_mgr.getUTMZone()
            coord = utm.to_latlon(params[0], params[1], zone, let)

            numPings = mavModel.EST_mgr.getNumPings(frequency)

            if self.mapDisplay is not None:
                self.mapDisplay.plotEstimate(coord, frequency)
                #self.queue.put( (self.mapDisplay.plotPrecision, coord, frequency, numPings) )
                #self.sig.emit()
                #self.mapDisplay.plotPrecision(coord, frequency, numPings)

            if self.mapOptions is not None:
                self.mapOptions.estDistance(coord, stale, res)


    def __handleNewPing(self, id):
        '''
        Internal callback to handle when a new ping is received
        '''
        mavModel = self._mavModels[id]
        freqList = mavModel.EST_mgr.getFrequencies()
        for frequency in freqList:
            last = mavModel.EST_mgr.getPings(frequency)[-1].tolist()
            zone, let = mavModel.EST_mgr.getUTMZone()
            u = (last[0], last[1], zone, let)
            coord = utm.to_latlon(*u)
            power = last[3]

            if self.mapDisplay is not None:
                self.mapDisplay.plotPing(coord, power)



    def __handleVehicleInfo(self, id):
        '''
        Internal Callback for Vehicle Info
        '''
        mavModel = self._mavModels[id]
        if mavModel == None:
            return
        last = list(mavModel.state['VCL_track'])[-1]
        coord = mavModel.state['VCL_track'][last]

        mavModel.EST_mgr.addVehicleLocation(coord)

        if self.mapDisplay is not None:
            self.mapDisplay.plotVehicle(id, coord)

    def __handleNewCone(self, id):
        '''
        Internal callback to handle new cone info
        '''
        mavModel = self._mavModels[id]
        if mavModel == None:
            return

        recentCone = list(mavModel.state['CONE_track'])[-1]
        cone = mavModel.state['CONE_track'][recentCone]

        if self.mapDisplay is not None:
            self.mapDisplay.plotCone(cone)

    def __handleRemoteException(self, id):
        '''
        Internal callback for an exception message
        '''
        mavModel = self._mavModels[id]
        WarningMessager.showWarning('An exception has occured!\n%s\n%s' % (
            mavModel.lastException[0], mavModel.lastException[1]))

    def __startStopMission(self):
        # State machine for start recording -> stop recording

        if self._mavModel == None:
            return

        if self.__missionStatusBtn.text() == 'Start Recording':
            self.__missionStatusBtn.setText('Stop Recording')

            self._mavModel.startMission(timeout=self.defaultTimeout)
        else:
            self.__missionStatusBtn.setText('Start Recording')
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


            with get_instance(Path('gcsConfig.ini')) as config:
                config.map_extent = (
                    (lat1, lon1),
                    (lat2, lon2)
                )

        for id in self._mavModels:
            mavModel = self._mavModels[id]
            mavModel.stop()
        self._mavModels = {}
        self._mavModel = None
        if self._transport is not None and self._transport.isOpen():
            self._transport.close()
        self._transport = None
        super().closeEvent(event)

    def __handleConnectInput(self):
        '''
        Internal callback to connect GCS to drone
        '''
        connectionDialog = ConnectionDialog(self.portVal, self)
        connectionDialog.exec_()

        if connectionDialog.portVal is None or \
            (connectionDialog.portVal == self.portVal and len(self._mavModels) > 1):
            return

        self.portVal = connectionDialog.portVal
        if self.config.connection_mode == ConnectionMode.DRONE:
            self.addrVal = connectionDialog.addrVal
        self.__startTransport()

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
        self.mainThread = QThread.currentThread()

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
        btn_setup = QPushButton("Connection Settings")
        btn_setup.resize(self.SBWidth, 100)
        btn_setup.clicked.connect(self.__handleConnectInput)
        self.model_select = QComboBox()
        self.model_select.resize(self.SBWidth, 100)
        self.model_select.currentIndexChanged.connect(self.__changeModelByIndex)
        self.model_select.hide()
        lay_sys.addWidget(btn_setup)
        lay_sys.addWidget(self.model_select)


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
        self.__missionStatusBtn = QPushButton(self.__missionStatusText)
        self.__missionStatusBtn.setEnabled(False)
        self.__missionStatusBtn.clicked.connect(self.__startStopMission)

        self.__btn_exportAll = QPushButton('Export Info')
        self.__btn_exportAll.setEnabled(False)
        self.__btn_exportAll.clicked.connect(self.exportAll)

        self.__btn_precision = QPushButton('Do Precision')
        self.__btn_precision.setEnabled(False)
        self.__btn_precision.clicked.connect(self.__do_precision)

        self.__btn_heatMap = QPushButton('Display Heatmap')
        self.__btn_heatMap.setEnabled(False)
        self.__btn_heatMap.clicked.connect(self.__do_display_heatmap)

        wlay.addWidget(self._systemConnectionTab)
        wlay.addWidget(self.statusWidget)
        wlay.addWidget(self.mapControl)
        wlay.addWidget(self.systemSettingsWidget)
        wlay.addWidget(self.upgradeDisplay)
        wlay.addWidget(self.__missionStatusBtn)
        wlay.addWidget(self.__btn_exportAll)
        wlay.addWidget(self.__btn_precision)
        wlay.addWidget(self.__btn_heatMap)

        wlay.addStretch()
        content.resize(self.SBWidth, 400)
        frm_sideControl.setMinimumWidth(self.SBWidth)
        holder.addWidget(frm_sideControl, 0, 0, alignment=Qt.AlignLeft)
        holder.addWidget(self.mapOptions, 0, 4, alignment=Qt.AlignTop)
        centr_widget.setLayout(holder)
        self.resize(1800, 1100)
        self.show()
    
    def __do_display_heatmap(self):
        if self.mapDisplay:
            self.mapDisplay.setupHeatMap
        else:
            raise RuntimeError('No map loaded')
    
    def __do_precision(self):
        # todo: add modular frequencies
        self._mavModel.EST_mgr.doPrecisions(173500000)

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
        browse_file_btn.clicked.connect(self.fileDialogue)
        self.__innerFrame.addWidget(browse_file_btn, 2, 0)

        upgrade_btn = QPushButton('Upgrade')
        upgrade_btn.clicked.connect(self.sendUpgradeFile)
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
        try:
            file = open(self.filename.text(), "rb")
        except FileNotFoundError:
            WarningMessager.showWarning("Please choose a valid file.")
            return
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

        if sys_status == rctCore.RCT_STATES.finish:
            self.statusLabel.setText('Stopping')
            self.statusLabel.setStyleSheet("background-color: red")
        elif sdr_status == rctCore.SDR_INIT_STATES.fail or dir_status == rctCore.OUTPUT_DIR_STATES.fail or gps_status == rctCore.EXTS_STATES.fail or sys_status == rctCore.RCT_STATES.fail or (sw_status != 0 and sw_status != 1):
            self.statusLabel.setText('Failed')
            self.statusLabel.setStyleSheet("background-color: red")
        elif sys_status == rctCore.RCT_STATES.start or sys_status == rctCore.RCT_STATES.wait_end:
            self.statusLabel.setText('Running')
            self.statusLabel.setStyleSheet("background-color: green")
        elif sdr_status == rctCore.SDR_INIT_STATES.rdy and dir_status == rctCore.OUTPUT_DIR_STATES.rdy and gps_status == rctCore.EXTS_STATES.rdy and sys_status == rctCore.RCT_STATES.wait_start and sw_status == 1:
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
            try:
                if varName in self.compDicts:
                    configDict = self.compDicts[varName]
                    if str(varValue) in configDict:
                        configOpts = configDict[str(varValue)]
                        if varName in self.statusLabels:
                            self.statusLabels[varName].setText(configOpts['text'])
                        style = "background-color: %s" % configOpts['bg']
                        if varName in self.statusLabels:
                            self.statusLabels[varName].setStyleSheet(style)
            except KeyError:
                WarningMessager.showWarning("Failed to update GUI option vars", "Unexpected Error")
                continue

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
        btn_loadMap.clicked.connect(self.__loadMapFile)
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
        btn_loadWebMap.clicked.connect(self.__loadWebMap)
        lay_loadWebMap.addWidget(btn_loadWebMap, 3, 1, 1, 2)

        btn_loadCachedMap = QPushButton('Load from Cache')
        btn_loadCachedMap.clicked.connect(self.__loadCachedMap)
        lay_loadWebMap.addWidget(btn_loadCachedMap, 4, 1, 1, 2)

        controlPanel.addWidget(frm_loadWebMap)
        controlPanel.addLayout(lay_loadWebMap)


        self.setContentLayout(controlPanel)

    def __coordsFromConf(self):
        '''
        Internal function to pull past coordinates from the config
        file if they exist
        '''
        config_path = 'gcsConfig.ini'
        config = configparser.ConfigParser()
        config.read(config_path)
        try:
            lat1 = config['LastCoords']['lat1']
            lon1 = config['LastCoords']['lon1']
            lat2 = config['LastCoords']['lat2']
            lon2 = config['LastCoords']['lon2']
            return lat1, lon1, lat2, lon2
        except KeyError:
            WarningMessager.showWarning("Could not read config path", config_path)
            return None, None, None, None

    def __initLatLon(self):
        lat1 = self.__p1latEntry.text()
        lon1 = self.__p1lonEntry.text()
        lat2 = self.__p2latEntry.text()
        lon2 = self.__p2lonEntry.text()



        if lat1 is None or lat2 is None or lon1 is None or lon2 is None or \
                lat1 == '' or lon1 == '' or lat2 == '' or lon2 == '':
            with get_instance(Path('gcsConfig.ini')) as config:
                nw_extent, se_extent = config.map_extent

            lat1 = str(nw_extent[0])
            self.__p1latEntry.setText(lat1)
            lon1 = str(nw_extent[1])
            self.__p1lonEntry.setText(lon1)
            lat2 = str(se_extent[0])
            self.__p2latEntry.setText(lat2)
            lon2 = str(se_extent[1])
            self.__p2lonEntry.setText(lon2)


        p1lat = float(lat1)
        p1lon = float(lon1)
        p2lat = float(lat2)
        p2lon = float(lon2)

        return [p1lat, p1lon, p2lat, p2lon]

    def __loadWebMap(self):
        '''
        Internal function to load map from web
        '''
        p1lat, p1lon, p2lat, p2lon = self.__initLatLon()
        try:
            temp = WebMap(self.__holder, p1lat, p1lon,
                    p2lat, p2lon, False)
        except RuntimeError:
            WarningMessager.showWarning("Failed to load web map")
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
        p1lat, p1lon, p2lat, p2lon = self.__initLatLon()
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
        try:
            self.__mapFrame = StaticMap(self.__holder)
        except FileNotFoundError as e:
            print(e)
            self.__loadWebMap()
        else:
            self.__mapFrame.resize(800, 500)
            self.__mapOptions.setMap(self.__mapFrame, False)
            self.__root.setMap(self.__mapFrame)
