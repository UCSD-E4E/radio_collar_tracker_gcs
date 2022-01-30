import time
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from qgis.core import *    
from qgis.gui import *  
from qgis.utils import *
from rctGCS import *
from ui.warnings import WarningMessager

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
            Qt.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(Qt.RightArrow)
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

    @pyqtSlot()
    def on_pressed(self):
        '''
        Internal Callback to be called when the toggle button is 
        pressed. Facilitates the collapsing and displaying of the
        content_area contents
        '''
        checked = self.toggle_button.isChecked()
        self.toggle_button.setArrowType(
            Qt.DownArrow if not checked else Qt.RightArrow
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
                WarningMessager.showWarning("Failed to update GUI option vars", "Unexpected Error")
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
                WarningMessager.showWarning("Target frequency " + str(self.targEntries[targetName][0]) + " is invalid. Please enter another value.")
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
                WarningMessager.showWarning("Failed to update GUI option vars", "Unexpected Error")
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
        p1lat = float(self.__p1latEntry.text())
        p1lon = float(self.__p1lonEntry.text())
        p2lat = float(self.__p2latEntry.text())
        p2lon = float(self.__p2lonEntry.text())
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

