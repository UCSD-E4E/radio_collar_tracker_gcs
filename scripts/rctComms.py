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
# DATE      WHO Description
# -----------------------------------------------------------------------------
# 05/20/20  NH  Fixed SYS_autostart type in SETOPT command, added exception
#                 logging to both receivers
# 05/18/20  NH  Implemented binary data protocol, moved droneComms to rctComms,
#                 added callback functionality
# 04/26/20  NH  Added catch for JSON Decoder errors
# 04/25/20  NH  Moved Commands and PacketTypes to rctTransport
# 04/20/20  NH  Updated docstrings and imports
# 04/19/20  NH  Switched to RCT Transport for comms
# 04/16/20  NH  Moved Commands and Events to module scope, added helper for
#               sending commands, cleaned up eventing mechanisms
# 04/14/20  NH  Initial commit, fixed start parameters, added support for
#               multiline packet
#
###############################################################################
import struct
import logging
import datetime as dt
import threading
import enum
import binascii

import rctTransport
import traceback


class PACKET_CLASS(enum.Enum):
    STATUS = 0x01
    CONFIGURATION = 0x02
    UPGRADE = 0x03
    DATA = 0x04
    COMMAND = 0x05


class STATUS_ID(enum.Enum):
    HEARTBEAT = 0x01
    EXCEPTION = 0x02


class CONFIG_ID(enum.Enum):
    FREQUENCIES = 0x01
    OPTIONS = 0x01


class UPGRADE_ID(enum.Enum):
    STATUS = 0x01


class DATA_ID(enum.Enum):
    PING = 0x01
    VEHICLE = 0x02


class COMMAND_ID(enum.Enum):
    ACK = 0x01
    GETF = 0x02
    SETF = 0x03
    GETOPT = 0x04
    SETOPT = 0x05
    START = 0x07
    STOP = 0x09
    UPGRADE = 0x0B


class rctBinaryPacket:
    def __init__(self, payload: bytes, packetClass: int, packetID: int):
        self._payload = payload
        self._pclass = packetClass
        self._pid = packetID

    def to_bytes(self):
        payloadLen = len(self._payload)
        header = struct.pack('<BBBBH', 0xE4, 0xEb,
                             self._pclass, self._pid, payloadLen)
        msg = header + self._payload
        cksum = binascii.crc_hqx(msg, 0xFFFF).to_bytes(2, 'big')
        return msg + cksum

    def getClassIDCode(self):
        return self._pclass << 8 | self._pid

    def __str__(self):
        string = self.to_bytes().hex().upper()
        length = 4
        return '0x%s' % ' '.join(string[i:i + length] for i in range(0, len(string), length))

    def __repr__(self):
        string = self.to_bytes().hex().upper()
        length = 4
        return '0x%s' % ' '.join(string[i:i + length] for i in range(0, len(string), length))

    def __eq__(self, packet):
        return self.to_bytes() == packet.to_bytes()

    @classmethod
    def from_bytes(cls, packet: bytes):
        if binascii.crc_hqx(packet, 0xFFFF) != 0:
            raise RuntimeError("Checksum verification failed")
        if len(packet) < 8:
            raise RuntimeError("Packet too short!")
        s1, s2, pcls, pid, _ = struct.unpack("<BBBBH", packet[0:6])
        if s1 != 0xE4 or s2 != 0xEB:
            raise RuntimeError("Not a packet!")
        payload = packet[6:-2]
        return rctBinaryPacket(payload, pcls, pid)

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return True


