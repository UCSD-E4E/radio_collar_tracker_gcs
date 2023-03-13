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

    sb_width = 500
    default_timeout = 5
    default_port_val = 9000

    sig = pyqtSignal()

    connect_signal = pyqtSignal(int)
    disconnect_signal = pyqtSignal(int)

    mav_event_signal = pyqtSignal(rctCore.Events, int)

    def __init__(self):
        '''
        Creates the GCS Application Object
        '''
        super().__init__()
        self.__log = logging.getLogger('rctGCS.GCS')
        self.port_val = self.default_port_val
        self._transport = None
        self._mav_models = {}
        self._mav_model = None
        self._buttons = []
        self._system_connection_tab = None
        self.system_settings_widget = None
        self.__mission_status_text = "Start Recording"
        self.__mission_status_btn = None
        self.inner_freq_frame = None
        self.freq_elements = []
        self.targ_entries = {}
        self.map_control = None
        self.map_options = None
        self.map_display = None
        self.test_frame = None
        self.ping_sheet_created = False
        self.user_popups = UserPopups()
        self.config = config.Configuration(Path('gcsConfig.ini'))
        self.config.load()

        self.__create_widgets()
        for button in self._buttons:
            button.config(state='disabled')

        self.queue = q.Queue()
        self.sig.connect(self.execute_inmain, Qt.QueuedConnection)

        self.connect_signal.connect(self.connection_slot)
        self.disconnect_signal.connect(self.disconnect_slot)

    def execute_inmain(self):
        while not self.queue.empty():
            (fn, coord, frequency, num_pings) = self.queue.get()
            fn(coord, frequency, num_pings)

    def __mav_event_handler(self, event, id):
        if event == rctCore.Events.Heartbeat:
            self.__heartbeat_callback(id)
        if event == rctCore.Events.Exception:
            self.__handle_remote_exception(id)
        if event == rctCore.Events.VehicleInfo:
            self.__handle_vehicle_info(id)
        if event == rctCore.Events.NewPing:
            self.__handle_new_ping(id)
        if event == rctCore.Events.NewEstimate:
            self.__handle_new_estimate(id)
        if event == rctCore.Events.ConeInfo:
            self.__handle_new_cone(id)

    def __register_model_callbacks(self, id):
        mav_model = self._mav_models[id]
        event_types = [rctCore.Events.Heartbeat, rctCore.Events.Exception,
                    rctCore.Events.VehicleInfo, rctCore.Events.NewPing,
                    rctCore.Events.NewEstimate, rctCore.Events.ConeInfo]
        for event_type in event_types:
            mav_model.registerCallback(event_type,
            partial(self.mav_event_signal.emit, event_type, id))

    def __start_transport(self):

        if self._transport is not None and self._transport.isOpen():
            self._transport.close()
        self.mav_event_signal.connect(self.__mav_event_handler)
        if self.config.connection_mode == config.ConnectionMode.TOWER:
            self._transport = RCTTCPServer(self.port_val, self.connection_handler)
            self._transport.open()
        else:
            attempts = 5
            retry_time = 5
            for i in range(attempts):
                try:
                    self._transport = RCTTCPClient(addr=self.addr_val, port=self.port_val)
                    self.connection_handler(self._transport, 0)
                    return
                except ConnectionRefusedError:
                    self.user_popups.show_timed_warning(text="Trying to reconnect. Attempt {} out of 5.\
                                                        \nRetrying after {} seconds.".format(str(i), retry_time), timeout=retry_time)
                    self._transport.close()

            self.user_popups.show_warning("Failure to connect:\nPlease ensure server is running.")
            return

    def connection_handler(self, connection, id):
        comms = gcsComms(connection, partial(self.__disconnect_handler, id))
        model = rctCore.MAVModel(comms)
        model.start()
        self._mav_models[id] = model
        if self._mav_model is None:
            self._mav_model = model
            self.__register_model_callbacks(id)

        self.connect_signal.emit(id)

    def connection_slot(self, id):
        '''
        Handle GUI updates in main thread by connecting pyqt signal to the
        remaining connection work
        '''
        self.update_connections_label()
        self.system_settings_widget.connection_made()
        self.__mission_status_btn.setEnabled(True)
        self.__btn_export_all.setEnabled(True)
        self.__btn_precision.setEnabled(True)
        self.__btn_heat_map.setEnabled(True)
        self.__log.info('Connected {}'.format(id))

    def __disconnect_handler(self, id):
        mav_model = self._mav_models[id]
        del self._mav_models[id]
        if mav_model == self._mav_model:
            self._mav_model = None

        self.disconnect_signal.emit(id)

    def disconnect_slot(self, id):
        '''
        Handle GUI updates in main thread by connecting pyqt signal to the
        remaining disconnection work
        '''
        if len(self._mav_models) == 0:
            self.system_settings_widget.disconnected()
            self.__mission_status_btn.setEnabled(False)
            self.__btn_export_all.setEnabled(False)
            self.__btn_precision.setEnabled(False)
            self.__btn_heat_map.setEnabled(False)
        self.update_connections_label()
        self.__log.info('Disconnected {}'.format(id))

    def update_connections_label(self):
        num_connections = len(self._mav_models)
        label = "System: No Connection"
        if num_connections == 1:
            label = "System: 1 Connection"
        elif num_connections > 1:
            label = "System: {} Connections".format(num_connections)
        self._system_connection_tab.update_text(label)

    def __change_model(self, id: int):
        '''
        Changing the selected _mav_model
        '''
        self._mav_model = self._mav_models[id]
        self.system_settings_widget.connection_made()

    def __change_model_by_index(self, index: int):
        '''
        Changing the selected _mav_model by index
        '''
        if index < 0 or index > len(self._mav_models):
            return
        try:
            self.__change_model(list(self._mav_models.keys())[index])
        except:
            print('Failed to change Model to {}'.format(index))
            self.__use_default_model()

    def __use_default_model(self):
        '''
        Using the first model as the default if possible
        '''
        try:
            if len(self._mav_models) > 0:
                self.__change_model(list(self._mav_models.keys())[0])
        except:
            self._mav_model = None

    def mainloop(self, n=0):
        '''
        Main Application Loop
        :param n:
        :type n:
        '''

    def __heartbeat_callback(self, id):
        '''
        Internal Heartbeat callback
        '''
        self.status_widget.update()

    def __start_command(self):
        '''
        Internal callback to send the start command
        '''

    def __stop_command(self):
        '''
        Internal callback to send the stop command
        '''

    def __no_heartbeat(self):
        '''
        Internal callback for the no heartbeat state
        '''
        for button in self._buttons:
            button.config(state='disabled')
        self.user_popups.show_warning("No Heartbeats Received")

    def __handle_new_estimate(self, id):
        '''
        Internal callback to handle when a new estimate is received
        '''
        mav_model = self._mav_models[id]
        freq_list = mav_model.EST_mgr.getFrequencies()
        for frequency in freq_list:
            params, stale, res = mav_model.EST_mgr.getEstimate(frequency)

            zone, let = mav_model.EST_mgr.getUTMZone()
            coord = utm.to_latlon(params[0], params[1], zone, let)

            num_pings = mav_model.EST_mgr.getnum_pings(frequency)

            if self.map_display is not None:
                self.map_display.plot_estimate(coord, frequency)
                #self.queue.put( (self.map_display.plot_precision, coord, frequency, num_pings) )
                #self.sig.emit()
                #self.map_display.plot_precision(coord, frequency, num_pings)

            if self.map_options is not None:
                self.map_options.est_distance(coord, stale, res)


    def __handle_new_ping(self, id):
        '''
        Internal callback to handle when a new ping is received
        '''
        mav_model = self._mav_models[id]
        freq_list = mav_model.EST_mgr.getFrequencies()
        for frequency in freq_list:
            last = mav_model.EST_mgr.getPings(frequency)[-1].tolist()
            zone, let = mav_model.EST_mgr.getUTMZone()
            u = (last[0], last[1], zone, let)
            coord = utm.to_latlon(*u)
            power = last[3]

            if self.map_display is not None:
                self.map_display.plot_ping(coord, power)

    def __handle_vehicle_info(self, id):
        '''
        Internal Callback for Vehicle Info
        '''
        mav_model = self._mav_models[id]
        if mav_model == None:
            return
        last = list(mav_model.state['VCL_track'])[-1]
        coord = mav_model.state['VCL_track'][last]

        mav_model.EST_mgr.addVehicleLocation(coord)

        if self.map_display is not None:
            self.map_display.plot_vehicle(id, coord)

    def __handle_new_cone(self, id):
        '''
        Internal callback to handle new cone info
        '''
        mav_model = self._mav_models[id]
        if mav_model == None:
            return

        recent_cone = list(mav_model.state['CONE_track'])[-1]
        cone = mav_model.state['CONE_track'][recent_cone]

        if self.map_display is not None:
            self.map_display.plot_cone(cone)

    def __handle_remote_exception(self, id):
        '''
        Internal callback for an exception message
        '''
        mav_model = self._mav_models[id]
        self.user_popups.show_warning('An exception has occured!\n%s\n%s' % (
            mav_model.lastException[0], mav_model.lastException[1]))

    def __start_stop_mission(self):
        # State machine for start recording -> stop recording
        if self._mav_model == None:
            return

        if self.__mission_status_btn.text() == 'Start Recording':
            self.__mission_status_btn.setText('Stop Recording')
            self._mav_model.startMission(timeout=self.default_timeout)
        else:
            self.__mission_status_btn.setText('Start Recording')
            self._mav_model.stopMission(timeout=self.default_timeout)

    def __update_status(self): # TODO: this isn't getting used and doesn't seem to work???
        '''
        Internal callback for status variable update
        '''
        for button in self._buttons:
            button.config(state='normal')
        self.progress_bar['value'] = 0
        sdr_status = self._mav_model.STS_sdr_status
        dir_status = self._mav_model.STS_dir_status
        gps_status = self._mav_model.STS_gps_status
        sys_status = self._mav_model.STS_sys_status
        sw_status = self._mav_model.STS_sw_status

        sdr_map = {
            self._mav_model.SDR_INIT_STATES.find_devices: ('SDR: Searching for devices', 'yellow'),
            self._mav_model.SDR_INIT_STATES.wait_recycle: ('SDR: Recycling!', 'yellow'),
            self._mav_model.SDR_INIT_STATES.usrp_probe: ('SDR: Initializing SDR', 'yellow'),
            self._mav_model.SDR_INIT_STATES.rdy: ('SDR: Ready', 'green'),
            self._mav_model.SDR_INIT_STATES.fail: ('SDR: Failed!', 'red')
        }

        try:
            self.sdr_status_label.config(
                text=sdr_map[sdr_status][0], bg=sdr_map[sdr_status][1])
        except KeyError:
            self.sdr_status_label.config(
                text='SDR: NULL', bg='red')

        dir_map = {
            self._mav_model.OUTPUT_DIR_STATES.get_output_dir: ('DIR: Searching', 'yellow'),
            self._mav_model.OUTPUT_DIR_STATES.check_output_dir: ('DIR: Checking for mount', 'yellow'),
            self._mav_model.OUTPUT_DIR_STATES.check_space: ('DIR: Checking for space', 'yellow'),
            self._mav_model.OUTPUT_DIR_STATES.wait_recycle: ('DIR: Recycling!', 'yellow'),
            self._mav_model.OUTPUT_DIR_STATES.rdy: ('DIR: Ready', 'green'),
            self._mav_model.OUTPUT_DIR_STATES.fail: ('DIR: Failed!', 'red'),
        }

        try:
            self.dir_status_label.config(
                text=dir_map[dir_status][0], bg=dir_map[dir_status][1])
        except KeyError:
            self.dir_status_label.config(text='DIR: NULL', bg='red')

        gps_map = {
            self._mav_model.GPS_STATES.get_tty: {'text': 'GPS: Getting TTY Device', 'bg': 'yellow'},
            self._mav_model.GPS_STATES.get_msg: {'text': 'GPS: Waiting for message', 'bg': 'yellow'},
            self._mav_model.GPS_STATES.wait_recycle: {'text': 'GPS: Recycling', 'bg': 'yellow'},
            self._mav_model.GPS_STATES.rdy: {'text': 'GPS: Ready', 'bg': 'green'},
            self._mav_model.GPS_STATES.fail: {
                'text': 'GPS: Failed!', 'bg': 'red'}
        }

        try:
            self.gps_status_label.config(**gps_map[gps_status])
        except KeyError:
            self.gps_status_label.config(text='GPS: NULL', bg='red')

        sys_map = {
            self._mav_model.RCT_STATES.init: {'text': 'SYS: Initializing', 'bg': 'yellow'},
            self._mav_model.RCT_STATES.wait_init: {'text': 'SYS: Initializing', 'bg': 'yellow'},
            self._mav_model.RCT_STATES.wait_start: {'text': 'SYS: Ready for start', 'bg': 'green'},
            self._mav_model.RCT_STATES.start: {'text': 'SYS: Starting', 'bg': 'blue'},
            self._mav_model.RCT_STATES.wait_end: {'text': 'SYS: Running', 'bg': 'blue'},
            self._mav_model.RCT_STATES.finish: {'text': 'SYS: Stopping', 'bg': 'blue'},
            self._mav_model.RCT_STATES.fail: {'text': 'SYS: Failed!', 'bg': 'red'},
        }

        try:
            self.sys_status_label.config(**sys_map[sys_status])
        except KeyError:
            self.sys_status_label.config(text='SYS: NULL', bg='red')

        if sw_status == 0:
            self.sw_status_label.config(text='SW: OFF', bg='yellow')
        elif sw_status == 1:
            self.sw_status_label.config(text='SW: ON', bg='green')
        else:
            self.sw_status_label.config(text='SW: NULL', bg='red')

    def export_all(self):
        '''
        Exports pings, vehcle path, and settings as json file
        '''
        final = {}

        if self.map_display is not None:
            vehicle_path = self._mav_model.EST_mgr.getVehiclePath()
            ping_dict = {}
            vehicle_dict = {}
            ind_ping = 0
            ind_path = 0
            freq_list = self._mav_model.EST_mgr.getFrequencies()
            for frequency in freq_list:
                pings = self._mav_model.EST_mgr.getPings(frequency)
                for ping_array in pings:
                    ping_list = ping_array.tolist()
                    zone, let = self._mav_model.EST_mgr.getUTMZone()
                    u = (ping_list[0], ping_list[1], zone, let)
                    coord = utm.to_latlon(*u)
                    amp = ping_list[3]
                    new_ping = {}
                    new_ping['Frequency'] = frequency
                    new_ping['Coordinate'] = coord
                    new_ping['Amplitude'] = amp
                    ping_dict[ind_ping] = new_ping
                    ind_ping = ind_ping + 1
            for coord in vehicle_path:
                new_coord = {}
                new_coord['Coordinate'] = (coord[0], coord[1])
                vehicle_dict[ind_path] = new_coord
                ind_path = ind_path + 1

            final['Pings'] = ping_dict
            final['Vehicle Path'] = vehicle_dict

        if self.system_settings_widget is not None:
            option_vars = self.system_settings_widget.option_vars
            option_dict = {}
            for key in option_vars.keys():
                if key == "TGT_frequencies":
                    option_dict[key] = option_vars[key]
                elif option_vars[key] is not None:
                    option_dict[key] = option_vars[key].text()

            final['System Settings'] = option_dict

        if self._mav_model is not None:
            var_dict = self._mav_model.state
            new_var_dict = {}

            for key in var_dict.keys():
                if ((key == 'STS_sdr_status') or (key == 'STS_dir_status') or
                    (key == 'STS_gps_status') or (key == 'STS_sys_status')):
                    temp = {}
                    temp['name'] = var_dict[key].name
                    temp['value'] = var_dict[key].value
                    new_var_dict[key] = temp
                elif(key == 'VCL_track'):
                    pass
                else:
                    new_var_dict[key] = var_dict[key]


            final['States'] = new_var_dict

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
        if self.map_display is not None:
            ext = trans.transformBoundingBox(self.map_display.canvas.extent())
            lat1 = ext.yMaximum()
            lon1 = ext.xMinimum()
            lat2 = ext.yMinimum()
            lon2 = ext.xMaximum()


            with get_instance(Path('gcsConfig.ini')) as config:
                config.map_extent = (
                    (lat1, lon1),
                    (lat2, lon2)
                )

        for id in self._mav_models:
            mav_model = self._mav_models[id]
            mav_model.stop()
        self._mav_models = {}
        self._mav_model = None
        if self._transport is not None and self._transport.isOpen():
            self._transport.close()
        self._transport = None
        super().closeEvent(event)

    def __handle_connect_input(self):
        '''
        Internal callback to connect GCS to drone
        '''
        connection_dialog = ConnectionDialog(self.port_val, self)
        connection_dialog.exec_()

        if connection_dialog.port_val is None or \
            (connection_dialog.port_val == self.port_val and \
            len(self._mav_models) > 1):
            return

        self.port_val = connection_dialog.port_val
        if self.config.connection_mode == ConnectionMode.DRONE:
            self.addr_val = connection_dialog.addr_val
        self.__start_transport()

    def __handle_config_input(self):
        '''
        Internal callback to connect GCS to drone
        '''
        connection_dialog = ConfigDialog(self)
        connection_dialog.exec_()

    def set_map(self, map_widget):
        '''
        Function to set the map_display widget
        Args:
            map_widget: A MapWidget object
        '''
        self.map_display = map_widget

    def __create_widgets(self):
        '''
        Internal helper to make GUI widgets
        '''
        holder = QGridLayout()
        centr_widget = QFrame()
        self.setCentralWidget(centr_widget)

        self.setWindowTitle('RCT GCS')
        frm_side_control = QScrollArea()

        content = QWidget()
        frm_side_control.setWidget(content)
        frm_side_control.setWidgetResizable(True)

        #wlay is the layout that holds all tabs
        wlay = QVBoxLayout(content)

        # SYSTEM TAB
        self._system_connection_tab = CollapseFrame(title='System: No Connection')
        self._system_connection_tab.resize(self.sb_width, 400)
        lay_sys = QVBoxLayout()
        btn_setup = QPushButton("Connection Settings")
        btn_setup.resize(self.sb_width, 100)
        btn_setup.clicked.connect(self.__handle_connect_input)
        self.model_select = QComboBox()
        self.model_select.resize(self.sb_width, 100)
        self.model_select.currentIndexChanged.connect(self.__change_model_by_index)
        self.model_select.hide()
        lay_sys.addWidget(btn_setup)
        lay_sys.addWidget(self.model_select)

        self._system_connection_tab.set_content_layout(lay_sys)

        # COMPONENTS TAB
        self.status_widget = StatusDisplay(frm_side_control, self)

        # DATA DISPLAY TOOLS
        self.map_options = MapOptions()
        self.map_options.resize(300, 100)
        self.map_control = MapControl(frm_side_control, holder,
                self.map_options, self)

        # SYSTEM SETTINGS
        self.system_settings_widget = SystemSettingsControl(self)
        self.system_settings_widget.resize(self.sb_width, 400)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.system_settings_widget)

        self.upgrade_display = UpgradeDisplay(content, self)
        self.upgrade_display.resize(self.sb_width, 400)

        # CONFIG TAB
        self._config_tab = CollapseFrame(title='Configuration Settings')
        self._config_tab.resize(self.sb_width, 400)
        lay_config = QVBoxLayout()
        btn_config = QPushButton("Edit Configuration Settings")
        btn_config.resize(self.sb_width, 100)
        btn_config.clicked.connect(self.__handle_config_input)
        self.config_select = QComboBox()
        self.config_select.resize(self.sb_width, 100)
        self.config_select.hide()
        lay_config.addWidget(btn_config)
        lay_config.addWidget(self.config_select)

        self._config_tab.set_content_layout(lay_config)

        # START PAYLOAD RECORDING
        self.__mission_status_btn = QPushButton(self.__mission_status_text)
        self.__mission_status_btn.setEnabled(False)
        self.__mission_status_btn.clicked.connect(self.__start_stop_mission)

        self.__btn_export_all = QPushButton('Export Info')
        self.__btn_export_all.setEnabled(False)
        self.__btn_export_all.clicked.connect(self.export_all)

        self.__btn_precision = QPushButton('Do Precision')
        self.__btn_precision.setEnabled(False)
        self.__btn_precision.clicked.connect(self.__do_precision)

        self.__btn_heat_map = QPushButton('Display Heatmap')
        self.__btn_heat_map.setEnabled(False)
        self.__btn_heat_map.clicked.connect(self.__do_display_heatmap)

        wlay.addWidget(self._system_connection_tab)
        wlay.addWidget(self.status_widget)
        wlay.addWidget(self.map_control)
        wlay.addWidget(self.system_settings_widget)
        wlay.addWidget(self.upgrade_display)
        wlay.addWidget(self._config_tab)
        wlay.addWidget(self.__mission_status_btn)
        wlay.addWidget(self.__btn_export_all)
        wlay.addWidget(self.__btn_precision)
        wlay.addWidget(self.__btn_heat_map)

        wlay.addStretch()
        content.resize(self.sb_width, 400)
        frm_side_control.setMinimumWidth(self.sb_width)
        holder.addWidget(frm_side_control, 0, 0, alignment=Qt.AlignLeft)
        holder.addWidget(self.map_options, 0, 4, alignment=Qt.AlignTop)
        centr_widget.setLayout(holder)
        self.resize(1800, 1100)
        self.show()

    def __do_display_heatmap(self):
        if self.map_display:
            self.map_display.set_up_heat_map
        else:
            raise RuntimeError('No map loaded')

    def __do_precision(self):
        # todo: add modular frequencies
        self._mav_model.EST_mgr.doPrecisions(173500000)

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

        self.__inner_frame = None

        self.file_name = None

        self.__create_widget()
        self.user_pops = UserPopups()

    def update(self):
        self.update_gui_option_vars()

    def __create_widget(self):
        '''
        Inner function to create internal widgets
        '''
        self.__inner_frame = QGridLayout()

        file_lbl = QLabel('Selected File:')
        self.__inner_frame.addWidget(file_lbl, 1, 0)

        self.file_name = QLineEdit()
        self.__inner_frame.addWidget(self.file_name, 1, 1)

        browse_file_btn = QPushButton('Browse for Upgrade File')
        browse_file_btn.clicked.connect(self.file_dialog)
        self.__inner_frame.addWidget(browse_file_btn, 2, 0)

        upgrade_btn = QPushButton('Upgrade')
        upgrade_btn.clicked.connect(self.send_upgrade_file)
        self.__inner_frame.addWidget(upgrade_btn, 3, 0)


        self.set_content_layout(self.__inner_frame)

    def file_dialog(self):
        '''
        Opens a dialog to allow the user to indicate a file
        '''
        file_name = QFileDialog.getOpenFileName()
        if file_name is None:
            return
        self.file_name.setText(file_name[0])

    def send_upgrade_file(self):
        '''
        Inner function to send a user specified upgrade file to the mav_model
        '''
        try:
            file = open(self.file_name.text(), "rb")
        except FileNotFoundError:
            self.user_pops.show_warning("Please choose a valid file.")
            return
        byte_stream = file.read()
        self.__root._mav_model.sendUpgradePacket(byte_stream)

    def update_gui_option_vars(self):
        pass

