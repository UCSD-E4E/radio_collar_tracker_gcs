from pathlib import Path
from typing import Any, List, Optional

from PyQt5.QtCore import QRegExp, Qt, QTimer
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtWidgets import (QButtonGroup, QGridLayout, QHBoxLayout, QLabel,
                             QLineEdit, QMessageBox, QPushButton, QRadioButton,
                             QVBoxLayout, QWizard, QWizardPage)

from RctGcs.config import ConnectionMode, get_config_path, get_instance


class UserPopups:
    """
    Creates popup boxes for user display
    """
    def create_text_box(self, name: str, text: str) -> Any:
        '''
        Params:
            name: takes a sting that is the name of the text box
            text: takes a string that will be used as value for the text box.
        Returns:
            form: Text box QGridLayout
            line: QLineEdit line
        '''
        form = QGridLayout()
        form.setColumnStretch(0,0)

        label = QLabel(name)
        form.addWidget(label)

        line = QLineEdit()
        line.setText(text)

        # The text box will be formatted in a grid. addWidget allows
        # the box to be manipulated according to the column and row. (c,r)
        form.addWidget(line,0,1)
        return form, line

    def create_binary_radio_button(self, name: str, labels_list: List[str], condition: bool):
        '''
        Creates a binary radio button box. The box will only have two
            options to select and will check according to a boolean condition
        Params:
            name: takes a sting that is the name of the text box
            labels: takes an list of strings and reads the first 2 elements.
            It uses those two elements as labels for each radio button.
            condition: takes conditional returns as a boolean.
        Returns:
            form: Text box QGridLayout
            retval: QRadioButton
        '''
        form = QGridLayout()
        form.setColumnStretch(1,0)
        label = QLabel(name)
        form.addWidget(label)
        true_event = QRadioButton(labels_list[0])
        false_event = QRadioButton(labels_list[1])
        if condition:
            true_event.setChecked(True)
        else:
            false_event.setChecked(True)

        button = QButtonGroup(parent=form)
        button.setExclusive(True)
        button.addButton(true_event)
        button.addButton(false_event)
        form.addWidget(true_event,0,1, Qt.AlignLeft)
        form.addWidget(false_event,0,0,Qt.AlignCenter)
        return form, true_event

    def show_warning(self, text: str, title: str ="Warning"):
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

    def show_timed_warning(self, text: str, timeout: int, title: str ="Warning"):
        '''
        Creates timed warning popups
        Args:
            title: message header
            timeout: timeout in seconds
            text: message body
        '''
        
        msg = QMessageBox()
        QTimer.singleShot(timeout*1000, lambda : msg.done(0))
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
    def __init__(self, parent, option_vars):
        '''
        Creates a new ExpertSettingsDialog
        Args:
            parent: the parent widget of the dialog
            optionVars: Dictionary object of option variables
        '''
        super(ExpertSettingsDialog, self).__init__(parent)
        self.parent = parent
        self.addPage(ExpertSettingsDialogPage(self, option_vars))
        self.setWindowTitle('Expert/Engineering Settings')
        self.resize(640,480)

