from RCTComms.comms import gcsComms
from RCTComms.transport import RCTTCPClient, RCTTCPServer
import rctCore
from PyQt5.QtCore import QRegExp
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QRegExpValidator
from config import ConnectionMode
import config
from pathlib import Path

class WarningMessager:

    def showWarning(text: str, title: str ="Warning"):
        '''
        Creates warning popups
        Args:
            title: message header
            text: message body
        '''
        msg = QMessageBox()
        msg.setText(title)
        msg.setWindowTitle("Alert")
        msg.setInformativeText(text)
        msg.setIcon(QMessageBox.Critical)
        msg.addButton(QMessageBox.Ok)
        msg.exec_()

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

        lbl_SYSautostart = QLabel("SYS Autostart")
        expSettingsFrame.addWidget(lbl_SYSautostart, 8, 0)

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

        self.optionVars['SYS_autostart'] = QLineEdit()
        expSettingsFrame.addWidget(self.optionVars['SYS_autostart'], 8, 1)

        btn_submit = QPushButton('submit')
        btn_submit.clicked.connect(lambda:self.submit())
        expSettingsFrame.addWidget(btn_submit, 9, 0, 1, 2)

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
            WarningMessager.showWarning("Entered information could not be validated")
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
            WarningMessager.showWarning("You have entered an invalid target frequency. Please try again.", "Invalid frequency")
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
    def __init__(self, portVal, parent):
        '''
        Creates new ConnectionDialog widget
        Args:
            portVal: the port value used
        '''
        super(ConnectionDialog, self).__init__()
        self.parent = parent
        self.setWindowTitle('Connect Settings')
        self.page = ConnectionDialogPage(portVal, self)
        self.portVal = portVal
        self.addPage(self.page)
        self.resize(640,480)
        self.button(QWizard.FinishButton).clicked.connect(lambda:self.submit())

    def submit(self):
        '''
        Internal Function to submit user inputted connection settings
        '''
        self.portVal = int(self.page.portEntry.text())

        if self.parent.config.connection_mode == ConnectionMode.TOWER:
            self.port = RCTTCPServer(self.portVal, self.parent.connectionHandler)
            self.port.open()
        else:
            try:
                self.port = RCTTCPClient(
                    addr=self.page.addrEntry.text(), port=int(self.page.portEntry.text()))
                self.parent.connectionHandler(self.port, 0)
            except ConnectionRefusedError:
                WarningMessager.showWarning("Failure to connect:\nPlease ensure server is running.")
                self.port.close()
                return
        self.parent._transport = self.port

class ConnectionDialogPage(QWizardPage):
    '''
    Custom DialogPage widget - Allows the user to configure
    settings to connect to the drone
    '''
    def __init__(self, portVal, parent):
        '''
        Creates a new AddTargetDialog
        Args:
            portVal: The port value used
        '''
        super(ConnectionDialogPage, self).__init__()
        self.__portEntryVal = portVal # default value
        self.portEntry = None # default value
        self.__parent = parent

        self.__createWidget()


    def __createWidget(self):
        '''
        Internal function to create widgets
        '''
        frm_holder = QVBoxLayout()
        frm_holder.addStretch(1)
        #-----
        frm_conType = QHBoxLayout()
        frm_conType.addStretch(1)

        lbl_conType = QLabel('Connection Type:')
        frm_conType.addWidget(lbl_conType)

        btn_TCP = QCheckBox('TCP')
        frm_conType.addWidget(btn_TCP)
        #-----
        frm_port = QHBoxLayout()
        frm_port.addStretch(1)

        lbl_port = QLabel('Port')
        frm_port.addWidget(lbl_port)

        self.portEntry = QLineEdit()
        self.portEntry.setText(str(self.__portEntryVal))
        frm_port.addWidget(self.portEntry)

        if self.__parent.parent.config.connection_mode == ConnectionMode.DRONE:
            frm_addr = QHBoxLayout()
            frm_addr.addStretch(1)

            lbl_addr = QLabel('Address')
            frm_addr.addWidget(lbl_addr)
            self.addrEntry = QLineEdit()

            self.addrEntry.setText('127.0.0.1')
            frm_addr.addWidget(self.addrEntry)

            frm_holder.addLayout(frm_addr)

        #-----
        frm_holder.addLayout(frm_port)
        frm_holder.addLayout(frm_conType)
        self.setLayout(frm_holder)

class ConfigDialog(QWizard):
    '''
    Custom Dialog widget to facilitate changing configuration settings
    '''
    def __init__(self, parent):
        '''
        Creates new ConnectionDialog widget
        Args:
            portVal: the port value used
        '''
        super(ConfigDialog, self).__init__()

        self.config = config.Configuration(Path('gcsConfig.ini'))
        self.config.load()

        self.parent = parent
        self.setWindowTitle('Edit Configuration Settings')
        self.page = ConfigDialogPage(self)
        self.addPage(self.page)
        self.resize(640,480)
        self.button(QWizard.FinishButton).clicked.connect(lambda:self.submit())

    def submit(self):
        '''
        Internal Function to submit user inputted configuration settings and
        close GCS UI
        '''
        self.config.qgis_prefix_path = Path(self.page.prefix_path.text())
        if self.page.prefix_set_true.isChecked():
            self.config.qgis_prefix_set = True
        else:
            self.config.qgis_prefix_set = False
        self.config.map_extent = (
            (float(self.page.lat_1.text()), float(self.page.lon_1.text())),
            (float(self.page.lat_2.text()), float(self.page.lon_2.text())) )
        self.config.connection_addr = self.page.addr.text()
        self.config.connection_port = int(self.page.portVal.text())
        if self.page.drone_mode.isChecked():
            self.config.connection_mode = ConnectionMode.DRONE
        else:
            self.config.connection_mode = ConnectionMode.TOWER
        self.config.write()

        self.parent.close()