class rctHeartBeatPacket(rctBinaryPacket):

    class SDR_STATES(enum.Enum):
        find_devices = 0
        wait_recycle = 1
        usrp_probe = 2
        rdy = 3
        fail = 4

    class EXT_SENSOR_STATES(enum.Enum):
        get_tty = 0
        get_msg = 1
        wait_recycle = 2
        rdy = 3
        fail = 4

    class STORAGE_STATES(enum.Enum):
        get_output_dir = 0
        check_output_dir = 1
        check_space = 2
        wait_recycle = 3
        rdy = 4
        fail = 5

    class SYS_STATES(enum.Enum):
        init = 0
        wait_init = 1
        wait_start = 2
        start = 3
        wait_end = 4
        finish = 5
        fail = 6

    class SW_STATES(enum.Enum):
        stop = 0
        start = 1

    def __init__(self, systemState: int,
                 sdrState: int,
                 sensorState: int,
                 storageState: int,
                 switchState: int,
                 timestamp: dt.datetime=None):
        self.systemState = systemState
        self.sdrState = sdrState
        self.sensorState = sensorState
        self.storageState = storageState
        self.switchState = switchState
        if timestamp is None:
            timestamp = dt.datetime.now()
        self.timestamp = timestamp
        self._pclass = 0x01
        self._pid = 0x01
        self._payload = struct.pack('<BBBBBBQ', 0x01, systemState,
                                    sdrState, sensorState,
                                    storageState, switchState,
                                    int(timestamp.timestamp() * 1e3))

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        if packetClass == 0x01 and packetID == 0x01:
            return True
        else:
            return False

    @classmethod
    def from_bytes(cls, packet: bytes):
        if binascii.crc_hqx(packet, 0xFFFF) != 0:
            raise RuntimeError("Checksum verification failed")
        if len(packet) < 8:
            raise RuntimeError("Packet too short!")
        s1, s2, pcls, pid, _ = struct.unpack("<BBBBH", packet[0:6])
        if s1 != 0xE4 or s2 != 0xEB:
            raise RuntimeError("Not a packet!")
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, systemState, sdrState, sensorState, storageState, switchState, timeMS = struct.unpack(
            '<BBBBBBQ', packet[6:-2])
        timestamp = dt.datetime.fromtimestamp(timeMS / 1e3)
        return rctHeartBeatPacket(systemState, sdrState, sensorState, storageState, switchState, timestamp)


class rctExceptionPacket(rctBinaryPacket):
    def __init__(self, e: str, tb: str):
        self._pclass = 0x01
        self._pid = 0x02
        self._payload = struct.pack('<BHH', 0x01, len(e), len(
            tb)) + e.encode('ascii') + tb.encode('ascii')
        self.exception = e
        self.traceback = tb

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x01 and packetID == 0x02

    @classmethod
    def from_bytes(cls, packet: bytes):
        header = packet[0:6]
        payload = packet[6:-2]
        _, _, pcls, pid, _ = struct.unpack("<BBBBH", header)
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, eLen, tbLen = struct.unpack('<BHH', payload[0x0000:0x0005])
        eStr = payload[0x0005:0x0005 + eLen].decode()
        tbStr = payload[0x0005 + eLen: 0x0005 + eLen + tbLen].decode()
        return rctExceptionPacket(eStr, tbStr)


class rctFrequenciesPacket(rctBinaryPacket):
    def __init__(self, frequencies: list):
        self._pclass = 0x02
        self._pid = 0x01
        self.frequencies = frequencies
        self._payload = struct.pack('<BB%dL' % len(
            frequencies), 0x01, len(frequencies), *tuple(frequencies))

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x02 and packetID == 0x01

    @classmethod
    def from_bytes(cls, packet: bytes):
        header = packet[0:6]
        payload = packet[6:-2]
        _, _, pcls, pid, _ = struct.unpack("<BBBBH", header)
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, nFreqs = struct.unpack('<BB', payload[0x0000:0x0002])
        freqs = struct.unpack(
            '<%dL' % nFreqs, payload[0x0002:0x0002 + 4 * nFreqs])
        return rctFrequenciesPacket(list(freqs))


