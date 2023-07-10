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
# 08/07/22  HG  Added multiple-client functionality
# 08/06/20  NH  Fixed reset on init
# 07/29/20  NH  Added docstrings
# 05/23/20  NH  Fixed simulator run/stop actions
# 05/20/20  NH  Added DroneSim.reset to facilitate simulator reset, fixed
#                 logging setup
# 05/19/20  NH  Renamed DroneSim.__options to DroneSim.PP_options to provide
#                 command line access
# 05/18/20  NH  Moved droneComms to rctComms, combined payload options into
#                 dict, annotated simulator parameters, updated commands to use
#                 binary protocol, integrated vehicle and ping data
# 05/05/20  NH  Integrated mission simulator and ping generation
# 04/26/20  NH  Removed old DroneSimulator class, added output, added command
#                 callback, fixed sendFrequencies, added error capture, fixed
#                 cli args
# 04/25/20  NH  Finished abstraction of DroneSimulator to DroneSim
# 04/20/20  NH  Fixed sender to not send tuple as addr
# 04/19/20  NH  Added abstraction, switched to rctTransport comm interface
# 04/14/20  NH  Initial history
#
###############################################################################
import argparse
import datetime as dt
import json
import logging
import math
import socket
import sys
import threading
import time
from pathlib import Path
from time import sleep
from typing import List

import numpy as np
import RCTComms.comms
import RCTComms.transport
import utm

from RctGcs.config import Configuration, ConnectionMode, get_config_path
from RctGcs.ping import rctPing


def get_ips():
    '''
    Returns this machine's IP addresses as a set
    '''
    ip = set()

    ip.add(socket.gethostbyname_ex(socket.gethostname())[2][0])
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 53))
    ip.add(s.getsockname()[0])
    s.close()
    return ip


