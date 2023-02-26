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
            "TGT_frequencies": [],
            "SDR_center_freq": None,
            "SDR_sampling_freq": None,
            "SDR_gain": None,
            "SDR_ping_width": None,
            "SDR_ping_snr": None,
            "SDR_ping_max": None,
            "SDR_ping_min": None,
            "GPS_mode": None,
            "GPS_device": None,
            "GPS_baud": None,
            "SYS_output_dir": None,
            "SYS_autostart": None
        }
        self.__create_widget()

    def update(self):
        '''
        Function to facilitate the updating of internal widget
        displays
        '''
        self.__update_widget() #add updated values

        # Repaint widgets and layouts
        self.widg_targ_holder.repaint()
        self.scroll_targ_holder.repaint()
        self.frm_targ_holder.activate()
        #CollapseFrame.repaint(self) // causes thread problems?
        self.__inner_frame.activate()


    def __update_widget(self):
        '''
        Function to update displayed values of target widgets
        '''
        if self.frm_targ_holder:
            while (self.frm_targ_holder.count() > 0):
                child = self.frm_targ_holder.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
        row_idx = 0
        self.targ_entries = {}
        if self.__root._mav_model is not None:
            cntr_freq = self.__root._mav_model.getOption('SDR_center_freq')
            samp_freq = self.__root._mav_model.getOption('SDR_sampling_freq')
            self.option_vars["SDR_center_freq"].setText(str(cntr_freq))
            self.option_vars["SDR_sampling_freq"].setText(str(samp_freq))
            self.frm_targ_holder.setVerticalSpacing(0)
            time.sleep(0.5)
            for freq in self.__root._mav_model.getFrequencies(self.__root.default_timeout):
                #Put in frm_targ_holder
                new = QHBoxLayout()
                freq_label = QLabel('Target %d' % (row_idx + 1))
                freq_variable = freq
                freq_entry = QLineEdit()
                val = QIntValidator(cntr_freq-samp_freq, cntr_freq+samp_freq)
                freq_entry.setValidator(val)
                freq_entry.setText(str(freq_variable))

                # Add new target to layout
                new.addWidget(freq_label)
                new.addWidget(freq_entry)
                new_widg = QWidget()
                new_widg.setLayout(new)
                self.frm_targ_holder.addRow(new_widg)


                self.targ_entries[freq] = [freq]
                row_idx += 1

    def __create_widget(self):
        '''
        Inner function to create widgets in the System Settings tab
        '''
        self.__inner_frame = QGridLayout()

        lbl_cntr_freq = QLabel('Center Frequency')

        lbl_samp_freq = QLabel('Sampling Frequency')

        lbl_sdr_gain = QLabel('SDR Gain')

        self.option_vars['SDR_center_freq'] = QLineEdit()


        self.option_vars['SDR_sampling_freq'] = QLineEdit()

        self.option_vars['SDR_gain'] = QLineEdit()

        self.frm_targ_holder = QFormLayout() # Layout that holds target widgets
        self.widg_targ_holder = QWidget()
        self.scroll_targ_holder = QScrollArea()
        self.scroll_targ_holder.setWidgetResizable(True)
        self.scroll_targ_holder.setWidget(self.widg_targ_holder)
        self.widg_targ_holder.setLayout(self.frm_targ_holder)

        row_idx = 0
        self.targ_entries = {}
        if self.__root._mav_model is not None:
            for freq in self.__root._mav_model.getFrequencies(self.__root.default_timeout):
                #Put in frm_targ_holder
                new = QHBoxLayout()
                freq_label = QLabel('Target %d' % (row_idx + 1))
                freq_variable = freq
                freq_entry = QLineEdit()
                cntr_freq = self.__root._mav_model.getOption('SDR_center_freq')
                samp_freq = self.__root._mav_model.getOption('SDR_sampling_freq')
                val = QIntValidator(cntr_freq-samp_freq, cntr_freq+samp_freq)
                freq_entry.setValidator(val)
                freq_entry.setText(freq_variable)

                new.addWidget(freq_label)
                new.addWidget(freq_entry)
                new_widg = QWidget()
                new_widg.setLayout(new)
                self.frm_targ_holder.addRow(new_widg)
                self.targ_entries[freq] = [freq]
                row_idx += 1

        # Add widgets to main layout: self.__inner_frame
        self.__inner_frame.addWidget(self.scroll_targ_holder, 4, 0, 1, 2)
        self.__inner_frame.addWidget(lbl_cntr_freq, 1, 0)
        self.__inner_frame.addWidget(lbl_samp_freq, 2, 0)
        self.__inner_frame.addWidget(lbl_sdr_gain, 3, 0)
        self.__inner_frame.addWidget(self.option_vars['SDR_center_freq'], 1, 1)
        self.__inner_frame.addWidget(self.option_vars['SDR_sampling_freq'], 2, 1)
        self.__inner_frame.addWidget(self.option_vars['SDR_gain'], 3, 1)

        self.btn_add_target = QPushButton('Add Target')
        self.btn_add_target.clicked.connect(self.add_target)
        self.btn_add_target.setEnabled(False)
        self.__inner_frame.addWidget(self.btn_add_target, 0, 0, 1, 2)
        self.btn_clear_targs = QPushButton('Clear Targets')
        self.btn_clear_targs.clicked.connect(self.clear_targets)
        self.btn_clear_targs.setEnabled(False)
        self.__inner_frame.addWidget(self.btn_clear_targs, 5, 0)

        self.btn_submit = QPushButton('Update')
        self.btn_submit.clicked.connect(self.__update_button_callback)
        self.btn_submit.setEnabled(False)
        self.__inner_frame.addWidget(self.btn_submit, 5, 1)

        self.btn_adv_settings = QPushButton('Expert & Debug Configuration')
        self.btn_adv_settings.clicked.connect(self.__advanced_settings)
        self.btn_adv_settings.setEnabled(False)
        self.__inner_frame.addWidget(self.btn_adv_settings, 6, 0, 1, 2)

        self.set_content_layout(self.__inner_frame)


    def clear_targets(self):
        '''
        Helper function to clear target frequencies from UI and
        MavMode
        '''
        self.__root._mav_model.setFrequencies(
            [], timeout=self.__root.default_timeout)
        self.update()

    def __advanced_settings(self):
        '''
        Helper function to open an ExpertSettingsDialog widget
        '''
        openSettings = ExpertSettingsDialog(self, self.option_vars)
        openSettings.exec_()

    def validate_frequency(self, var: int):
        '''
        Helper function to ensure frequencies are within an appropriate
        range
        Args:
            var: An integer value that is the frequency to be validated
        '''
        cntr_freq = self.__root._mav_model.getOption('SDR_center_freq')
        samp_freq = self.__root._mav_model.getOption('SDR_sampling_freq')
        if abs(var - cntr_freq) > samp_freq:
            return False
        return True

    def __update_button_callback(self):
        '''
        Internal callback to be called when the update button is
        pressed
        '''
        cntr_freq = int(self.option_vars['SDR_center_freq'].text())
        samp_freq = int(self.option_vars['SDR_sampling_freq'].text())

        target_frequencies = []
        for target_name in self.targ_entries:
            if not self.validate_frequency(self.targ_entries[target_name][0]):
                UserPopups.show_warning("Target frequency " + str(self.targ_entries[target_name][0]) + " is invalid. Please enter another value.")
                return
            target_freq = self.targ_entries[target_name][0]
            target_frequencies.append(target_freq)

        self.__root._mav_model.setFrequencies(
            target_frequencies, self.__root.default_timeout)

        self.submit_gui_option_vars(0x00)

        self.update_gui_option_vars()

    def update_gui_option_vars(self, scope=0, options=None):
        if options is not None:
            self.option_vars = options
        option_dict = self.__root._mav_model.getOptions(
            scope, timeout=self.__root.default_timeout)
        for option_name, option_value in option_dict.items():
            if option_name == 'GPS_mode' or option_name == 'SYS_autostart':
                try:
                    if option_value:
                        self.option_vars[option_name].setText('true')
                    else:
                        self.option_vars[option_name].setText('false')
                except AttributeError:
                    UserPopups.show_warning("Failed to update GUI option vars", "Unexpected Error")
                    print(option_name)
            else:
                try:
                    self.option_vars[option_name].setText(str(option_value))
                except AttributeError:
                    UserPopups.show_warning("Failed to update GUI option vars", "Unexpected Error")
                    print(option_name)
        self.update()

    def submit_gui_option_vars(self, scope: int):
        __base_option_keywords = ['SDR_center_freq',
                                'SDR_sampling_freq', 'SDR_gain']
        __exp_option_keywords = ['SDR_ping_width', 'SDR_ping_snr',
                               'SDR_ping_max', 'SDR_ping_min', 'SYS_output_dir']
        __eng_option_keywords = ['GPS_mode',
                               'GPS_baud', 'GPS_device', 'SYS_autostart']

        accepted_keywords = []
        if scope >= 0x00:
            accepted_keywords.extend(__base_option_keywords)
        if scope >= 0x01:
            accepted_keywords.extend(__exp_option_keywords)
        if scope >= 0xFF:
            accepted_keywords.extend(__eng_option_keywords)

        options = {}

        for keyword in accepted_keywords:
            if keyword == 'SYS_output_dir' or keyword == 'GPS_device':
                options[keyword] = self.option_vars[keyword].text()
            elif keyword == 'GPS_mode' or keyword == 'SYS_autostart':
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
        self.__root._mav_model.setOptions(
            timeout=self.__root.default_timeout, **options)

    def add_target(self):
        '''
        Internal function to facilitate users adding target frequencies
        '''
        try:
            cntr_freq = int(self.option_vars['SDR_center_freq'].text())
            samp_freq = int(self.option_vars['SDR_sampling_freq'].text())
            sdr_gain = float(self.option_vars['SDR_gain'].text())
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
        self.update_gui_option_vars()
        self.btn_add_target.setEnabled(True)
        self.btn_clear_targs.setEnabled(True)
        self.btn_submit.setEnabled(True)
        self.btn_adv_settings.setEnabled(True)
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