class rctOptionsPacket(rctBinaryPacket):
    BASE_OPTIONS = 0x00
    EXP_OPTIONS = 0x01
    ENG_OPTIONS = 0xFF

    __baseOptionKeywords = ['SDR_centerFreq', 'SDR_samplingFreq', 'SDR_gain']
    __expOptionKeywords = ['DSP_pingWidth', 'DSP_pingSNR',
                           'DSP_pingMax', 'DSP_pingMin', 'SYS_outputDir']
    __engOptionKeywords = ['GPS_mode',
                           'GPS_baud', 'GPS_device', 'SYS_autostart']

    __keywordTypes = {
        'SDR_centerFreq': (int, '<L', 4),
        'SDR_samplingFreq': (int, '<L', 4),
        'SDR_gain': ((int, float), '<f', 4),
        'DSP_pingWidth': ((int, float), '<f', 4),
        'DSP_pingSNR': ((int, float), '<f', 4),
        'DSP_pingMax': ((int, float), '<f', 4),
        'DSP_pingMin': ((int, float), '<f', 4),
        'SYS_outputDir': (str, 's', 2),
        'GPS_mode': (int, '<B', 1),
        'GPS_baud': (int, '<L', 4),
        'GPS_device': (str, 's', 2),
        'SYS_autostart': (bool, '<?', 1)
    }

    def __init__(self, scope: int, **kwargs):
        if scope == self.BASE_OPTIONS:
            acceptedKeywords = self.__baseOptionKeywords
        elif scope == self.EXP_OPTIONS:
            acceptedKeywords = self.__baseOptionKeywords + self.__expOptionKeywords
        elif scope == self.ENG_OPTIONS:
            acceptedKeywords = self.__baseOptionKeywords + \
                self.__expOptionKeywords + self.__engOptionKeywords
        else:
            raise RuntimeError('Unrecognized scope')

        self._pclass = 0x02
        self._pid = 0x02
        self._payload = struct.pack('<BB', 0x01, scope)
        self.options = {}
        self.scope = scope
        for keyword in acceptedKeywords:
            assert(isinstance(kwargs[keyword],
                              self.__keywordTypes[keyword][0]))
            self.options[keyword] = kwargs[keyword]
            if self.__keywordTypes[keyword][1] != 's':
                self._payload += struct.pack(
                    self.__keywordTypes[keyword][1], kwargs[keyword])
            else:
                self._payload += struct.pack('<H', len(kwargs[keyword]))
                self._payload += kwargs[keyword].encode('ascii')

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x02 and packetID == 0x02

    @classmethod
    def from_bytes(cls, packet: bytes):
        header = packet[0:6]
        payload = packet[6:-2]
        _, _, pcls, pid, _ = struct.unpack("<BBBBH", header)
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, scope = struct.unpack('<BB', payload[0x0000:0x0002])
        idx = 0x0002
        options = {}
        if scope >= cls.BASE_OPTIONS:
            for keyword in cls.__baseOptionKeywords:
                fmt = cls.__keywordTypes[keyword]
                options[keyword], = struct.unpack(
                    fmt[1], payload[idx:idx + fmt[2]])
                idx += fmt[2]
        if scope >= cls.EXP_OPTIONS:
            for keyword in cls.__expOptionKeywords:
                fmt = cls.__keywordTypes[keyword]
                if fmt[1] != 's':
                    options[keyword], = struct.unpack(
                        fmt[1], payload[idx:idx + fmt[2]])
                    idx += fmt[2]
                else:
                    strlen, = struct.unpack('<H', payload[idx:idx + 2])
                    options[keyword] = payload[idx +
                                               2:idx + strlen + 2].decode()
                    idx += 2 + strlen
        if scope >= cls.ENG_OPTIONS:
            for keyword in cls.__engOptionKeywords:
                fmt = cls.__keywordTypes[keyword]
                if fmt[1] != 's':
                    options[keyword], = struct.unpack(
                        fmt[1], payload[idx:idx + fmt[2]])
                    idx += fmt[2]
                else:
                    strlen, = struct.unpack('<H', payload[idx:idx + 2])
                    options[keyword] = payload[idx +
                                               2:idx + strlen + 2].decode()
                    idx += 2 + strlen
        return rctOptionsPacket(scope, **options)


class rctUpgradeStatusPacket(rctBinaryPacket):
    UPGRADE_READY = 0x00
    UPGRADE_PROGRESS = 0x01
    UPGRADE_COMPLETE = 0xFE
    UPGRADE_FAILED = 0xFF

    def __init__(self, state: int, msg: str):
        self._pclass = 0x03
        self._pid = 0x01
        self._payload = struct.pack(
            '<BBH', 0x01, state, len(msg)) + msg.encode('ascii')
        self.state = state
        self.msg = msg

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x03 and packetID == 0x01

    @classmethod
    def from_bytes(cls, packet: bytes):
        header = packet[0:6]
        payload = packet[6:-2]
        _, _, pcls, pid, _ = struct.unpack("<BBBBH", header)
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, state, strlen = struct.unpack('<BBH', payload[0x0000: 0x0004])
        msg = payload[0x0004:0x0004 + strlen].decode()
        return rctUpgradeStatusPacket(state, msg)


