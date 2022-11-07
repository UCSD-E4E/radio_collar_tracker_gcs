import time
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIntValidator
from ui.popups import *

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

        self.btn_addTarget = QPushButton('Add Target')
        self.btn_addTarget.clicked.connect(lambda:self.addTarget())
        self.btn_addTarget.setEnabled(False)
        self.__innerFrame.addWidget(self.btn_addTarget, 0, 0, 1, 2)
        self.btn_clearTargs = QPushButton('Clear Targets')
        self.btn_clearTargs.clicked.connect(lambda:self.clearTargets())
        self.btn_clearTargs.setEnabled(False)
        self.__innerFrame.addWidget(self.btn_clearTargs, 5, 0)

        self.btn_submit = QPushButton('Update')
        self.btn_submit.clicked.connect(lambda:self._updateButtonCallback())
        self.btn_submit.setEnabled(False)
        self.__innerFrame.addWidget(self.btn_submit, 5, 1)

        self.btn_advSettings = QPushButton('Expert & Debug Configuration')
        self.btn_advSettings.clicked.connect(lambda:self.__advancedSettings())
        self.btn_advSettings.setEnabled(False)
        self.__innerFrame.addWidget(self.btn_advSettings, 6, 0, 1, 2)

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

        self.submitGUIOptionVars(0x00)

        self.updateGUIOptionVars()

    def updateGUIOptionVars(self, scope=0, options=None):
        if options is not None:
            self.optionVars = options
        optionDict = self.__root._mavModel.getOptions(
            scope, timeout=self.__root.defaultTimeout)
        for optionName, optionValue in optionDict.items():
            if optionName == 'GPS_mode' or optionName == 'SYS_autostart':
                try:
                    if optionValue:
                        self.optionVars[optionName].setText('true')
                    else:
                        self.optionVars[optionName].setText('false')
                except AttributeError:
                    WarningMessager.showWarning("Failed to update GUI option vars", "Unexpected Error")
                    print(optionName)
            else:
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
            if keyword == 'SYS_outputDir' or keyword == 'GPS_device':
                options[keyword] = self.optionVars[keyword].text()
            elif keyword == 'GPS_mode' or keyword == 'SYS_autostart':
                val = self.optionVars[keyword].text()
                if val == 'true':
                    options[keyword] = True
                else:
                    options[keyword] = False
            else:
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
        try:
            cntrFreq = int(self.optionVars['SDR_centerFreq'].text())
            sampFreq = int(self.optionVars['SDR_samplingFreq'].text())
            sdrGain = float(self.optionVars['SDR_gain'].text())
        except ValueError:
            WarningMessager.showWarning("Please enter center and sampling frequences and SDR gain settings.")
            return

        if (cntrFreq < 70000000 or cntrFreq > 6000000000):
            WarningMessager.showWarning("Center frequency " + str(cntrFreq) +
                " is invalid. Please enter another value.")
            return
        if (sampFreq < 0 or sampFreq > 56000000):
            WarningMessager.showWarning("Sampling frequency " + str(sampFreq) +
                " is invalid. Please enter another value.")
            return
        if (sdrGain < 0 or sdrGain > 70):
            WarningMessager.showWarning("SDR gain" + str(sdrGain) +
                " is invalid. Please enter another value.")
            return

        addTargetWindow = AddTargetDialog(self.frm_targHolder, cntrFreq, sampFreq)
        addTargetWindow.exec_()

        # TODO: remove name
        name = addTargetWindow.name
        freq = addTargetWindow.freq

        if freq is None or not self.validateFrequency(freq):
            #WarningMessager.showWarning("Target frequency " + str(freq) +
                #" is invalid. Please enter another value.")
            return

        self.__root._mavModel.addFrequency(freq, self.__root.defaultTimeout)

        self.update()

    def connectionMade(self):
        '''
        Helper method to enable system settings buttons once connection is made
        '''

        self.btn_addTarget.setEnabled(True)
        self.btn_clearTargs.setEnabled(True)
        self.btn_submit.setEnabled(True)
        self.btn_advSettings.setEnabled(True)
        self.__root.statusWidget.updateGUIOptionVars()

    def disconnected(self):
        '''
        Helper method to disable system settings buttons once mavModel stops
        '''

        self.btn_addTarget.setEnabled(False)
        self.btn_clearTargs.setEnabled(False)
        self.btn_submit.setEnabled(False)
        self.btn_advSettings.setEnabled(False)
        self.__root._systemConnectionTab.updateText("System: No Connection")
