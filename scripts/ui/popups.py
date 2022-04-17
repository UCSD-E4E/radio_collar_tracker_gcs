from RCTComms.comms import gcsComms
from RCTComms.transport import RCTTCPServer
import rctCore
from PyQt5.QtCore import QRegExp
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QRegExpValidator

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
            self.port = RCTTCPServer(port=int(self.page.portEntry.text()))
            self.comms = gcsComms(self.port, self.__parent.systemSettingsWidget)
            self.comms.start()

            self.model = rctCore.MAVModel(self.comms)
            self.model.start()
        except:
            WarningMessager.showWarning("Please specify valid connection settings")
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

        #-----
        frm_holder.addLayout(frm_port)
        frm_holder.addLayout(frm_conType)
        self.setLayout(frm_holder)