class ExpertSettingsDialogPage(QWizardPage):
    '''
    Custom DialogPage widget to facilitate user configured
    expert settings.
    '''
    def __init__(self, parent=None, option_vars=None):
        '''
        Creates a new ExpertSettingsDialogPage object
        Args:
            parent: An ExpertSettingsDialog object
            optionVars: Dictionary object of option variables
        '''
        super(ExpertSettingsDialogPage, self).__init__(parent)
        self.__parent = parent
        self.option_vars = option_vars
        self.user_pops = UserPopups()
        self.create_widget()
        # Configure member vars here
        self.__parent.parent.updateGUIOptionVars(0xFF, self.option_vars)

    def create_widget(self):
        '''
        Internal function to create widgets
        '''
        exp_settings_frame = QGridLayout()

        lbl_ping_width = QLabel('Expected Ping Width(ms)')
        exp_settings_frame.addWidget(lbl_ping_width, 0, 0)

        lbl_min_width_mult = QLabel('Min. Width Multiplier')
        exp_settings_frame.addWidget(lbl_min_width_mult, 1, 0)

        lbl_max_width_mult = QLabel('Max. Width Multiplier')
        exp_settings_frame.addWidget(lbl_max_width_mult, 2, 0)

        lbl_min_ping_snr = QLabel('Min. Ping SNR(dB)')
        exp_settings_frame.addWidget(lbl_min_ping_snr, 3, 0)

        lbl_gps_port = QLabel('GPS Port')
        exp_settings_frame.addWidget(lbl_gps_port, 4, 0)

        lbl_gps_baud_rate = QLabel('GPS Baud Rate')
        exp_settings_frame.addWidget(lbl_gps_baud_rate, 5, 0)

        lbl_output_dir = QLabel('Output Directory')
        exp_settings_frame.addWidget(lbl_output_dir, 6, 0)

        lbl_gps_mode = QLabel('GPS Mode')
        exp_settings_frame.addWidget(lbl_gps_mode, 7, 0)

        lbl_sys_auto_start = QLabel("SYS Autostart")
        exp_settings_frame.addWidget(lbl_sys_auto_start, 8, 0)

        self.option_vars['DSP_pingWidth'] = QLineEdit()
        exp_settings_frame.addWidget(self.option_vars['DSP_pingWidth'], 0, 1)

        self.option_vars['DSP_pingMin'] = QLineEdit()
        exp_settings_frame.addWidget(self.option_vars['DSP_pingMin'], 1, 1)

        self.option_vars['DSP_pingMax'] = QLineEdit()
        exp_settings_frame.addWidget(self.option_vars['DSP_pingMax'], 2, 1)

        self.option_vars['DSP_pingSNR'] = QLineEdit()
        exp_settings_frame.addWidget(self.option_vars['DSP_pingSNR'], 3, 1)

        self.option_vars['GPS_device'] = QLineEdit()
        exp_settings_frame.addWidget(self.option_vars['GPS_device'], 4, 1)

        self.option_vars['GPS_baud'] = QLineEdit()
        exp_settings_frame.addWidget(self.option_vars['GPS_baud'], 5, 1)

        self.option_vars['SYS_outputDir'] = QLineEdit()
        exp_settings_frame.addWidget(self.option_vars['SYS_outputDir'], 6, 1)

        self.option_vars['GPS_mode'] = QLineEdit()
        exp_settings_frame.addWidget(self.option_vars['GPS_mode'], 7, 1)

        self.option_vars['SYS_autostart'] = QLineEdit()
        exp_settings_frame.addWidget(self.option_vars['SYS_autostart'], 8, 1)

        btn_submit = QPushButton('submit')
        btn_submit.clicked.connect(self.submit)
        exp_settings_frame.addWidget(btn_submit, 9, 0, 1, 2)

        self.setLayout(exp_settings_frame)

    def validate_parameters(self):
        '''
        Inner function to validate parameters set
        '''
        return True # TODO: actual validation

    def submit(self):
        '''
        Inner function to submit enterred information
        '''
        if not self.validate_parameters():
            self.user_pops.show_warning(text="Entered information could not be validated")
            return
        self.__parent.parent.submitGUIOptionVars(0xFF)

class AddTargetDialog(QWizard):
    '''
    A Custom Dialog Widget to facilitate user-added target frequencies
    '''
    def __init__(self, parent, center_frequency: int, sampling_frequency: int):
        '''
        Creates a new AddTargetDialog
        Args:
            parent: the parent widget of the AddTargetDialog
            center_frequency: an integer frequency value
            sampling_frequency: an integer value to indicate sampling range
        '''
        QWizardPage.__init__(self)
        self.__parent = parent
        self.name = "filler"
        self.freq = 0
        self.center_frequency = center_frequency
        self.sampling_frequency = sampling_frequency
        self.page = AddTargetDialogPage(self, center_frequency, sampling_frequency)
        self.addPage(self.page)
        self.setWindowTitle('Add Target')
        self.resize(640,480)
        self.button(QWizard.FinishButton).clicked.connect(self.submit)
        self.user_pops = UserPopups()

    def validate(self):
        '''
        Helper Method ot validate input frequency
        '''
        return abs(int(self.page.targ_freq_entry.text()) -\
             self.center_frequency) <= self.sampling_frequency

    def submit(self):
        '''
        Internal function to submit newly added target frequency
        '''
        if not self.validate():
            self.user_pops.show_warning("You have entered an invalid target\
            frequency. Please try again.", "Invalid frequency")
            return
        self.name = self.page.targ_name_entry.text()
        self.freq = int(self.page.targ_freq_entry.text())

class AddTargetDialogPage(QWizardPage):
    '''
    Custom DialogPage widget to facilitate user-added target
    frequencies
    '''
    def __init__(self, parent, center_frequency: int, sampling_frequency: int):
        '''
        Creates a new AddTargetDialog
        Args:
            parent: the parent widget of the AddTargetDialog
            center_frequency: an integer frequency value
            sampling_frequency: an integer value to indicate sampling range
        '''
        QWizardPage.__init__(self, parent)
        self.__parent = parent
        self.targ_name_entry = None
        self.targ_freq_entry = None

        self.__center_freq = center_frequency
        self.__sampling_freq = sampling_frequency

        self.name = None
        self.freq = None

        self.__create_widget()

    def __create_widget(self):
        '''
        Internal function to create widgets
        '''
        regex_string  = QRegExp("[0-9]{30}")
        val = QRegExpValidator(regex_string)
        frm_target_settings = QGridLayout()

        lbl_target_name = QLabel('Target Name:')
        frm_target_settings.addWidget(lbl_target_name, 0, 0)

        #entr_targetName = QLineEdit()
        self.targ_name_entry = QLineEdit()
        frm_target_settings.addWidget(self.targ_name_entry, 0, 1)

        lbl_target_freq = QLabel('Target Frequency:')
        frm_target_settings.addWidget(lbl_target_freq, 1, 0)

        self.targ_freq_entry = QLineEdit()
        self.targ_freq_entry.setValidator(val)
        frm_target_settings.addWidget(self.targ_freq_entry, 1, 1)
        self.setLayout(frm_target_settings)