class ConfigDialogPage(QWizardPage):
    '''
    Custom DialogPage widget - Allows the user to configure
    settings to connect to the drone
    '''
    def __init__(self, parent):
        '''
        Creates a new AddTargetDialog
        Args:
            portVal: The port value used
        '''
        super(ConfigDialogPage, self).__init__()
        '''self.__portEntryVal = portVal # default value
        self.portEntry = None # default value'''
        self.__parent = parent

        self.__createWidget()


    def __createWidget(self):
        '''
        Internal function to create widgets
        '''
        frm_holder = QVBoxLayout()
        frm_holder.addStretch(1)

        #----- Prefix Path
        frm_prefix_path = QHBoxLayout()
        frm_prefix_path.addStretch(1)

        lbl_prefix_path = QLabel('QGis Prefix Path')
        frm_prefix_path.addWidget(lbl_prefix_path)

        self.prefix_path = QLineEdit()
        self.prefix_path.setText(str(self.__parent.config.qgis_prefix_path))
        frm_prefix_path.addWidget(self.prefix_path, 15)
        #----- Prefix Set
        frm_prefix_set = QHBoxLayout()
        frm_prefix_set.addStretch(1)

        lbl_prefix_set = QLabel('QGis Prefix Set')
        frm_prefix_set.addWidget(lbl_prefix_set)

        self.prefix_set_true = QRadioButton('True')
        self.prefix_set_false = QRadioButton('False')
        if self.__parent.config.qgis_prefix_set:
            self.prefix_set_true.setChecked(True)
        else:
            self.prefix_set_false.setChecked(True)
        prefix_set = QButtonGroup(parent=frm_prefix_set)
        prefix_set.setExclusive(True)
        prefix_set.addButton(self.prefix_set_true)
        prefix_set.addButton(self.prefix_set_false)

        frm_prefix_set.addWidget(self.prefix_set_true)
        frm_prefix_set.addWidget(self.prefix_set_false)
        #----- Lat 1
        frm_lat_1 = QHBoxLayout()
        frm_lat_1.addStretch(1)

        lbl_lat_1 = QLabel('Lat 1')
        frm_lat_1.addWidget(lbl_lat_1)

        self.lat_1 = QLineEdit()
        self.lat_1.setText(str(self.__parent.config.map_extent[0][0]))
        frm_lat_1.addWidget(self.lat_1)
        #----- Lat 2
        frm_lat_2 = QHBoxLayout()
        frm_lat_2.addStretch(1)

        lbl_lat_2 = QLabel('Lat 2')
        frm_lat_2.addWidget(lbl_lat_2)

        self.lat_2 = QLineEdit()
        self.lat_2.setText(str(self.__parent.config.map_extent[1][0]))
        frm_lat_2.addWidget(self.lat_2)
        #----- Lon 1
        frm_lon_1 = QHBoxLayout()
        frm_lon_1.addStretch(1)

        lbl_lon_1 = QLabel('Lon 1')
        frm_lon_1.addWidget(lbl_lon_1)

        self.lon_1 = QLineEdit()
        self.lon_1.setText(str(self.__parent.config.map_extent[0][1]))
        frm_lon_1.addWidget(self.lon_1)
        #----- Lon 2
        frm_lon_2 = QHBoxLayout()
        frm_lon_2.addStretch(1)

        lbl_lon_2 = QLabel('Lon 2')
        frm_lon_2.addWidget(lbl_lon_2)

        self.lon_2 = QLineEdit()
        self.lon_2.setText(str(self.__parent.config.map_extent[1][1]))
        frm_lon_2.addWidget(self.lon_2)
        #----- Addr
        frm_addr = QHBoxLayout()
        frm_addr.addStretch(1)

        lbl_addr = QLabel('Addr')
        frm_addr.addWidget(lbl_addr)

        self.addr = QLineEdit()
        self.addr.setText(str(self.__parent.config.connection_addr))
        frm_addr.addWidget(self.addr)
        #----- Port
        frm_port = QHBoxLayout()
        frm_port.addStretch(1)

        lbl_port = QLabel('Port')
        frm_port.addWidget(lbl_port)

        self.portVal = QLineEdit()
        self.portVal.setText(str(self.__parent.config.connection_port))
        frm_port.addWidget(self.portVal)
        #----- Mode
        frm_mode = QHBoxLayout()
        frm_mode.addStretch(1)

        lbl_mode = QLabel('Mode')
        frm_mode.addWidget(lbl_mode)

        self.drone_mode = QRadioButton('Drone')
        self.tower_mode = QRadioButton('Tower')
        if self.__parent.config.connection_mode == ConnectionMode.DRONE:
            self.drone_mode.setChecked(True)
        else:
            self.tower_mode.setChecked(True)
        mode = QButtonGroup(parent=frm_mode)
        mode.setExclusive(True)
        mode.addButton(self.drone_mode)
        mode.addButton(self.tower_mode)

        frm_mode.addWidget(self.drone_mode)
        frm_mode.addWidget(self.tower_mode)

        #-----
        frm_holder.addLayout(frm_prefix_path)
        frm_holder.addLayout(frm_prefix_set)
        frm_holder.addLayout(frm_lat_1)
        frm_holder.addLayout(frm_lat_2)
        frm_holder.addLayout(frm_lon_1)
        frm_holder.addLayout(frm_lon_2)
        frm_holder.addLayout(frm_addr)
        frm_holder.addLayout(frm_port)
        frm_holder.addLayout(frm_mode)

        self.setLayout(frm_holder)