class rctPingPacket(rctBinaryPacket):
    def __init__(self, lat: float, lon: float, alt: float, txp: float, txf: int, timestamp: dt.datetime = None):
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.txp = txp
        self.txf = txf
        if timestamp is None:
            timestamp = dt.datetime.now()
        self.timestamp = timestamp

        self._pclass = 0x04
        self._pid = 0x01
        self._payload = struct.pack("<BQllHfL", 0x01, int(timestamp.timestamp(
        ) * 1e3), int(lat * 1e7), int(lon * 1e7), int(alt * 10), txp, txf)

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x04 and packetID == 0x01

    @classmethod
    def from_bytes(cls, packet: bytes):
        header = packet[0:6]
        payload = packet[6:-2]
        _, _, pcls, pid, _ = struct.unpack("<BBBBH", header)
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, timeMS, lat7, lon7, alt1, txp, txf = struct.unpack(
            '<BQllHfL', payload)
        timestamp = dt.datetime.fromtimestamp(timeMS / 1e3)
        lat = lat7 / 1e7
        lon = lon7 / 1e7
        alt = alt1 / 10
        return rctPingPacket(lat, lon, alt, txp, txf, timestamp)


class rctVehiclePacket(rctBinaryPacket):
    def __init__(self, lat: float, lon: float, alt: float, hdg: int, timestamp: dt.datetime = None):
        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.hdg = hdg
        if timestamp is None:
            timestamp = dt.datetime.now()
        self.timestamp = timestamp

        self._pclass = 0x04
        self._pid = 0x02
        self._payload = struct.pack("<BQllHH", 0x01, int(timestamp.timestamp(
        ) * 1e3), int(lat * 1e7), int(lon * 1e7), int(alt * 10), hdg)

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x04 and packetID == 0x02

    @classmethod
    def from_bytes(cls, packet: bytes):
        header = packet[0:6]
        payload = packet[6:-2]
        _, _, pcls, pid, _ = struct.unpack("<BBBBH", header)
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, timeMS, lat7, lon7, alt1, hdg = struct.unpack(
            '<BQllHH', payload)
        timestamp = dt.datetime.fromtimestamp(timeMS / 1e3)
        lat = lat7 / 1e7
        lon = lon7 / 1e7
        alt = alt1 / 10
        return rctVehiclePacket(lat, lon, alt, hdg, timestamp)


class rctACKCommand(rctBinaryPacket):
    def __init__(self, commandID: int, ack: bool, timestamp: dt.datetime = None):
        self.commandID = commandID
        self.ack = ack
        if timestamp is None:
            timestamp = dt.datetime.now()
        self.timestamp = timestamp
        self._pclass = 0x05
        self._pid = 0x01
        self._payload = struct.pack(
            '<BB?Q', 0x01, commandID, ack, int(timestamp.timestamp() * 1e3))

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x05 and packetID == 0x01

    @classmethod
    def from_bytes(cls, packet: bytes):
        header = packet[0:6]
        payload = packet[6:-2]
        _, _, pcls, pid, _ = struct.unpack("<BBBBH", header)
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, commandID, ack, timeMS = struct.unpack('<BB?Q', payload)
        timestamp = dt.datetime.fromtimestamp(timeMS / 1e3)
        return rctACKCommand(commandID, ack, timestamp)


class rctGETFCommand(rctBinaryPacket):
    def __init__(self):
        self._pclass = 0x05
        self._pid = 0x02
        self._payload = b'\x01'

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x05 and packetID == 0x02

    @classmethod
    def from_bytes(cls, packet: bytes):
        return rctGETFCommand()


class rctSETFCommand(rctBinaryPacket):
    def __init__(self, frequencies: list):
        self._pclass = 0x05
        self._pid = 0x03
        self.frequencies = frequencies
        self._payload = struct.pack('<BB%dL' % len(
            frequencies), 0x01, len(frequencies), *tuple(frequencies))

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x05 and packetID == 0x03

    @classmethod
    def from_bytes(cls, packet: bytes):
        header = packet[0:6]
        payload = packet[6:-2]
        _, _, pcls, pid, _ = struct.unpack("<BBBBH", header)
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, nFreqs = struct.unpack('<BB', payload[0x0000:0x0002])
        freqs = struct.unpack(
            '<%dL' % nFreqs, payload[0x0002:0x0002 + 4 * nFreqs])
        return rctSETFCommand(list(freqs))


