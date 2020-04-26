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
# DATE      WHO DESCRIPTION
# -----------------------------------------------------------------------------
# 04/25/20  NH  Moved Commands and PacketTypes to rctTransport
# 04/19/20  NH  Initial commit: base class, UDP Transport
#
###############################################################################

import abc
import socket
import select
import os
import enum


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


class COMMANDS(enum.Enum):
    GET_FREQUENCY = "getF"
    START = 'start'
    STOP = 'stop'
    SET_FREQUENCY = 'setF'
    GET_OPTIONS = 'getOpts'
    SET_OPTIONS = 'setOpts'
    WRITE_OPTIONS = 'writeOpts'
    UPGRADE = 'upgrade'


class RCTAbstractTransport(abc.ABC):
    @abc.abstractmethod
    def __init__(self):
        pass

    @abc.abstractmethod
    def open(self):
        pass

    @abc.abstractmethod
    def receive(self, bufLen: int, timeout: int=None):
        pass

    @abc.abstractmethod
    def send(self, data: bytes, dest):
        pass

    @abc.abstractmethod
    def close(self):
        pass


class RCTUDPClient(RCTAbstractTransport):
    def __init__(self, port: int = 9000):
        self.__socket = None
        self.__port = port

    def open(self):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__socket.bind(("", self.__port))

    def close(self):
        self.__socket.close()

    def receive(self, bufLen: int, timeout: int=None):
        ready = select.select([self.__socket], [], [], timeout)
        if ready[0]:
            data, addr = self.__socket.recvfrom(bufLen)
            return data, addr[0]
        else:
            raise TimeoutError

    def send(self, data: bytes, dest):
        self.__socket.sendto(data, (dest, self.__port))


class RCTUDPServer(RCTAbstractTransport):
    def __init__(self, port: int = 9000):
        self.__socket = None
        self.__port = port

    def open(self):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.__socket.setblocking(0)
        self.__socket.bind(("", self.__port))

    def close(self):
        self.__socket.close()

    def receive(self, bufLen: int, timeout: int = None):
        ready = select.select([self.__socket], [], [], timeout)
        if ready[0]:
            data, addr = self.__socket.recvfrom(bufLen)
            return data, addr[0]
        else:
            raise TimeoutError

    def send(self, data: bytes, dest):
        if dest is None:
            dest = '255.255.255.255'
        self.__socket.sendto(data, (dest, self.__port))


class RCTPipeClient(RCTAbstractTransport):
    def __init__(self):
        pass

    def open(self):
        if not os.path.exists("/tmp/rctClient2Simulator"):
            os.mkfifo('/tmp/rctClient2Simulator')
        if not os.path.exists("/tmp/rctSimulator2Client"):
            os.mkfifo('/tmp/rctSimulator2Client')

        self.__inFile = os.open(
            '/tmp/rctSimulator2Client', os.O_NONBLOCK | os.O_RDONLY)
        self.__outFile = open('/tmp/rctClient2Simulator', 'wb')

    def close(self):
        pass

    def receive(self, bufLen: int, timeout: int = None):
        pass

    def send(self, data: bytes, dest):
        pass