class StatusDisplay(CollapseFrame):
    '''
    Custom widget to display system status
    '''
    def __init__(self, parent, root: GCS):
        CollapseFrame.__init__(self, 'Components')

        self.__parent = parent
        self.__root = root
        self.component_status_widget = None

        self.__inner_frame = None

        self.status_label = None

        self.__create_widget()

    def update(self):
        CollapseFrame.update(self)
        self.update_gui_option_vars()

    def __create_widget(self):
        '''
        Inner funciton to create internal widgets
        '''
        self.__inner_frame = QGridLayout()

        lbl_overall_status = QLabel('Status:')
        self.__inner_frame.addWidget(lbl_overall_status, 1, 0)

        entr_overall_status = QLabel('')
        self.__inner_frame.addWidget(entr_overall_status, 1, 1)

        self.component_status_widget = ComponentStatusDisplay(root=self.__root)
        h1 = self.component_status_widget.inner_frame.sizeHint().height()
        self.__inner_frame.addWidget(self.component_status_widget, 2, 0, 1, 2)

        self.status_label = entr_overall_status
        h2 = self.__inner_frame.sizeHint().height()
        h3 = self.toggle_button.sizeHint().height()


        self.content_height = h1 + h2 + h3 + h3
        self.set_content_layout(self.__inner_frame)

    def update_gui_option_vars(self, scope=0):
        var_dict = self.__root._mav_model.state

        sdr_status = var_dict["STS_sdr_status"]
        dir_status = var_dict["STS_dir_status"]
        gps_status = var_dict["STS_gps_status"]
        sys_status = var_dict["STS_sys_status"]
        sw_status = var_dict["STS_sw_status"]

        if sys_status == rctCore.RCT_STATES.finish:
            self.status_label.setText('Stopping')
            self.status_label.setStyleSheet("background-color: red")
        elif sdr_status == rctCore.SDR_INIT_STATES.fail or \
            dir_status == rctCore.OUTPUT_DIR_STATES.fail or \
            gps_status == rctCore.EXTS_STATES.fail or \
            sys_status == rctCore.RCT_STATES.fail or \
            (sw_status != 0 and sw_status != 1):
            self.status_label.setText('Failed')
            self.status_label.setStyleSheet("background-color: red")
        elif sys_status == rctCore.RCT_STATES.start or \
            sys_status == rctCore.RCT_STATES.wait_end:
            self.status_label.setText('Running')
            self.status_label.setStyleSheet("background-color: green")
        elif sdr_status == rctCore.SDR_INIT_STATES.rdy and \
            dir_status == rctCore.OUTPUT_DIR_STATES.rdy and \
            gps_status == rctCore.EXTS_STATES.rdy and \
            sys_status == rctCore.RCT_STATES.wait_start and sw_status == 1:
            self.status_label.setText('Idle')
            self.status_label.setStyleSheet("background-color: yellow")
        else:
            self.status_label.setText('Not Connected')
            self.status_label.setStyleSheet("background-color: yellow")

        self.component_status_widget.update()

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
        self.user_pops = UserPopups()
        self.sdr_map = {
            "SDR_INIT_STATES.find_devices": {'text': 'SDR: Searching for devices', 'bg':'yellow'},
            "SDR_INIT_STATES.wait_recycle": {'text':'SDR: Recycling!', 'bg':'yellow'},
            "SDR_INIT_STATES.usrp_probe": {'text':'SDR: Initializing SDR', 'bg':'yellow'},
            "SDR_INIT_STATES.rdy": {'text':'SDR: Ready', 'bg':'green'},
            "SDR_INIT_STATES.fail": {'text':'SDR: Failed!', 'bg':'red'}
        }

        self.dir_map = {
            "OUTPUT_DIR_STATES.get_output_dir": {'text':'DIR: Searching', 'bg':'yellow'},
            "OUTPUT_DIR_STATES.check_output_dir": {'text':'DIR: Checking for mount', 'bg':'yellow'},
            "OUTPUT_DIR_STATES.check_space": {'text':'DIR: Checking for space', 'bg':'yellow'},
            "OUTPUT_DIR_STATES.wait_recycle": {'text':'DIR: Recycling!', 'bg':'yellow'},
            "OUTPUT_DIR_STATES.rdy": {'text':'DIR: Ready', 'bg':'green'},
            "OUTPUT_DIR_STATES.fail": {'text':'DIR: Failed!', 'bg':'red'},
        }

        self.gps_map = {
            "EXTS_STATES.get_tty": {'text': 'GPS: Getting TTY Device', 'bg': 'yellow'},
            "EXTS_STATES.get_msg": {'text': 'GPS: Waiting for message', 'bg': 'yellow'},
            "EXTS_STATES.wait_recycle": {'text': 'GPS: Recycling', 'bg': 'yellow'},
            "EXTS_STATES.rdy": {'text': 'GPS: Ready', 'bg': 'green'},
            "EXTS_STATES.fail": {'text': 'GPS: Failed!', 'bg': 'red'}
        }

        self.sys_map = {
            "RCT_STATES.init": {'text': 'SYS: Initializing', 'bg': 'yellow'},
            "RCT_STATES.wait_init": {'text': 'SYS: Initializing', 'bg': 'yellow'},
            "RCT_STATES.wait_start": {'text': 'SYS: Ready for start', 'bg': 'green'},
            "RCT_STATES.start": {'text': 'SYS: Starting', 'bg': 'blue'},
            "RCT_STATES.wait_end": {'text': 'SYS: Running', 'bg': 'blue'},
            "RCT_STATES.finish": {'text': 'SYS: Stopping', 'bg': 'blue'},
            "RCT_STATES.fail": {'text': 'SYS: Failed!', 'bg': 'red'},
        }

        self.sw_map = {
            '0': {'text': 'SW: OFF', 'bg': 'yellow'},
            '1': {'text': 'SW: ON', 'bg': 'green'},
        }

        self.comp_dict = {
            "STS_sdr_status": self.sdr_map,
            "STS_dir_status": self.dir_map,
            "STS_gps_status": self.gps_map,
            "STS_sys_status": self.sys_map,
            "STS_sw_status": self.sw_map,
        }

        self.__root = root
        self.inner_frame = None
        self.status_labels = {}
        self.__create_widget()

    def update(self):
        self.update_gui_option_vars()

    def __create_widget(self):
        '''
        Inner Function to create internal widgets
        '''
        self.inner_frame = QGridLayout()

        lbl_sdr_status = QLabel('SDR Status')
        self.inner_frame.addWidget(lbl_sdr_status, 1, 0)

        lbl_dir_status = QLabel('Storage Status')
        self.inner_frame.addWidget(lbl_dir_status, 2, 0)

        lbl_gps_status = QLabel('GPS Status')
        self.inner_frame.addWidget(lbl_gps_status, 3, 0)

        lbl_sys_status = QLabel('System Status')
        self.inner_frame.addWidget(lbl_sys_status, 4, 0)

        lbl_sw_status = QLabel('Software Status')
        self.inner_frame.addWidget(lbl_sw_status, 5, 0)

        entr_sdr_status = QLabel('')
        self.inner_frame.addWidget(entr_sdr_status, 1, 1)

        entr_dir_status = QLabel('')
        self.inner_frame.addWidget(entr_dir_status, 2, 1)

        entr_gps_status = QLabel('')
        self.inner_frame.addWidget(entr_gps_status, 3, 1)

        entr_sys_status = QLabel('')
        self.inner_frame.addWidget(entr_sys_status, 4, 1)

        entr_sw_status = QLabel('')
        self.inner_frame.addWidget(entr_sw_status, 5, 1)

        self.status_labels["STS_sdr_status"] = entr_sdr_status
        self.status_labels["STS_dir_status"] = entr_dir_status
        self.status_labels["STS_gps_status"] = entr_gps_status
        self.status_labels["STS_sys_status"] = entr_sys_status
        self.status_labels["STS_sw_status"] = entr_sw_status
        self.set_content_layout(self.inner_frame)

    def update_gui_option_vars(self, scope=0):
        var_dict = self.__root._mav_model.state
        for var_name, var_value in var_dict.items():
            try:
                if var_name in self.comp_dict:
                    config_dict = self.comp_dict[var_name]
                    if str(var_value) in config_dict:
                        config_opts = config_dict[str(var_value)]
                        if var_name in self.status_labels:
                            self.status_labels[var_name].setText(config_opts['text'])
                        style = "background-color: %s" % config_opts['bg']
                        if var_name in self.status_labels:
                            self.status_labels[var_name].setStyleSheet(style)
            except KeyError:
                self.user_pops.show_warning("Failed to update GUI option vars", "Unexpected Error")
                continue