class rctGETOPTCommand(rctBinaryPacket):
    BASE_OPTIONS = 0x00
    EXP_OPTIONS = 0x01
    ENG_OPTIONS = 0xFF

    def __init__(self, scope: int):
        self._pclass = 0x05
        self._pid = 0x04
        self._payload = struct.pack('<BB', 0x01, scope)
        self.scope = scope

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x05 and packetID == 0x04

    @classmethod
    def from_bytes(cls, packet: bytes):
        header = packet[0:6]
        payload = packet[6:-2]
        _, _, pcls, pid, _ = struct.unpack("<BBBBH", header)
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, scope = struct.unpack('<BB', payload[0x0000:0x0002])
        return rctGETOPTCommand(scope)


class rctSETOPTCommand(rctBinaryPacket):
    BASE_OPTIONS = 0x00
    EXP_OPTIONS = 0x01
    ENG_OPTIONS = 0xFF

    __baseOptionKeywords = ['SDR_centerFreq', 'SDR_samplingFreq', 'SDR_gain']
    __expOptionKeywords = ['DSP_pingWidth', 'DSP_pingSNR',
                           'DSP_pingMax', 'DSP_pingMin', 'SYS_outputDir']
    __engOptionKeywords = ['GPS_mode',
                           'GPS_baud', 'GPS_device', 'SYS_autostart']

    __keywordTypes = {
        'SDR_centerFreq': (int, '<L', 4),
        'SDR_samplingFreq': (int, '<L', 4),
        'SDR_gain': ((int, float), '<f', 4),
        'DSP_pingWidth': ((int, float), '<f', 4),
        'DSP_pingSNR': ((int, float), '<f', 4),
        'DSP_pingMax': ((int, float), '<f', 4),
        'DSP_pingMin': ((int, float), '<f', 4),
        'SYS_outputDir': (str, 's', 2),
        'GPS_mode': (int, '<B', 1),
        'GPS_baud': (int, '<L', 4),
        'GPS_device': (str, 's', 2),
        'SYS_autostart': (bool, '<?', 1)
    }

    def __init__(self, scope: int, **kwargs):
        if scope >= self.BASE_OPTIONS:
            acceptedKeywords = self.__baseOptionKeywords
        if scope >= self.EXP_OPTIONS:
            acceptedKeywords = self.__baseOptionKeywords + self.__expOptionKeywords
        if scope >= self.ENG_OPTIONS:
            acceptedKeywords = self.__baseOptionKeywords + \
                self.__expOptionKeywords + self.__engOptionKeywords

        self._pclass = 0x05
        self._pid = 0x05
        self._payload = struct.pack('<BB', 0x01, scope)
        self.options = {}
        self.scope = scope
        for keyword in acceptedKeywords:
            assert(isinstance(kwargs[keyword],
                              self.__keywordTypes[keyword][0]))
            self.options[keyword] = kwargs[keyword]
            if self.__keywordTypes[keyword][1] != 's':
                self._payload += struct.pack(
                    self.__keywordTypes[keyword][1], kwargs[keyword])
            else:
                self._payload += struct.pack('<H', len(kwargs[keyword]))
                self._payload += kwargs[keyword].encode('ascii')

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x05 and packetID == 0x05

    @classmethod
    def from_bytes(cls, packet: bytes):
        header = packet[0:6]
        payload = packet[6:-2]
        _, _, pcls, pid, _ = struct.unpack("<BBBBH", header)
        if not cls.matches(pcls, pid):
            raise RuntimeError("Incorrect packet type")
        _, scope = struct.unpack('<BB', payload[0x0000:0x0002])
        idx = 0x0002
        options = {}
        if scope >= cls.BASE_OPTIONS:
            for keyword in cls.__baseOptionKeywords:
                fmt = cls.__keywordTypes[keyword]
                options[keyword], = struct.unpack(
                    fmt[1], payload[idx:idx + fmt[2]])
                idx += fmt[2]
        if scope >= cls.EXP_OPTIONS:
            for keyword in cls.__expOptionKeywords:
                fmt = cls.__keywordTypes[keyword]
                if fmt[1] != 's':
                    options[keyword], = struct.unpack(
                        fmt[1], payload[idx:idx + fmt[2]])
                    idx += fmt[2]
                else:
                    strlen, = struct.unpack('<H', payload[idx:idx + 2])
                    options[keyword] = payload[idx +
                                               2:idx + strlen + 2].decode()
                    idx += 2 + strlen
        if scope >= cls.ENG_OPTIONS:
            for keyword in cls.__engOptionKeywords:
                fmt = cls.__keywordTypes[keyword]
                if fmt[1] != 's':
                    options[keyword], = struct.unpack(
                        fmt[1], payload[idx:idx + fmt[2]])
                    idx += fmt[2]
                else:
                    strlen, = struct.unpack('<H', payload[idx:idx + 2])
                    options[keyword] = payload[idx +
                                               2:idx + strlen + 2].decode()
                    idx += 2 + strlen
        return rctSETOPTCommand(scope, **options)


