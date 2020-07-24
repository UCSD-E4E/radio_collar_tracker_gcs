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
# 07/23/20  NH  Added docstring for base class
# 05/25/20  NH  Started docstrings
# 05/20/20  NH  Fixed select condition in TCP clients
# 05/18/20  NH  Removed unused enumerations
# 04/26/20  NH  Added TCP Server and Client
# 04/25/20  NH  Moved Commands and PacketTypes to rctTransport
# 04/19/20  NH  Initial commit: base class, UDP Transport
#
###############################################################################

import abc
import socket
import select
import os


class RCTAbstractTransport(abc.ABC):
    '''
    Abstract transport class - all transport types should inherit from this 
    '''
    @abc.abstractmethod
    def __init__(self):
        '''
        Constructor for the RCTAbstractTransport class.  This constructor shall
        provision resources for the port, but it shall not open the port.  That
        is, other processes must be able to access the port after this function
        returns.
        '''

    @abc.abstractmethod
    def open(self):
        '''
        Opens the port represented by the RCTAbstractTransport class.  After
        this function returns, the port shall be owned by this process and be
        capable of sending and receiving data.  Failure to open the port shall
        result in an Exception being thrown.
        '''

    @abc.abstractmethod
    def receive(self, bufLen: int, timeout: int=None):
        '''
        Receives data from the port.  This function shall attempt to retrieve at
        most buflen bytes from the port within timeout seconds.
        
        If there is less than buflen bytes available when this function is 
        called, the function shall return all available bytes immediately.  If 
        there are  more than buflen bytes available when this function is 
        called, the function shall return exactly buflen bytes.  If there is no 
        data available when this function is called, this function shall wait at
        most timeout seconds.  If any data arrives within timeout seconds, that 
        data shall be immediately returned.  If no data arrives, the function 
        shall raise an Exception.
        
        This function shall return a tuple containing two elements.  The first
        element shall be a bytes object containing the data received.  The 
        second element shall be a string denoting the originating machine.
        
        Making a call to this function when the port is not open shall result in
        an Exception.
        
        :param bufLen:    Maximum number of bytes to return
        :param timeout:    Maximum number of seconds to wait for data
        '''

    @abc.abstractmethod
    def send(self, data: bytes, dest):
        '''
        Sends data to the specified destination from the port.  This function
        shall transmit the provided data to the specified destination.
        
        This function shall block until all data is transmitted.
        
        :param data:    Data to transmit
        :param dest:    Destination to route data to
        '''

    @abc.abstractmethod
    def close(self):
        '''
        Closes the underlying port.  This function shall release the underlying
        port to be used by other processes.  Calling this function on a port
        that is already closed shall not result in an Exception.  Subsequent
        calls to open() shall not fail if the port is available for this process
        to own.
        '''


class RCTUDPClient(RCTAbstractTransport):
    def __init__(self, port: int = 9000):
        self.__socket = None
        self.__port = port

    def open(self):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.__socket.bind(("", self.__port))

    def close(self):
        try:
            self.__socket.close()
        except:
            pass

    def receive(self, bufLen: int, timeout: int=None):
        ready = select.select([self.__socket], [], [], timeout)
        if len(ready[0]) == 1:
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


class RCTTCPClient(RCTAbstractTransport):
    def __init__(self, port: int, addr: str):
        self.__target = (addr, port)
        self.__socket = None

    def open(self):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.__socket.connect(self.__target)

    def close(self):
        self.__socket.shutdown(socket.SHUT_RDWR)

    def receive(self, bufLen: int, timeout: int=None):
        ready = select.select([self.__socket], [], [], timeout)
        if len(ready[0]) == 1:
            data = self.__socket.recv(bufLen)
            return data, self.__target[0]
        else:
            raise TimeoutError

    def send(self, data: bytes, dest=None):
        self.__socket.send(data)


class RCTTCPServer(RCTAbstractTransport):
    def __init__(self, port: int):
        self.__port = port
        self.__socket = None
        self.__conn = None
        self.__addr = None

    def open(self):
        self.__socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__socket.bind(('', self.__port))
        self.__socket.listen()
        self.__conn, self.__addr = self.__socket.accept()

    def close(self):
        self.__socket.close()

    def receive(self, bufLen: int, timeout: int=None):
        ready = select.select([self.__conn], [], [], timeout)
        if ready[0]:
            data = self.__conn.recv(bufLen)
            return data, self.__addr[0]
        else:
            raise TimeoutError

    def send(self, data: bytes, dest=None):
        self.__conn.send(data)