class MapControl(CollapseFrame):
    '''
    Custom Widget Class to facilitate Map Loading
    '''
    def __init__(self, parent, holder, map_options, root: GCS):
        CollapseFrame.__init__(self, title='Map Display Tools')
        self.__parent = parent
        self.__root = root
        self.__map_options = map_options
        self.__holder = holder
        self.__map_frame = None
        self.__lat_entry = None
        self.__lon_entry = None
        self.__zoom_entry = None
        self.user_pops = UserPopups()
        self.__create_widgets()

    def __create_widgets(self):
        '''
        Internal function to create widgets
        '''
        control_panel_holder = QScrollArea()
        content = QWidget()

        control_panel_holder.setWidget(content)
        control_panel_holder.setWidgetResizable(True)

        control_panel = QVBoxLayout(content)
        control_panel.addStretch()

        self.__map_frame = QWidget()
        self.__map_frame.resize(800, 500)
        self.__holder.addWidget(self.__map_frame, 0, 0, 1, 3)
        btn_load_map = QPushButton('Load Map')
        btn_load_map.clicked.connect(self.__load_map_file)
        control_panel.addWidget(btn_load_map)

        frm_load_web_map = QLabel('Load WebMap')
        control_panel.addWidget(frm_load_web_map)
        lay_load_web_map = QGridLayout()
        lay_load_web_map_holder = QVBoxLayout()
        lay_load_web_map_holder.addStretch()


        lbl_p1 = QLabel('Lat/Long NW Point')
        lay_load_web_map.addWidget(lbl_p1, 0, 0)

        self.__p1_lat_entry = QLineEdit()
        lay_load_web_map.addWidget(self.__p1_lat_entry, 0, 1)
        self.__p1_lon_entry = QLineEdit()
        lay_load_web_map.addWidget(self.__p1_lon_entry, 0, 2)

        lbl_p2 = QLabel('Lat/Long SE Point')
        lay_load_web_map.addWidget(lbl_p2, 1, 0)

        self.__p2_lat_entry = QLineEdit()
        lay_load_web_map.addWidget(self.__p2_lat_entry, 1, 1)
        self.__p2_lon_entry = QLineEdit()
        lay_load_web_map.addWidget(self.__p2_lon_entry, 1, 2)

        btn_load_web_map = QPushButton('Load from Web')
        btn_load_web_map.clicked.connect(self.__load_web_map)
        lay_load_web_map.addWidget(btn_load_web_map, 3, 1, 1, 2)

        btn_load_cached_map = QPushButton('Load from Cache')
        btn_load_cached_map.clicked.connect(self.__load_cached_map)
        lay_load_web_map.addWidget(btn_load_cached_map, 4, 1, 1, 2)

        control_panel.addWidget(frm_load_web_map)
        control_panel.addLayout(lay_load_web_map)

        self.set_content_layout(control_panel)

    def __coords_from_config(self):
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
            self.user_pops.show_warning("Could not read config path", config_path)
            return None, None, None, None

    def __init_lat_lon(self):
        lat1 = self.__p1_lat_entry.text()
        lon1 = self.__p1_lon_entry.text()
        lat2 = self.__p2_lat_entry.text()
        lon2 = self.__p2_lon_entry.text()

        if lat1 is None or lat2 is None or lon1 is None or lon2 is None or \
                lat1 == '' or lon1 == '' or lat2 == '' or lon2 == '':
            with get_instance(Path('gcsConfig.ini')) as config:
                nw_extent, se_extent = config.map_extent

            lat1 = str(nw_extent[0])
            self.__p1_lat_entry.setText(lat1)
            lon1 = str(nw_extent[1])
            self.__p1_lon_entry.setText(lon1)
            lat2 = str(se_extent[0])
            self.__p2_lat_entry.setText(lat2)
            lon2 = str(se_extent[1])
            self.__p2_lon_entry.setText(lon2)

        p1_lat = float(lat1)
        p1_lon = float(lon1)
        p2_lat = float(lat2)
        p2_lon = float(lon2)

        return [p1_lat, p1_lon, p2_lat, p2_lon]

    def __load_web_map(self):
        '''
        Internal function to load map from web
        '''
        p1_lat, p1_lon, p2_lat, p2_lon = self.__init_lat_lon()
        try:
            temp = WebMap(self.__holder, p1_lat, p1_lon, p2_lat, p2_lon, False)
        except RuntimeError:
            self.user_pops.show_warning("Failed to load web map")
            return
        self.__map_frame.setParent(None)
        self.__map_frame = temp
        self.__map_frame.resize(800, 500)
        self.__map_options.set_map(self.__map_frame, True)
        self.__root.set_map(self.__map_frame)

    def __load_cached_map(self):
        '''
        Internal function to load map from cached tiles
        '''
        p1_lat, p1_lon, p2_lat, p2_lon = self.__init_lat_lon()
        self.__map_frame.setParent(None)
        self.__map_frame = WebMap(self.__holder, p1_lat, p1_lon,
                p2_lat, p2_lon, True)
        self.__map_frame.resize(800, 500)
        self.__map_options.set_map(self.__map_frame, True)
        self.__root.set_map(self.__map_frame)

    def __load_map_file(self):
        '''
        Internal function to load user-specified raster file
        '''
        self.__map_frame.setParent(None)
        try:
            self.__map_frame = StaticMap(self.__holder)
        except FileNotFoundError as e:
            print(e)
            self.__load_web_map()
        else:
            self.__map_frame.resize(800, 500)
            self.__map_options.set_map(self.__map_frame, False)
            self.__root.set_map(self.__map_frame)