class rctSTARTCommand(rctBinaryPacket):
    def __init__(self):
        self._pclass = 0x05
        self._pid = 0x07
        self._payload = b'\x01'

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x05 and packetID == 0x07

    @classmethod
    def from_bytes(cls, packet: bytes):
        return rctSTARTCommand()


class rctSTOPCommand(rctBinaryPacket):
    def __init__(self):
        self._pclass = 0x05
        self._pid = 0x09
        self._payload = b'\x01'

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x05 and packetID == 0x09

    @classmethod
    def from_bytes(cls, packet: bytes):
        return rctSTOPCommand()


class rctUPGRADECommand(rctBinaryPacket):
    def __init__(self):
        self._pclass = 0x05
        self._pid = 0x0B
        self._payload = b'\x01'

    @classmethod
    def matches(cls, packetClass: int, packetID: int):
        return packetClass == 0x05 and packetID == 0x0B

    @classmethod
    def from_bytes(cls, packet: bytes):
        return rctUPGRADECommand()


class rctBinaryPacketFactory:
    class State(enum.Enum):
        FIND_SYNC = 0
        HEADER = 1
        PAYLOAD = 2
        CKSUM = 3
        VALIDATE = 4

    packetMap = {0x0101: rctHeartBeatPacket,
                 0x0102: rctExceptionPacket,
                 0x0201: rctFrequenciesPacket,
                 0x0202: rctOptionsPacket,
                 0x0301: rctUpgradeStatusPacket,
                 0x0401: rctPingPacket,
                 0x0402: rctVehiclePacket,
                 0x0501: rctACKCommand,
                 0x0502: rctGETFCommand,
                 0x0503: rctSETFCommand,
                 0x0504: rctGETOPTCommand,
                 0x0505: rctSETOPTCommand,
                 0x0507: rctSTARTCommand,
                 0x0509: rctSTOPCommand,
                 0x050B: rctUPGRADECommand}

    def __init__(self):
        self.__state = self.State.FIND_SYNC
        self.__payloadLen = 0

    def parseByte(self, data: int):
        if self.__state == self.State.FIND_SYNC:
            if data == 0xE4:
                self.__state = self.State.HEADER
                self.__buffer = bytearray()
                self.__buffer.append(data)
            return None
        elif self.__state == self.State.HEADER:
            self.__buffer.append(data)
            if len(self.__buffer) == 0x0006:
                self.__state = self.State.PAYLOAD
                self.__payloadLen, = struct.unpack(
                    '<H', self.__buffer[0x0004:0x0006])
            return None
        elif self.__state == self.State.PAYLOAD:
            self.__buffer.append(data)
            if len(self.__buffer) == self.__payloadLen + 0x0006:
                self.__state = self.State.CKSUM
            return None
        elif self.__state == self.State.CKSUM:
            self.__buffer.append(data)
            self.__state = self.State.VALIDATE
            return None
        elif self.__state == self.State.VALIDATE:
            self.__buffer.append(data)
            if binascii.crc_hqx(self.__buffer, 0xFFFF) != 0:
                raise RuntimeError("Checksum verification failed")
            packetID, = struct.unpack('>H', self.__buffer[0x0002:0x0004])
            self.__state = self.State.FIND_SYNC
            if packetID not in self.packetMap:
                return rctBinaryPacket.from_bytes(self.__buffer)
            else:
                return self.packetMap[packetID].from_bytes(self.__buffer)

    def parseBytes(self, data: bytes):
        packets = []
        for byte in data:
            retval = self.parseByte(byte)
            if retval is not None:
                packets.append(retval)
        return packets


