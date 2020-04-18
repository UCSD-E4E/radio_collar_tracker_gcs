#!/usr/bin/env python3
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
# DATE        Name  Description
# -----------------------------------------------------------------------------
# 04/16/20    NH    Moved Commands and Events to module scope, added helper for
#                   sending commands, cleaned up eventing mechanisms
# 04/14/20    NH    Initial commit, fixed start parameters, added support for
#                   multiline packet
#
###############################################################################
import socket
import select
import json
import logging
import datetime as dt
import threading
import enum

from time import sleep


class COMMANDS(enum.Enum):
    GET_FREQUENCY = "getF"
    START = 'start'
    STOP = 'stop'
    SET_FREQUENCY = 'setF'
    GET_OPTIONS = 'getOpts'
    SET_OPTIONS = 'setOpts'
    WRITE_OPTIONS = 'writeOpts'
    UPGRADE = 'upgrade'


class PACKET_TYPES(enum.Enum):
    HEARTBEAT = 'heartbeat'
    PING = 'ping'
    FREQUENCIES = 'frequencies'
    EXCEPTION = 'exception'
    TRACEBACK = 'traceback'
    OPTIONS = 'options'
    UPGRADE_READY = 'upgrade_ready'
    UPGRADE_STATUS = 'upgrade_status'
    UPGRADE_COMPLETE = 'upgrade_complete'
    COMMAND = 'cmd'


class EVENTS(enum.Enum):
    HEARTBEAT = PACKET_TYPES.HEARTBEAT
    PING = PACKET_TYPES.PING
    FREQUENCIES = PACKET_TYPES.FREQUENCIES
    EXCEPTION = PACKET_TYPES.EXCEPTION
    TRACEBACK = PACKET_TYPES.TRACEBACK
    OPTIONS = PACKET_TYPES.OPTIONS
    UPGRADE_READY = PACKET_TYPES.UPGRADE_READY
    UPGRADE_STATUS = PACKET_TYPES.UPGRADE_STATUS
    UPGRADE_COMPLETE = PACKET_TYPES.UPGRADE_COMPLETE
    COMMAND = PACKET_TYPES.COMMAND
    NO_HEARTBEAT = enum.auto()
    UNKNOWN_PACKET = enum.auto()
    GENERAL_EXCEPTION = enum.auto()


