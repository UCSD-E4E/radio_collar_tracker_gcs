
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot

from RctGcs.config import get_instance
from RctGcs.rctCore import (BASE_OPTIONS, ENG_OPTIONS, EXP_OPTIONS, MAVModel,
                            NoActiveModel, Options, base_options_keywords,
                            engineering_options_keywords,
                            expert_options_keywords)
from RctGcs.ui.option_vars import option_var_table, update_option_var_widgets
from RctGcs.ui.popups import AddTargetDialog, ExpertSettingsDialog, UserPopups


class CollapseFrame(QtWidgets.QWidget):
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
        self.toggle_button = QtWidgets.QToolButton(
            text=title, checkable=True, checked=False
        )
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(Qt.RightArrow)
        self.toggle_button.pressed.connect(self.on_pressed)

        self.content_area = QtWidgets.QWidget()
        self.content_area.setVisible(False)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)


    def update_text(self, text):
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

    def set_content_layout(self, layout):
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
        self.__root = root

        self.__inner_frame = None
        self.frm_targ_holder = None
        self.scroll_targ_holder = None
        self.widg_targ_holder = None
        self.targ_entries = {}

        self.option_vars = {
            Options.TGT_FREQUENCIES: [],
            Options.SDR_CENTER_FREQ: None,
            Options.SDR_SAMPLING_FREQ: None,
            Options.SDR_GAIN: None,
            Options.DSP_PING_WIDTH: None,
            Options.DSP_PING_SNR: None,
            Options.DSP_PING_MAX: None,
            Options.DSP_PING_MIN: None,
            Options.GPS_MODE: None,
            Options.GPS_DEVICE: None,
            Options.GPS_BAUD: None,
            Options.SYS_OUTPUT_DIR: None,
            Options.SYS_AUTOSTART: None
        }
        self.__create_widget()

    def update(self):
        '''
        Function to facilitate the updating of internal widget
        displays
        '''
        update_option_var_widgets()

        #CollapseFrame.repaint(self) // causes thread problems?
        self.__inner_frame.activate()

    def __create_widget(self):
        '''
        Inner function to create widgets in the System Settings tab
        '''
        self.__inner_frame = QtWidgets.QGridLayout()


        label, entry = option_var_table[Options.SDR_CENTER_FREQ].make_pair(None)
        self.__inner_frame.addWidget(label, 1, 0)
        self.__inner_frame.addWidget(entry, 1, 1)


        label, entry = option_var_table[Options.SDR_SAMPLING_FREQ].make_pair(None)
        self.__inner_frame.addWidget(label, 2, 0)
        self.__inner_frame.addWidget(entry, 2, 1)

        label, entry = option_var_table[Options.SDR_GAIN].make_pair(None)
        self.__inner_frame.addWidget(label, 3, 0)
        self.__inner_frame.addWidget(entry, 3, 1)
        
        label, entry = option_var_table[Options.TGT_FREQUENCIES].make_pair(None)
        self.__inner_frame.addWidget(label, 4, 0, 1, 2)
        self.__inner_frame.addWidget(entry, 5, 0, 1, 2)

        self.__submit_btn = QtWidgets.QPushButton(self)
        self.__submit_btn.setText('Update Settings')
        self.__submit_btn.clicked.connect(self.__update_button_callback)
        self.__submit_btn.setEnabled(False)
        self.__inner_frame.addWidget(self.__submit_btn, 6, 0, 1, 2)

        self.btn_adv_settings = QtWidgets.QPushButton('Expert & Debug Configuration')
        self.btn_adv_settings.clicked.connect(self.__advanced_settings)
        self.btn_adv_settings.setEnabled(False)
        self.__inner_frame.addWidget(self.btn_adv_settings, 7, 0, 1, 2)


        self.set_content_layout(self.__inner_frame)

        update_option_var_widgets()


    def __advanced_settings(self):
        '''
        Helper function to open an ExpertSettingsDialog widget
        '''
        openSettings = ExpertSettingsDialog(self, self.option_vars)
        openSettings.exec_()

    def validate_frequency(self, value: int) -> bool:
        '''
        Helper function to ensure frequencies are within an appropriate
        range
        Args:
            var: An integer value that is the frequency to be validated
        '''
        try:
            model = MAVModel.get_model()
        except NoActiveModel:
            return
        cntr_freq = model.getOption(Options.SDR_CENTER_FREQ)
        samp_freq = model.getOption(Options.SDR_SAMPLING_FREQ)
        if abs(value - cntr_freq) > samp_freq:
            return False
        return True

    def __update_button_callback(self):
        '''
        Internal callback to be called when the update button is
        pressed
        '''
        try:
            model = MAVModel.get_model()
        except NoActiveModel:
            return
        
        cntr_freq = option_var_table[Options.SDR_CENTER_FREQ]
        samp_freq = option_var_table[Options.SDR_SAMPLING_FREQ]
        sdr_gain = option_var_table[Options.SDR_GAIN]
        

        tgt_freq = option_var_table[Options.TGT_FREQUENCIES]
        target_frequencies = tgt_freq.get_value()

        default_timeout = get_instance().default_timeout
        try:
            model.setFrequencies(target_frequencies, default_timeout)
        except Exception:
            UserPopups.show_warning('Failed to set frequencies')
            return

        self.submit_gui_option_vars(0x00)

        update_option_var_widgets()


    def submit_gui_option_vars(self, scope: int):

        accepted_keywords = []
        if scope >= BASE_OPTIONS:
            accepted_keywords.extend(base_options_keywords)
        if scope >= EXP_OPTIONS:
            accepted_keywords.extend(expert_options_keywords)
        if scope >= ENG_OPTIONS:
            accepted_keywords.extend(engineering_options_keywords)

        options = {}

        for keyword in accepted_keywords:
            if keyword == Options.SYS_OUTPUT_DIR or keyword == Options.GPS_DEVICE:
                options[keyword] = self.option_vars[keyword].text()
            elif keyword == Options.GPS_MODE or keyword == Options.SYS_AUTOSTART:
                val = self.option_vars[keyword].text()
                if val == 'true':
                    options[keyword] = True
                else:
                    options[keyword] = False
            else:
                try:
                    options[keyword] = int(self.option_vars[keyword].text())
                except ValueError:
                    options[keyword] = float(self.option_vars[keyword].text())
        mav_model = MAVModel.get_model()
        default_timeout = get_instance().default_timeout
        mav_model.setOptions(timeout=default_timeout, **options)

    def add_target(self):
        '''
        Internal function to facilitate users adding target frequencies
        '''
        try:
            cntr_freq = int(self.option_vars[Options.SDR_CENTER_FREQ].text())
            samp_freq = int(self.option_vars[Options.SDR_SAMPLING_FREQ].text())
            sdr_gain = float(self.option_vars[Options.SDR_GAIN].text())
        except ValueError:
            UserPopups.show_warning("Please enter center and sampling frequences and SDR gain settings.")
            return

        if (cntr_freq < 70000000 or cntr_freq > 6000000000):
            UserPopups.show_warning("Center frequency " + str(cntr_freq) + \
                " is invalid. Please enter another value.")
            return
        if (samp_freq < 0 or samp_freq > 56000000):
            UserPopups.show_warning("Sampling frequency " + str(samp_freq) + \
                " is invalid. Please enter another value.")
            return
        if (sdr_gain < 0 or sdr_gain > 70):
            UserPopups.show_warning("SDR gain" + str(sdr_gain) + \
                " is invalid. Please enter another value.")
            return

        add_target_window = AddTargetDialog(self.frm_targ_holder, cntr_freq, samp_freq)
        add_target_window.exec_()

        # TODO: remove name
        name = add_target_window.name
        freq = add_target_window.freq

        if freq is None or not self.validate_frequency(freq):
            #UserPopups.show_warning("Target frequency " + str(freq) +
                #" is invalid. Please enter another value.")
            return

        self.__root._mav_model.addFrequency(freq, self.__root.default_timeout)

        self.update()

    def connection_made(self):
        '''
        Helper method to enable system settings buttons once connection is made
        '''
        self.update()
        self.btn_adv_settings.setEnabled(True)
        self.__submit_btn.setEnabled(True)
        self.__root.status_widget.update_gui_option_vars()

    def disconnected(self):
        '''
        Helper method to disable system settings buttons once mavModel stops
        '''
        self.btn_add_target.setEnabled(False)
        self.btn_clear_targs.setEnabled(False)
        self.btn_submit.setEnabled(False)
        self.btn_adv_settings.setEnabled(False)
        self.__root._system_connection_tab.update_text("System: No Connection")