class DroneSim:
    '''
    Drone simulator class
    '''
    class MISSION_STATE:
        '''
        Mission State values.  These are the possible values of
        self.SS_vehicle_state
        '''
        TAKEOFF = 0
        WAYPOINTS = 1
        RTL = 2
        LAND = 3
        END = 4
        SPIN = 5

    def __init__(self, port: RCTComms.comms.mavComms):
        '''
        Creates a new DroneSim object
        :param port:
        '''
        self.__tx_thread = None
        self.__mission_thread = None
        self.__end_mission_event = None
        self.port = port
        self.__command_map = {}
        self.__state = {
            'STS_sdr_status': 0,
            'STS_dir_status': 0,
            'STS_gps_status': 0,
            'STS_sys_status': 0,
            'STS_sw_status': 0,
        }

        self.__tx_thread = None

        # PP - Payload parameters
        self.PP_options = {
            "TGT_frequencies": [],
            "SDR_center_freq": 173500000,
            "SDR_sampling_freq": 2000000,
            "SDR_gain": 20.0,
            "DSP_ping_width": 15,
            "DSP_ping_snr": 4.0,
            "DSP_ping_max": 1.5,
            "DSP_ping_min": 0.5,
            "GPS_mode": 0,
            "GPS_device": "/dev/null",
            "GPS_baud": 115200,
            "SYS_output_dir": "/tmp",
            "SYS_autostart": False,
        }

        # SM - Simulator Mission parameters
        self.SM_mission_run = True

        self.SM_utm_zone_num = 11
        self.SM_utm_zone = 'S'
        self.SM_origin = (478110, 3638925, 0)
        self.SM_end = (478110, 3638400, 0)
        self.SM_takeoff_target = (478110, 3638925, 30)
        self.SM_waypoints = [(477974.06988529314, 3638776.3039655555, 30),
                             (478281.5079546513, 3638711.2010632926, 30),
                             (478274.9146625505, 3638679.2543171947, 30),
                             (477975.5071926904, 3638745.8378777136, 30),
                             (477968.40893670684, 3638712.893777053, 30),
                             (478266.818223601, 3638648.3095763493, 30),
                             (478258.7096344019, 3638611.871386835, 30),
                             (477961.8023651167, 3638675.453913263, 30),
                             (477953.6915540979, 3638638.5166701586, 30),
                             (478246.5868126497, 3638575.4419162693, 30),
                             (478239.4937485707, 3638544.494662541, 30),
                             (477943.58029727807, 3638604.5801627054, 30),
                             (477968.0164183045, 3638761.8351352056, 30),
                             (477976.95013863116, 3638774.1124560814, 30)]
        self.SM_target_threshold = 5
        self.SM_loop_period = 0.1
        self.SM_takeoff_vel = 5
        self.SM_wp_vel = 35
        self.SM_rtl_vel = 20
        self.SM_land_vel = 1

        # SC - Simulation Communications parameters
        self.SM_vehicle_position_msg_period = 1
        self.SC_ping_measurement_period = 1
        self.SC_ping_measurement_sigma = 0
        self.SC_heartbeat_period = 5

        # SP - Simulation Ping parameters
        self.SP_tx_power = 144
        self.SP_tx_power_sigma = 0
        self.SP_system_loss = 0
        self.SP_system_loss_sigma = 0
        self.SP_exponent = 2.5
        self.SP_exponent_sigma = 0
        self.SS_position = (478110, 3638661, 0)
        self.SP_noise_floor = 90
        self.SP_noise_floor_sigma = 0
        self.SP_tx_freq = 173500000

        # SV - Simulation Vehicle parameters
        self.SV_vehicle_position_sigma = np.array((0, 0, 0))

        # SS - Simulation State parameters
        self.SS_utm_zone_num = 11
        self.SS_utm_zone = 'S'
        self.SS_vehicle_position = self.SM_origin
        self.SS_vehicle_state = DroneSim.MISSION_STATE.TAKEOFF
        self.SS_start_time = dt.datetime.now()
        self.SS_velocity_vector = np.array([0, 0, 0])
        self.SS_vehicle_target = np.array(self.SM_takeoff_target)
        self.SS_waypoint_idx = 0
        self.SS_payload_running = False
        self.SS_heading = 0

        # HS - Heartbeat State parameters
        self.HS_run = True

        # register command actions here
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_GETF, self.__do_get_frequency)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_SETF, self.__do_set_frequency)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_GETOPT, self.__do_get_options)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_SETOPT, self.__do_set_options)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_START, self.__do_start_mission)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_STOP, self.__do_stop_mission)
        self.port.registerCallback(
            RCTComms.comms.EVENTS.COMMAND_UPGRADE, self.__do_upgrade)

        # Reset state parameters
        self.reset()

    def reset(self):
        '''
        Sets simulator parameters to their default
        '''
        self.stop()
        self.__command_map = {}
        self.__state = {
            'STS_sdr_status': 0,
            'STS_dir_status': 0,
            'STS_gps_status': 0,
            'STS_sys_status': 0,
            'STS_sw_status': 0,
        }

        # PP - Payload parameters
        self.PP_options = {
            "TGT_frequencies": [],
            "SDR_center_freq": 173500000,
            "SDR_sampling_freq": 2000000,
            "SDR_gain": 20.0,
            "DSP_ping_width": 15,
            "DSP_ping_snr": 4.0,
            "DSP_ping_max": 1.5,
            "DSP_ping_min": 0.5,
            "GPS_mode": 0,
            "GPS_device": "/dev/null",
            "GPS_baud": 115200,
            "SYS_output_dir": "/tmp",
            "SYS_autostart": False,
        }

        # SM - Simulator Mission parameters
        self.SM_mission_run = True

        self.SM_utm_zone_num = 11
        self.SM_utm_zone = 'S'
        self.SM_origin = (478110, 3638925, 0)
        self.SM_end = (478110, 3638400, 0)
        self.SM_takeoff_target = (478110, 3638925, 30)
        '''
        Triangle
        self.SM_waypoints = [(478110, 3638925, 30),
                             (478080, 3638700, 30),
                             (478140, 3638700, 30)]
        Square
        self.SM_waypoints = [(477995, 3638776, 30),
                             (477995, 3638546, 30),
                             (478225, 3638546, 30),
                             (478225, 3638776, 30),
                             (477995, 3638776, 30)]
        100m
        self.SM_waypoints = [(478110.0, 3638761.0, 30),
                            (478060.0, 3638747.6025403785, 30),
                            (478023.39745962154, 3638711.0, 30),
                            (478010.0, 3638661.0, 30),
                            (478023.39745962154, 3638611.0, 30),
                            (478060.0, 3638574.3974596215, 30),
                            (478110.0, 3638561.0, 30),
                            (478160.0, 3638574.3974596215, 30),
                            (478196.60254037846, 3638611.0, 30),
                            (478210.0, 3638661.0, 30),
                            (478196.60254037846, 3638711.0, 30),
                            (478160.0, 3638747.6025403785, 30),
                            (478110.0, 3638761.0, 30)]
        70m
        self.SM_waypoints = [(478110.0, 3638731.0, 30),
                            (478075.0, 3638721.621778265, 30),
                            (478049.37822173507, 3638696.0, 30),
                            (478040.0, 3638661.0, 30),
                            (478049.37822173507, 3638626.0, 30),
                            (478075.0, 3638600.378221735, 30),
                            (478110.0, 3638591.0, 30),
                            (478145.0, 3638600.378221735, 30),
                            (478170.62177826493, 3638626.0, 30),
                            (478180.0, 3638661.0, 30),
                            (478170.62177826493, 3638696.0, 30),
                            (478145.0, 3638721.621778265, 30),
                            (478110.0, 3638731.0, 30)]
        OG
        self.SM_waypoints = [(477974.06988529314, 3638776.3039655555, 30),
                             (477974.06988529314, 3638776.3039655555, 30),
                             (477974.06988529314, 3638776.3039655555, 30),
                             (477974.06988529314, 3638776.3039655555, 30),
                             (477974.06988529314, 3638776.3039655555, 30),
                             (478281.5079546513, 3638711.2010632926, 30),
                             (478274.9146625505, 3638679.2543171947, 30),
                             (477975.5071926904, 3638745.8378777136, 30),
                             (477968.40893670684, 3638712.893777053, 30),
                             (478266.818223601, 3638648.3095763493, 30),
                             (478258.7096344019, 3638611.871386835, 30),
                             (477961.8023651167, 3638675.453913263, 30),
                             (477953.6915540979, 3638638.5166701586, 30),
                             (478246.5868126497, 3638575.4419162693, 30),
                             (478239.4937485707, 3638544.494662541, 30),
                             (477943.58029727807, 3638604.5801627054, 30),
                             (477968.0164183045, 3638761.8351352056, 30),
                             (477976.95013863116, 3638774.1124560814, 30)]
        '''
        self.SM_waypoints = [(478060, 3638631, 30),
                             (478170, 3638631, 30)]
        self.SM_target_threshold = 5
        self.SM_loop_period = 0.1
        self.SM_takeoff_vel = 5
        self.SM_wp_vel = 35
        self.SM_rtl_vel = 20
        self.SM_land_vel = 1

        # SC - Simulation Communications parameters
        self.SM_vehicle_position_msg_period = 1
        self.SC_ping_measurement_period = 0.5
        self.SC_ping_measurement_sigma = 0
        self.SC_heartbeat_period = 5

        # SP - Simulation Ping parameters
        self.SP_tx_power = 144
        self.SP_tx_power_sigma = 0
        self.SP_system_loss = 0
        self.SP_system_loss_sigma = 0
        self.SP_exponent = 2.5
        self.SP_exponent_sigma = 0
        self.SS_position = (478110, 3638661, 0)

        #center
        #self.SS_position = (478110, 3638825, 0)

        #20m beyond
        #self.SS_position = (478110, 3638680, 0)

        #20m right
        #self.SS_position = (478130, 3638825, 0)

        #50m right
        #self.SS_position = (478160, 3638825, 0)

        #diagonal
        #self.SS_position = (478150, 3638680, 0)

        self.SP_noise_floor = 90
        self.SP_noise_floor_sigma = 0
        self.SP_tx_freq = 173500000

        # SV - Simulation Vehicle parameters
        self.SV_vehicle_position_sigma = np.array((0, 0, 0))

        # SS - Simulation State parameters
        self.SS_utm_zone_num = 11
        self.SS_utm_zone = 'S'
        self.SS_vehicle_position = self.SM_origin
        self.SS_vehicle_state = DroneSim.MISSION_STATE.TAKEOFF
        self.SS_start_time = dt.datetime.now()
        self.SS_velocity_vector = np.array([0, 0, 0])
        self.SS_vehicle_target = np.array(self.SM_takeoff_target)
        self.SS_waypoint_idx = 0
        self.SS_vehicle_hdg = 0
        self.SS_hdg_index = 0
        self.SS_payload_running = False
        self.SS_heading = 0

        # HS - Heartbeat State parameters
        self.HS_run = True

    def set_gain(self, gain: float):
        '''
        Sets the SDR_gain parameter to the specified value
        :param gain:
        '''
        self.PP_options['SDR_gain'] = gain

    def set_output_dir(self, output_dir: str):
        '''
        Sets the output directory to the specified value
        :param output_dir:
        '''
        self.PP_options['SYS_output_dir'] = output_dir

    def set_ping_parameters(self, DSP_ping_width: int = None, DSP_ping_snr: float = None, DSP_ping_max: float = None, DSP_ping_min: float = None):
        '''
        Sets the specified ping parameters
        :param DSP_ping_width:
        :param DSP_ping_snr:
        :param DSP_ping_max:
        :param DSP_ping_min:
        '''
        if DSP_ping_width is not None:
            self.PP_options['DSP_ping_width'] = DSP_ping_width

        if DSP_ping_snr is not None:
            self.PP_options['DSP_ping_snr'] = DSP_ping_snr

        if DSP_ping_max is not None:
            self.PP_options['DSP_ping_max'] = DSP_ping_max

        if DSP_ping_min is not None:
            self.PP_options['DSP_ping_min'] = DSP_ping_min

    def set_gps_parameters(self, GPS_device: str = None, GPS_baud: int = None, GPS_mode: bool = None):
        '''
        Sets the specified GPS parameters
        :param GPS_device:
        :param GPS_baud:
        :param GPS_mode:
        '''
        if GPS_device is not None:
            self.PP_options['GPS_device'] = GPS_device

        if GPS_baud is not None:
            self.PP_options['GPS_baud'] = GPS_baud

        if GPS_mode is not None:
            self.PP_options['GPS_mode'] = GPS_mode

    def set_autostart(self, SYS_autostart: bool):
        '''
        Sets the autostart parameter
        :param SYS_autostart:
        '''
        self.PP_options['SYS_autostart'] = SYS_autostart

    def start(self):
        '''
        Starts the simulator.  This is equivalent to turning on the payload with
        autostart enabled.
        '''
        #self.reset()
        self.port.start()
        self.HS_run = True
        self.__tx_thread = threading.Thread(target=self.__sender)
        self.__tx_thread.start()

    def stop(self):
        '''
        Stops the simulator.  This is equivalent to turning off the payload.
        '''
        self.HS_run = False
        if self.__tx_thread is not None:
            self.__tx_thread.join()
            self.port.stop()

    def restart(self):
        '''
        Stops then starts the simulator.  This is equivalent to power cycling
        the payload.
        '''
        self.stop()
        self.start()

    def got_ping(self, drone_ping: rctPing, hdg:float):
        '''
        Helper function to send a ping packet.  This must be called while the
        port is open.
        :param drone_ping: rctPing object to send
        '''
        if not self.port.isOpen():
            raise RuntimeError
        print("Ping on %d at %3.7f, %3.7f, %3.0f m, measuring %3.3f" %
              (drone_ping.freq, drone_ping.lat, drone_ping.lon, drone_ping.alt, drone_ping.power))

        cone_packet = RCTComms.comms.rctConePacket(drone_ping.lat, drone_ping.lon, drone_ping.alt, drone_ping.power, hdg)


        self.port.sendCone(cone_packet)

    def set_system_state(self, system: str, state):
        '''
        Sets the simulator's system state to the specified state.
        :param system: One of STS_sdr_status, STS_dir_status, STS_gps_status,
                        STS_sys_status, or STS_sw_status
        :param state: The appropriate state number per ICD
        '''
        self.__state[system] = state

    def set_exception(self, exception: str, traceback: str):
        '''
        Helper function to send an exception packet.  This must be called while
        the port is open.
        :param exception: Exception string
        :param traceback: Traceback string
        '''
        if not self.port.isOpen():
            raise RuntimeError
        self.port.sendException(exception, traceback)

    def set_frequencies(self, frequencies: list):
        '''
        Sets the simulator's frequencies to the specified frequencies
        :param frequencies:
        '''
        self.PP_options['TGT_frequencies'] = frequencies

    def get_frequencies(self):
        '''
        Retrieves the simulator's frequencies
        '''
        return self.PP_options['TGT_frequencies']

    def set_center_frequency(self, center_freq: int):
        '''
        Sets the simulator's center frequency
        :param center_freq:
        '''
        self.PP_options['SDR_center_freq'] = center_freq

    def set_sampling_frequency(self, sampling_freq: int):
        '''
        Sets the simulator's sampling frequency
        :param sampling_freq:
        '''
        self.PP_options['SDR_sampling_freq'] = sampling_freq

    def __ack_command(self, command: RCTComms.comms.rctBinaryPacket):
        '''
        Sends the command acknowledge packet for the given command.
        :param command:
        '''
        self.port.sendToGCS(RCTComms.comms.rctACKCommand(command._pid, 1))

    def __do_get_frequency(self, packet: RCTComms.comms.rctGETFCommand, addr: str):
        '''
        Callback for the Get Frequency command packet
        :param packet:
        :param addr:
        '''
        self.port.sendToGCS(RCTComms.comms.rctFrequenciesPacket(
            self.PP_options['TGT_frequencies']))

    def __do_start_mission(self, packet: RCTComms.comms.rctSTARTCommand, addr: str):
        '''
        Callback for the Start Mission command packet
        :param packet:
        :param addr:
        '''
        self.SS_payload_running = True
        self.__ack_command(packet)

    def __do_stop_mission(self, packet: RCTComms.comms.rctSTOPCommand, addr: str):
        '''
        Callback for the Stop Mission command packet
        :param packet:
        :param addr:
        '''
        self.SS_payload_running = False
        self.__ack_command(packet)

    def __do_set_frequency(self, packet: RCTComms.comms.rctSETFCommand, addr: str):
        '''
        Callback for the Set Frequency command packet
        :param packet:
        :param addr:
        '''
        frequencies = packet.frequencies

        # Nyquist check
        for freq in frequencies:
            if abs(freq - self.PP_options['SDR_center_freq']) > self.PP_options['SDR_sampling_freq']:
                raise RuntimeError("Invalid frequency")

        self.PP_options['TGT_frequencies'] = frequencies
        self.__ack_command(packet)
        self.__do_get_frequency(packet, addr)

    def __do_get_options(self, packet: RCTComms.comms.rctGETOPTCommand, addr: str):
        '''
        Callback for the Get Options command packet
        :param packet:
        :param addr:
        '''
        scope = packet.scope
        print(self.PP_options)
        packet = RCTComms.comms.rctOptionsPacket(scope, **self.PP_options)
        self.port.sendToGCS(packet)

    def __do_set_options(self, packet: RCTComms.comms.rctSETOPTCommand, addr: str):
        '''
        Callback for the Set Options command packet
        :param packet:
        :param addr:
        '''
        self.PP_options.update(packet.options)
        self.__do_get_options(packet, addr)
        self.__ack_command(packet)

    def __do_upgrade(self, command_payload):
        '''
        Callback for the Upgrade command packet
        :param command_payload:
        '''
        pass

    def __sender(self):
        '''
        Thread function for the heartbeat sender.  This function sends the
        heartbeat packet every self.SC_heartbeat_period seconds.
        '''
        while self.HS_run is True:
            packet = RCTComms.comms.rctHeartBeatPacket(self.__state['STS_sys_status'],
                                                 self.__state['STS_sdr_status'],
                                                 self.__state['STS_gps_status'],
                                                 self.__state['STS_dir_status'],
                                                 self.__state['STS_sw_status'])
            self.port.sendToAll(packet)
            time.sleep(self.SC_heartbeat_period)

    def transmit_position(self):
        '''
        Transmits the current vehicle position.  This function must only be used
        when the port is open.  Position is defined by self.SS_vehicle_position
        in the self.SS_utm_zone_num and self.SS_utm_zone zone.
        '''
        if not self.port.isOpen():
            raise RuntimeError
        print(self.SS_vehicle_position, self.SS_vehicle_state,
              np.linalg.norm(self.SS_velocity_vector))
        lat, lon = utm.to_latlon(
            self.SS_vehicle_position[0], self.SS_vehicle_position[1], self.SS_utm_zone_num, self.SS_utm_zone)
        alt = self.SS_vehicle_position[2]
        hdg = 0
        packet = RCTComms.comms.rctVehiclePacket(lat, lon, alt, hdg)

        self.port.sendVehicle(packet)

    def do_mission_on_thread(self, return_on_end: bool = False):
        '''
        Runs the flight mission on a new thread.
        '''
        self.__mission_thread = threading.Thread(target=self.do_mission, args=(return_on_end,))
        self.__end_mission_event = threading.Event()
        time.sleep(0.109) # Help threads not run all together
        self.__mission_thread.start()

    def stop_mission_on_thread(self):
        if self.__end_mission_event is not None:
            self.__end_mission_event.set()
            self.__mission_thread.join()


    def do_mission(self, return_on_end: bool = False):
        '''
        Runs the flight mission.  This function simulates flying the mission
        specified in the SM parameters.
        :param return_on_end:
        '''

        self.SS_vehicle_position = self.SM_origin
        self.SS_vehicle_state = DroneSim.MISSION_STATE.TAKEOFF
        self.SS_start_time = dt.datetime.now()
        self.SS_velocity_vector = np.array([0, 0, 0])
        self.SS_vehicle_target = np.array(self.SM_takeoff_target)
        self.SS_waypoint_idx = 0

        prev_pos_time = prev_ping_time = prev_time = self.SS_start_time
        wp_time = self.SS_start_time
        while self.SM_mission_run:
            #######################
            # Loop time variables #
            #######################
            # Current time
            cur_time = dt.datetime.now()
            # Time since mission start
            el_time = (cur_time - self.SS_start_time).total_seconds()
            # Time since last loop
            it_time = (cur_time - prev_time).total_seconds()
            # Time since last waypoint
            seg_time = (cur_time - wp_time).total_seconds()

            ########################
            # Flight State Machine #
            ########################
            if self.SS_vehicle_state == DroneSim.MISSION_STATE.TAKEOFF:
                self.SS_velocity_vector = np.array(
                    [0, 0, 1]) * self.SM_takeoff_vel
                self.SS_vehicle_position += self.SS_velocity_vector * it_time
                distance_to_target = np.linalg.norm(
                    self.SS_vehicle_target - self.SS_vehicle_position)
                if distance_to_target < self.SM_target_threshold:
                    self.SS_velocity_vector = np.array([0, 0, 0])
                    self.SS_vehicle_state = DroneSim.MISSION_STATE.WAYPOINTS
                    self.SS_vehicle_target = np.array(
                        self.SM_waypoints[self.SS_waypoint_idx])
                    wp_time = dt.datetime.now()

            elif self.SS_vehicle_state == DroneSim.MISSION_STATE.WAYPOINTS:
                target_vector = self.SS_vehicle_target - self.SS_vehicle_position
                distance_to_target = np.linalg.norm(target_vector)
                self.SS_velocity_vector = target_vector / distance_to_target * self.SM_wp_vel

                self.SS_vehicle_position += self.SS_velocity_vector * it_time
                if distance_to_target < self.SM_target_threshold:
                    self.SS_velocity_vector = np.array([0, 0, 0])
                    wp_time = dt.datetime.now()

                    self.SS_waypoint_idx += 1
                    self.SS_vehicle_state = DroneSim.MISSION_STATE.SPIN

            elif self.SS_vehicle_state == DroneSim.MISSION_STATE.SPIN:
                self.SS_vehicle_hdg = self.SS_hdg_index*5
                self.SS_hdg_index += 1
                if self.SS_vehicle_hdg == 360:
                    self.SS_hdg_index = 0
                    if self.SS_waypoint_idx < len(self.SM_waypoints):
                        self.SS_vehicle_state = DroneSim.MISSION_STATE.WAYPOINTS
                        self.SS_vehicle_target = np.array(
                            self.SM_waypoints[self.SS_waypoint_idx])
                    else:
                        self.SS_vehicle_state = DroneSim.MISSION_STATE.RTL
                        #self.SS_vehicle_target = np.array(self.SM_end)
                        self.SS_vehicle_target = np.array(self.SM_takeoff_target)
            elif self.SS_vehicle_state == DroneSim.MISSION_STATE.RTL:
                target_vector = self.SS_vehicle_target - self.SS_vehicle_position
                distance_to_target = np.linalg.norm(target_vector)
                self.SS_velocity_vector = target_vector / distance_to_target * self.SM_rtl_vel

                self.SS_vehicle_position += self.SS_velocity_vector * it_time
                if distance_to_target < self.SM_target_threshold:
                    self.SS_velocity_vector = np.array([0, 0, 0])
                    wp_time = dt.datetime.now()

                    self.SS_vehicle_state = DroneSim.MISSION_STATE.LAND
                    #self.SS_vehicle_target = np.array(self.SM_end)
                    self.SS_vehicle_target = np.array(self.SM_origin)

            elif self.SS_vehicle_state == DroneSim.MISSION_STATE.LAND:
                self.SS_velocity_vector = np.array([0, 0, -1]) * self.SM_land_vel
                self.SS_vehicle_position += self.SS_velocity_vector * it_time
                distance_to_target = np.linalg.norm(
                    self.SS_vehicle_target - self.SS_vehicle_position)
                if distance_to_target < self.SM_target_threshold:
                    self.SS_velocity_vector = np.array([0, 0, 0])
                    wp_time = dt.datetime.now()
                    self.SS_vehicle_state = DroneSim.MISSION_STATE.END
            else:
                if return_on_end:
                    return
                else:
                    self.SS_velocity_vector = np.array([0, 0, 0])

            if self.__end_mission_event is not None:
                if self.__end_mission_event.wait(self.SM_loop_period):
                    self.SM_mission_run = False
                    break
            else:
                sleep(self.SM_loop_period)

            ###################
            # Ping Simulation #
            ###################
            if (cur_time - prev_ping_time).total_seconds() > self.SC_ping_measurement_period:
                lat, lon = utm.to_latlon(
                    self.SS_vehicle_position[0], self.SS_vehicle_position[1], self.SM_utm_zone_num, self.SM_utm_zone)
                latT, lonT = utm.to_latlon(
                    self.SS_vehicle_target[0], self.SS_vehicle_target[1], self.SM_utm_zone_num, self.SM_utm_zone)
                if self.SS_vehicle_state == DroneSim.MISSION_STATE.SPIN:
                        hdg = self.SS_vehicle_hdg
                else:
                    hdg = self.get_bearing(lat, lon, latT, lonT)
                    self.SS_vehicle_hdg = hdg
                ping_measurement = self.calculate_ping_measurement()
                if ping_measurement is not None:
                    print("in Ping Measurement")

                    new_ping = rctPing(
                        lat, lon, ping_measurement[0], ping_measurement[1], self.SS_vehicle_position[2], cur_time.timestamp())

                    #hdg = self.get_bearing(self.SS_vehicle_position[0], self.SS_vehicle_position[1], self.SS_vehicle_target[0], self.SS_vehicle_target[1])

                    print(hdg)
                    '''
                    if self.SS_payload_running:
                        self.got_ping(new_ping)
                    '''
                    if new_ping is not None:
                        self.got_ping(new_ping, hdg)
                prev_ping_time = cur_time

            ###################
            # Position Output #
            ###################
            if (cur_time - prev_pos_time).total_seconds() > self.SM_vehicle_position_msg_period:
                self.transmit_position()
                prev_pos_time = cur_time
            prev_time = cur_time

    def get_bearing(self, lat1, long1, lat2, long2):
        dLon = (long2 - long1)
        x = math.cos(math.radians(lat2)) * math.sin(math.radians(dLon))
        y = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(dLon))
        brng = np.arctan2(x,y)
        brng = np.degrees(brng)

        return brng

    def __antenna_model(self, beam_angle) -> float:
        return np.abs(np.cos(beam_angle)) ** (2.99999)

    def __compute_heading_multiplier(self) -> float:
        # Get my current heading
        x = np.cos(np.deg2rad(self.SS_vehicle_hdg))
        y = np.sin(np.deg2rad(self.SS_vehicle_hdg))
        heading_vector = np.array([x, y, 0])

        # Get the bearing to the transmitter
        transmitter_vector = np.array(self.SS_position) - np.array(self.SS_vehicle_position)
        transmitter_vector = transmitter_vector / np.linalg.norm(transmitter_vector)

        # Compute the bearing from antenna to transmitter
        dot = np.dot(heading_vector, transmitter_vector)
        angle = np.arccos(dot)
        print("Angle: ", np.rad2deg(angle))

        # Plug into directivity model
        model = self.__antenna_model(angle)
        print("Model: ", model)
        return model

    def calculate_ping_measurement(self):
        '''
        Calculate the simulated ping measurement from the current state
        variables
        '''
        # check against frequencies
        '''
        if abs(self.SP_tx_freq - self.PP_options['SDR_center_freq']) > self.PP_options['SDR_sampling_freq']:
            return None
        if self.SP_tx_freq not in self.PP_options['TGT_frequencies']:
            return None
        '''
        # vehicle is correctly configured
        l_rx = np.array(self.SS_vehicle_position)
        l_tx = np.array(self.SS_position)
        rand = np.random.normal(scale=self.SP_tx_power_sigma)
        P_tx = self.SP_tx_power + rand
        rand_ex = np.random.normal(scale=self.SP_exponent_sigma)
        n = self.SP_exponent + rand_ex
        C = self.SP_system_loss
        f_tx = self.SP_tx_freq
        rand_n = np.random.normal(scale=self.SP_noise_floor_sigma)#added
        P_n = self.SP_noise_floor + rand_n
        print(rand_n)
        print(P_n)

        d = np.linalg.norm(l_rx - l_tx)

        Prx = P_tx - 10 * n * np.log10(d) - C

        measurement = [Prx, f_tx]

        measurement[0] *= self.__compute_heading_multiplier()

        measurement = (measurement[0], measurement[1])

        # implement noise floor
        if Prx < P_n:
           measurement = None


        return measurement


    def export_settings(self, filename):
        e = {}
        e['commandMap'] = str(self.__command_map)

        e['State'] = str(self.__state )

        e['PP_options'] = str(self.PP_options )
        e['SM_mission_run'] = str(self.SM_mission_run )

        e['SM_utm_zone_num'] = str(self.SM_utm_zone_num)
        e['SM_utm_zone'] = str(self.SM_utm_zone)

        e['SM_origin'] = str(self.SM_origin)

        e['SM_takeoff_target'] = str(self.SM_takeoff_target)

        e['SM_waypoints'] = str(self.SM_waypoints )

        e['SM_target_threshold'] = str(self.SM_target_threshold)

        e['SM_loop_period'] = str(self.SM_loop_period )

        e['SM_takeoff_vel'] = str(self.SM_takeoff_vel)

        e['SM_wp_vel'] = str(self.SM_wp_vel )

        e['SM_rtl_vel'] = str(self.SM_rtl_vel)

        e['SM_land_vel'] = str(self.SM_land_vel)


        e['SM_vehicle_position_msg_period'] = str(self.SM_vehicle_position_msg_period)

        e['SC_ping_measurement_period'] = str(self.SC_ping_measurement_period )

        e['SC_ping_measurement_sigma'] = str(self.SC_ping_measurement_sigma )

        e['SC_heartbeat_period'] = str(self.SC_heartbeat_period )


        e['SP_tx_power'] = str(self.SP_tx_power )

        e['SP+TxPowerSigma'] = str(self.SP_tx_power_sigma)

        e['SP_system_loss'] = str(self.SP_system_loss )

        e['SP_system_loss_sigma'] = str(self.SP_system_loss_sigma )

        e['SP_exponent'] = str(self.SP_exponent )

        e['SP_exponent_sigma'] = str(self.SP_exponent_sigma)

        e['SS_position'] = str(self.SS_position )

        e['SP_noise_floor'] = str(self.SP_noise_floor)

        e['SP_noise_floor_sigma:'] = str(self.SP_noise_floor_sigma )

        e['SP_tx_freq'] = str(self.SP_tx_freq )


        e['SV_vehicle_position_sigma'] = str(self.SV_vehicle_position_sigma)


        e['SS_utm_zone_num'] = str(self.SS_utm_zone_num)

        e['SS_utm_zone'] = str(self.SS_utm_zone )

        e['SS_vehicle_position'] = str(self.SS_vehicle_position )

        e['SS_vehicle_state'] = str(self.SS_vehicle_state)

        e['SS_start_time'] = str(self.SS_start_time )

        e['SS_velocity_vector'] = str(self.SS_velocity_vector)

        e['SS_vehicle_target'] = str(self.SS_vehicle_target)

        e['SS_waypoint_idx'] = str(self.SS_waypoint_idx )

        e['SS_payload_running'] = str(self.SS_payload_running )

        e['SS_heading'] = str(self.SS_heading )



        e['HS_run'] = str(self.HS_run )

        settings_file = filename + '.json'
        with open(settings_file, 'w') as outfile:
            json.dump(e, outfile)

