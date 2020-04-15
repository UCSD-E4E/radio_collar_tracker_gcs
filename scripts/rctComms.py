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

class MAVReceiver:
    '''
    Radio Collar Tracker UDP Interface
    '''
    __BUFFER_LEN = 1024

    def __init__(self, port: int):
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
            'heartbeat': [self.__processHeartbeat],
            '_nheartbeat': [],
            'exception': [],
        }

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
                    print(line)
                    packet = json.loads(line)
                    if 'heartbeat' in packet:
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
        while self.__run:
            ready = select.select([self.sock], [], [], 1)
            if ready[0]:
                data, addr = self.sock.recvfrom(self.__BUFFER_LEN)
                self.__log.info("Received: %s" % data.decode())
                packet = json.loads(data.decode())
                for key in self.__packetMap.keys():
                    if key in packet:
                        for callback in self.__packetMap[key]:
                            callback(packet[key])
            if (dt.datetime.now() - self.__lastHeartbeat).total_seconds() > 30:
                self.__log.warn("No heartbeats!")
                for callback in self.__packetMap['_nheartbeat']:
                    callback(None)

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

    def __processHeartbeat(self, packet):
        '''
        Internal callback to handle recognizing loss of heartbeat
        :param packet:
        :type packet:
        '''
        self.__lastHeartbeat = dt.datetime.now()

    def registerRxCallback(self, packetKey, callback):
        '''
        Registers a callback for the particular packet keyword
        :param packetKey: Keyword to recognize
        :type packetKey: String
        :param callback: Callback function
        :type callback: function pointer
        '''
        if packetKey in self.__packetMap:
            self.__packetMap[packetKey].append(callback)
        else:
            self.__packetMap[packetKey] = [callback]

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