class EVENTS(enum.Enum):
    STATUS_HEARTBEAT = 0x0101
    STATUS_EXCEPTION = 0x0102
    CONFIG_FREQUENCIES = 0x0201
    CONFIG_OPTIONS = 0x0202
    UPGRADE_STATUS = 0x0301
    DATA_PING = 0x0401
    DATA_VEHCLE = 0x0402
    COMMAND_ACK = 0x0501
    COMMAND_GETF = 0x0502
    COMMAND_SETF = 0x0503
    COMMAND_GETOPT = 0x0504
    COMMAND_SETOPT = 0x0505
    COMMAND_START = 0x0507
    COMMAND_STOP = 0x0509
    COMMAND_UPGRADE = 0x050B
    GENERAL_NO_HEARTBEAT = 0x10000
    GENERAL_EXCEPTION = 0x20000
    GENERAL_UNKNOWN = 0x30000


class gcsComms:
    '''
    Radio Collar Tracker UDP Interface
    '''
    __BUFFER_LEN = 1024

    def __init__(self, port: rctTransport.RCTAbstractTransport):
        '''
        Initializes the UDP interface on the specified port.  Also specifies a
        filename to use as a logfile, which defaults to no log.

        :param port: Port object
        :type port: rctTransport.RCTAbstractTransport
        :param originString: Origin string
        :type originString: str
        '''
        self.__log = logging.getLogger('rctGCS.gcsComms')
        self.sock = port

        self.__receiverThread = None
        self.__log.info('RTC gcsComms created')
        self.HS_run = False
        self.__mavIP = None
        self.__lastHeartbeat = None
        self.__packetMap = {
            EVENTS.STATUS_HEARTBEAT.value: [self.__processHeartbeat],
            EVENTS.GENERAL_NO_HEARTBEAT.value: [],
            EVENTS.GENERAL_EXCEPTION.value: [],
            EVENTS.GENERAL_UNKNOWN.value: [],
        }

        self.__parser = rctBinaryPacketFactory()

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
        for _ in range(timeout):
            try:
                data, addr = self.sock.receive(1024, 1)
                packets = self.__parser.parseBytes(data)
                for packet in packets:
                    if isinstance(packet, rctHeartBeatPacket):
                        self.__log.info("Received heartbeat %s" % (packet))
                        self.__lastHeartbeat = dt.datetime.now()
                        return addr, packets
            except TimeoutError:
                pass
            if guiTick is not None:
                guiTick()
        self.__log.error("Failed to receive any heartbeats")
        return (None, None)

    def __receiverLoop(self):
        '''
        Receiver thread
        '''
        self.__log.info('RCT gcsComms rxThread started')

        while self.HS_run:
            try:
                data, addr = self.sock.receive(self.__BUFFER_LEN, 1)
                self.__log.info("Received: %s" % data.hex())
                packets = self.__parser.parseBytes(data)
                for packet in packets:
                    packetCode = packet.getClassIDCode()
                    try:
                        for callback in self.__packetMap[packetCode]:
                            callback(packet=packet, addr=addr)
                    except KeyError:
                        for callback in self.__packetMap[EVENTS.GENERAL_UNKNOWN.value]:
                            callback(packet=packet, addr=addr)
                    except Exception as e:
                        self.__log.error("Exception %s: %s" %
                                         (type(e), str(e)))
                        self.__log.error("Traceback: %s" %
                                         (traceback.format_exc()))

                        for callback in self.__packetMap[EVENTS.GENERAL_EXCEPTION.value]:
                            callback(packet=packet, addr=addr)

            except TimeoutError:
                pass

            if (dt.datetime.now() - self.__lastHeartbeat).total_seconds() > 30:
                self.__log.warning(
                    "No heartbeats, last heartbeat at %s" % self.__lastHeartbeat)
                for callback in self.__packetMap[EVENTS.GENERAL_NO_HEARTBEAT.value]:
                    callback(packet=None, addr=None)

    def start(self, gui=None):
        '''
        Starts the receiver.
        '''
        self.__log.info("RCT gcsComms starting...")
        self.sock.open()
        self.__mavIP, packets = self.waitForHeartbeat(guiTick=gui)
        if self.__mavIP is None:
            raise RuntimeError("Failed to receive heartbeats")
        for packet in packets:
            packetCode = packet.getClassIDCode()
            try:
                for callback in self.__packetMap[packetCode]:
                    callback(packet=packet, addr=self.__mavIP)
            except KeyError:
                for callback in self.__packetMap[EVENTS.GENERAL_UNKNOWN.value]:
                    callback(packet=packet, addr=self.__mavIP)
            except Exception:
                for callback in self.__packetMap[EVENTS.GENERAL_EXCEPTION.value]:
                    callback(packet=packet, addr=self.__mavIP)
        self.HS_run = True
        self.__receiverThread = threading.Thread(target=self.__receiverLoop)
        self.__receiverThread.start()
        self.__log.info('RCT gcsComms started')

    def stop(self):
        '''
        Stops the receiver.
        '''
        self.__log.info("HS_run set to False")
        self.HS_run = False
        if self.__receiverThread is not None:
            self.__receiverThread.join(timeout=1)
        self.__log.info('RCT gcsComms stopped')
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
        if event.value in self.__packetMap:
            self.__packetMap[event.value].append(callback)
        else:
            self.__packetMap[event.value] = [callback]

    def unregisterCallback(self, event: EVENTS, callback):
        self.__packetMap[event.value].remove(callback)

    def sendMessage(self, payload: bytes, packetClass: int, packetID: int):
        '''
        Sends the specified dictionary as a packet
        :param packet: Packet to send
        :type packet: dictionary
        '''
        assert(isinstance(payload, bytes))
        payloadLen = len(payload)
        header = struct.pack('<BBBBH', 0xE4, 0xEb,
                             packetClass, packetID, payloadLen)
        msg = header + payload
        cksum = binascii.crc_hqx(msg, 0xFFFF).to_bytes(2, 'big')
        self.__log.info("Send: %s" % ((msg + cksum).hex()))
        self.sock.send(msg, self.__mavIP)

    def sendPacket(self, packet: rctBinaryPacket):
        '''
        Sends the specified packet object
        :param packet:
        :type packet:
        '''

        self.__log.info("Send: %s" % (packet))
        self.sock.send(packet.to_bytes(), self.__mavIP)