class ConnectionDialog(QWizard):
    '''
    Custom Dialog widget to facilitate connecting to the drone
    '''
    def __init__(self, transport_spec: Optional[str] = None):
        '''
        Creates new ConnectionDialog widget
        Args:
            port_val: the port value used
        '''
        super(ConnectionDialog, self).__init__()
        self.setWindowTitle('Connect Settings')
        self.page = ConnectionDialogPage(transport_spec=transport_spec)
        self.transport_spec = None
        self.addPage(self.page)
        self.resize(320, 120)    # width, height
        self.button(QWizard.FinishButton).clicked.connect(self.submit)

    def submit(self):
        '''
        Internal Function to submit user inputted connection settings
        '''
        self.transport_spec = self.page.port_entry.text()

class ConnectionDialogPage(QWizardPage):
    '''
    Custom DialogPage widget - Allows the user to configure
    settings to connect to the drone
    '''
    def __init__(self, transport_spec: Optional[str] = None):
        '''
        Creates a new ConnectionDialogPage
        Args:
            port_val: The port value used
        '''
        super(ConnectionDialogPage, self).__init__()
        self.__transport_spec_val = transport_spec # default value
        self.port_entry = None # default value
        self.__create_widget()

    def __create_widget(self):
        '''
        Internal function to create widgets
        '''
        frm_holder = QVBoxLayout()
        frm_holder.addStretch(1)

        frm_port = QHBoxLayout()
        frm_port.addStretch(1)

        lbl_port = QLabel('Connection Specifier')
        frm_port.addWidget(lbl_port)

        self.port_entry = QLineEdit()
        self.port_entry.setText(self.__transport_spec_val)
        frm_port.addWidget(self.port_entry)

        frm_holder.addLayout(frm_port)
        self.setLayout(frm_holder)

class ConfigDialog(QWizard):
    '''
    Custom Dialog widget to facilitate changing configuration settings
    '''
    def __init__(self, parent):
        '''
        Creates new ConfigDialog widget
        Args:
            parent: The parent widget of this ConfigDialog widget
        '''
        super(ConfigDialog, self).__init__()
        self.config = get_instance(get_config_path())

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
        self.config.qgis_prefix_path = Path(self.page.prefix_path[1].text())
        if self.page.prefix_set[1].isChecked():
            self.config.qgis_prefix_set = True
        else:
            self.config.qgis_prefix_set = False
        self.config.map_extent = (
            (float(self.page.lat_1[1].text()),float(self.page.lon_1[1].text())),
            (float(self.page.lat_2[1].text()),float(self.page.lon_2[1].text())) )
        self.config.connection_addr = self.page.address[1].text()
        self.config.connection_port = int(self.page.port_number[1].text())
        if self.page.drone_mode[1].isChecked():
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
        Creates a new ConfigDialogPage
        Args:
            parent: The parent widget of this page
        '''
        super(ConfigDialogPage, self).__init__()
        self.__parent = parent
        self.__create_widget()

    def __create_widget(self):
        '''
        Internal function to create widgets
        '''
        pop_up_box = UserPopups()
        frm_holder = QVBoxLayout()
        #----- Prefix Path
        self.prefix_path = pop_up_box.create_text_box('QGis Prefix Path',\
            str(self.__parent.config.qgis_prefix_path))
        #----- Prefix Set
        self.prefix_set = pop_up_box.create_binary_radio_button(
            'QGis Prefix Set', ['True', 'False'],
            self.__parent.config.qgis_prefix_set)
        #----- Lat 1
        self.lat_1 = pop_up_box.create_text_box(
                    'Lat 1', str(self.__parent.config.map_extent[0][0]))
        #----- Lat 2
        self.lat_2 = pop_up_box.create_text_box(
                    'Lat 2', str(self.__parent.config.map_extent[1][0]))
        #----- Lon 1
        self.lon_1 = pop_up_box.create_text_box(
                    'Lon 1', str(self.__parent.config.map_extent[0][1]))
        #----- Lon 2
        self.lon_2 = pop_up_box.create_text_box(
                    'Lon 2', str(self.__parent.config.map_extent[1][1]))
        #----- Addr
        self.address = pop_up_box.create_text_box(
                    'Addr', str(self.__parent.config.connection_addr))
        #----- Port
        self.port_number = pop_up_box.create_text_box(
                    'Port', str(self.__parent.config.connection_port))
        #----- Mode
        self.drone_mode = pop_up_box.create_binary_radio_button('Mode',
                    ['Drone', 'Tower'],
                    self.__parent.config.connection_mode == ConnectionMode.DRONE)
        #-----
        frm_holder.addLayout(self.prefix_path[0])
        frm_holder.addLayout(self.prefix_set[0])
        frm_holder.addLayout(self.lat_1[0])
        frm_holder.addLayout(self.lat_2[0])
        frm_holder.addLayout(self.lon_1[0])
        frm_holder.addLayout(self.lon_2[0])
        frm_holder.addLayout(self.address[0])
        frm_holder.addLayout(self.port_number[0])
        frm_holder.addLayout(self.drone_mode[0])

        self.setLayout(frm_holder)