class DroneSimPack:
    def __init__(self, port: int, addr: str, protocol: str, clients: int):
        '''
        Creates a pack of multiple DroneSim object
        :param port: port through which to connect
        :param addr: host address to which to connect
        :param protocol: transport protocol, tcp or udp
        :param clients: the number of clients to create if in tower mode
        '''
        self.config_obj = Configuration(get_config_path())
        self.config_obj.load()
        self.sim_list = []

        self.addr = addr
        self.port = port
        self.protocol = protocol

        if protocol == 'udp':
            if self.config_obj.connection_mode == ConnectionMode.TOWER:
                for i in range(clients):
                    tsport = RCTComms.transport.RCTUDPClient(port=port, addr=addr)
                    sim = DroneSim(RCTComms.comms.mavComms(tsport))
                    self.sim_list.append(sim)
            else:
                tsport = RCTComms.transport.RCTUDPServer(port=args.port)
                sim = DroneSim(RCTComms.comms.mavComms(tsport))
                self.sim_list.append(sim)

        elif protocol == 'tcp':
            if self.config_obj.connection_mode == ConnectionMode.TOWER:
                for i in range(args.clients):
                    tsport = RCTComms.transport.RCTTCPClient(port=port, addr=addr)
                    sim = DroneSim(RCTComms.comms.mavComms(tsport))
                    self.sim_list.append(sim)
            else:
                connected = False
                tsport = RCTComms.transport.RCTTCPServer(port, self.__connection_handler, addr=addr)
                tsport.open()
                while len(tsport.simList) == 0:
                    continue
                sim = DroneSim(RCTComms.comms.mavComms(tsport.simList[0]))
                self.sim_list.append(sim)

    def start(self):
        '''
        Starts all the simulators in the pack
        '''
        for sim in self.sim_list:
            sim.start()

    def do_mission(self, return_on_end: bool = False):
        '''
        Starts missions for all the simulators in the pack
        '''
        for sim in self.sim_list:
            sim.do_mission_on_thread(return_on_end)

    def stop(self):
        '''
        Stops all missions and the simulators in the pack
        '''
        for sim in self.sim_list:
            sim.stop_mission_on_thread()
            sim.stop()

    def add_client(self):
        '''
        Connects another client and adds the associated simulator to simList
        '''
        if not self.config_obj.connection_mode == ConnectionMode.TOWER:
            print("Must be in tower mode to run multiple clients")
            return

        if self.protocol == 'udp':
            port = RCTComms.transport.RCTUDPClient(port=self.port, addr=self.addr)
        elif self.protocol == 'tcp':
            port = RCTComms.transport.RCTTCPClient(port=self.port, addr=self.addr)
        sim = DroneSim(RCTComms.comms.mavComms(port))
        self.sim_list.append(sim)

    def __connection_handler(self, connection, id):
        print('Connected {}'.format(id))
        comms = RCTComms.comms.mavComms(connection)
        sim = DroneSim(comms)
        self.sim_list.append(sim)

def main():
    parser = argparse.ArgumentParser(
        description='Radio Collar Tracker Payload Control Simulator')
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--protocol', type=str,
                        choices=['udp', 'tcp'], required=True)
    parser.add_argument('--target', type=str, default='127.0.0.1',
                        help='Target IP Address.  Use 255.255.255.255 for broadcast, 127.0.0.1 for local')
    parser.add_argument('--clients', type=int, default=1)
    args = parser.parse_args()
    logName = dt.datetime.now().strftime('%Y.%m.%d.%H.%M.%S_sim.log')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.ERROR)
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d: %(levelname)s:%(name)s: %(message)s', datefmt='%Y-%M-%d %H:%m:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ch = logging.FileHandler(logName)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    sim = DroneSimPack(args.port, args.target, args.protocol, args.clients);
    if sim.config_obj.connection_mode == ConnectionMode.DRONE:
        sim = sim.sim_list[0]; # Just have a single simulator

    try:
        __IPYTHON__
    except NameError:
        sim.start()

if __name__ == '__main__':
    main()