class MAVReceiver:
    '''
    Radio Collar Tracker UDP Interface
    '''
    __BUFFER_LEN = 1024

    def __init__(self, port: int, originString='gcs'):
        '''
        Initializes the UDP interface on the specified port.  Also specifies a
        filename to use as a logfile, which defaults to no log.

        :param port: Port number
        :type port: Integer
        '''
        assert(isinstance(port, (int)))
        self.__log = logging.getLogger('rctGCS.MAVReceiver')
        self.sock = None
        self.__portNo = port

        self.__receiverThread = None
        self.__log.info('RTC MAVReceiver created')
        self.__run = False
        self.__mavIP = None
        self.__lastHeartbeat = None
        self.__packetMap = {
            EVENTS.HEARTBEAT: [self.__processHeartbeat],
            EVENTS.NO_HEARTBEAT: [],
            EVENTS.GENERAL_EXCEPTION: [],
            EVENTS.UNKNOWN_PACKET: [],
        }
        self.__originString = originString

    def waitForHeartbeat(self, guiTick=None, timeout: int=30):
        '''
        Waits to receive a heartbeat packet.  Returns a tuple containing the
        MAV's IP address and port number as a single tuple, and the contents of
        the received heartbeat packet. 
        :param guiTick:
        :type guiTick:
        :param timeout: Seconds to wait before timing out
        :type timeout: Integer
        '''
        assert(isinstance(timeout, (int)))
        for i in range(timeout):
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                data, addr = self.sock.recvfrom(1024)
                strData = data.decode('utf-8')
                for line in strData.split('\r\n'):
                    packet = json.loads(line)
                    if PACKET_TYPES.HEARTBEAT.value in packet:
                        self.__log.info("Received heartbeat %s" % (packet))
                        self.__lastHeartbeat = dt.datetime.now()
                        return addr, packet
            if guiTick is not None:
                guiTick()
        self.__log.error("Failed to receive any heartbeats")
        return (None, None)

    def __receiverLoop(self):
        '''
        Receiver thread
        '''
        self.__log.info('RCT MAVReceiver rxThread started')
        keywordEventMap = {}
        for event in EVENTS:
            if isinstance(event.value, PACKET_TYPES):
                keywordEventMap[event.value.value] = event
        while self.__run:
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                data, addr = self.sock.recvfrom(self.__BUFFER_LEN)
                self.__log.info("Received: %s" % data.decode())
                packet = json.loads(data.decode())
                for key in packet.keys():
                    try:
                        event = keywordEventMap[key]
                        for callback in self.__packetMap[event]:
                            callback(packet=packet[key], addr=addr)
                    except KeyError:
                        for callback in self.__packetMap[EVENTS.UNKNOWN_PACKET]:
                            callback(packet=packet, addr=addr)
                    except Exception:
                        for callback in self.__packetMap[EVENTS.GENERAL_EXCEPTION]:
                            callback(packet=packet, addr=addr)
            if (dt.datetime.now() - self.__lastHeartbeat).total_seconds() > 30:
                self.__log.warning("No heartbeats!")
                for callback in self.__packetMap[EVENTS.NO_HEARTBEAT]:
                    callback(packet=None, addr=None)

    def start(self, gui=None):
        '''
        Starts the receiver.
        '''
        self.__log.info("RCT MAVReceiver starting...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.__portNo))
        self.__mavIP, packet = self.waitForHeartbeat(guiTick=gui)
        if self.__mavIP is None:
            raise RuntimeError("Failed to receive heartbeats")
        for key in self.__packetMap.keys():
            if key in packet:
                for callback in self.__packetMap[key]:
                    callback(packet[key])
        self.__run = True
        self.__receiverThread = threading.Thread(target=self.__receiverLoop)
        self.__receiverThread.start()
        self.__log.info('RCT MAVReceiver started')

    def stop(self):
        '''
        Stops the receiver.
        '''
        self.__log.info("__run set to False")
        self.__run = False
        if self.__receiverThread is not None:
            self.__receiverThread.join(timeout=1)
        self.__log.info('RCT MAVReceiver stopped')
        self.sock.close()

    def __processHeartbeat(self, **args):
        '''
        Internal callback to handle recognizing loss of heartbeat
        '''
        self.__lastHeartbeat = dt.datetime.now()

    def registerCallback(self, event: EVENTS, callback):
        '''
        Registers a callback for the particular packet keyword
        :param event: Event to trigger on
        :type event: EVENTS
        :param callback: Callback function
        :type callback: function pointer.  The function shall accept two 
                keyword parameters: packet (dict) and addr (str).  The packet
                dictionary shall the the packet payload, and the addr shall be
                the address of the MAV
        '''
        if event in self.__packetMap:
            self.__packetMap[event].append(callback)
        else:
            self.__packetMap[event] = [callback]

    def sendMessage(self, packet: dict):
        '''
        Sends the specified dictionary as a packet
        :param packet: Packet to send
        :type packet: dictionary
        '''
        assert(isinstance(packet, dict))
        msg = json.dumps(packet)
        self.__log.info("Send: %s" % (msg))
        self.sock.sendto(msg.encode('utf-8'), self.__mavIP)

    def sendCommandPacket(self, command: COMMANDS, options: dict = None):
        '''
        Generates a generic command packet
        :param command:    Command to generate
        :type command: COMMANDS
        :param options: Options for command
        :type options: dict
        :return dict    Populated generic command packet
        '''
        packet = {}
        commandPacket = {}
        commandPacket['id'] = self.__originString
        commandPacket['action'] = command.value
        if options is not None:
            commandPacket.update(options)
        packet[PACKET_TYPES.COMMAND.value] = commandPacket
        self.sendMessage(packet)


if __name__ == '__main__':
    rx = MAVReceiver(9000)
    rx.start()
    sleep(1)
    rx.sendCommandPacket(COMMANDS.START)
    rx.stop()