class mavComms:

    def __init__(self, port: rctTransport.RCTAbstractTransport):
        self.__log = logging.getLogger('rctComms.mavComms')
        self.__port = port

        self.__rxThread = None
        self.__log.info('RCT mavComms created')
        self.HS_run = False
        self.__gcsAddr = None
        self.__packetMap = {
            EVENTS.GENERAL_EXCEPTION.value: [],
            EVENTS.GENERAL_UNKNOWN.value: [],
        }

        self.__parser = rctBinaryPacketFactory()

    def start(self):
        self.__log.info('RCT mavComms starting...')
        self.HS_run = True
        self.__port.open()
        self.__rxThread = threading.Thread(target=self.__receiver)
        self.__rxThread.start()

    def stop(self):
        self.__log.info('HS_run set to False')
        self.HS_run = False
        if self.__rxThread is not None:
            self.__rxThread.join(timeout=1)
        self.__port.close()
        self.__log.info('RCT mavComms stopped')

    def sendToGCS(self, packet: rctBinaryPacket):
        self.sendPacket(packet, self.__gcsAddr)

    def sendToAll(self, packet: rctBinaryPacket):
        self.sendPacket(packet, None)

    def sendPacket(self, packet: rctBinaryPacket, dest: str):
        self.__log.info('Send: %s' % (packet))
        print("TX: %s" % packet)
        self.__port.send(packet.to_bytes(), dest)

    def sendPing(self, ping: rctPingPacket):
        self.sendPacket(ping, None)

    def sendException(self, exception: str, traceback: str):
        packet = rctExceptionPacket(exception, traceback)
        self.sendToAll(packet)

    def __receiver(self):
        while self.HS_run is True:
            try:
                data, addr = self.__port.receive(1024, 1)
                self.__log.info('Received: %s' % data.hex())
                packets = self.__parser.parseBytes(data)
                for packet in packets:
                    print("RX: %s" % packet)
                    packetCode = packet.getClassIDCode()
                    try:
                        for callback in self.__packetMap[packetCode]:
                            callback(packet=packet, addr=addr)
                    except KeyError:
                        for callback in self.__packetMap[EVENTS.GENERAL_UNKNOWN.value]:
                            callback(packet=packet, addr=addr)
            except TimeoutError:
                continue
            except Exception as e:
                self.sendException(str(e), traceback.format_exc())
                self.__log.error("Exception %s: %s" %
                                 (type(e), str(e)))
                self.__log.error("Traceback: %s" % (traceback.format_exc()))
                continue

    def registerCallback(self, event: EVENTS, callback):
        if event.value in self.__packetMap:
            self.__packetMap[event.value].append(callback)
        else:
            self.__packetMap[event.value] = [callback]
