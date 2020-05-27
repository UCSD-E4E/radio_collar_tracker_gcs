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
# 05/25/20  NH  Added getter for pings for LocationEstimator and DataManager
# 05/18/20  NH  Added logic to convert rctPing to/from rctPingPacket
# 05/05/20  NH  Added estimator
# 04/25/20  NH  Moved rctPings to own module
#
###############################################################################

import datetime as dt
import numpy as np
from scipy.optimize import least_squares
import utm
import rctComms


class rctPing:
    def __init__(self, lat: float, lon: float, amplitude: float, freq: int, alt: float, time: float):
        self.lat = lat
        self.lon = lon
        self.amplitude = amplitude
        self.freq = freq
        self.alt = alt
        self.time = dt.datetime.fromtimestamp(time)

    def toNumpy(self):
        # X, Y, Z, A
        easting, northing, _, _ = utm.from_latlon(self.lat, self.lon)
        return np.array([easting, northing, self.alt, 20 * np.log10(self.amplitude)])

    def toDict(self):
        d = {}
        d['lat'] = int(self.lat * 1e7)
        d['lon'] = int(self.lon * 1e7)
        d['amp'] = int(self.amplitude)
        d['txf'] = self.freq
        d['alt'] = self.alt
        d['time'] = int(self.time.timestamp() / 1e3)

    def toPacket(self):
        return rctComms.rctPingPacket(self.lat, self.lon, self.alt, self.amplitude, self.freq, self.time)

    @classmethod
    def fromDict(cls, packet: dict):
        latStr = packet['lat']
        lonStr = packet['lon']
        ampStr = packet['amp']
        freqStr = packet['txf']
        altStr = packet['alt']
        timeStr = packet['time']

        lat = float(latStr) / 1e7
        lon = float(lonStr) / 1e7
        amp = float(ampStr)
        freq = int(freqStr)
        alt = float(altStr)
        time = int(timeStr) / 1e3

        return rctPing(lat, lon, amp, freq, alt, time)

    @classmethod
    def fromPacket(cls, packet: rctComms.rctPingPacket):
        lat = packet.lat
        lon = packet.lon
        alt = packet.alt
        amp = packet.txp
        freq = packet.txf
        time = packet.timestamp
        return rctPing(lat, lon, amp, freq, alt, time)


class DataManager:
    def __init__(self):
        self.__estimators = {}

    def addPing(self, ping: rctPing):
        pingFreq = ping.freq
        if pingFreq not in self.__estimators:
            self.__estimators[pingFreq] = LocationEstimator()
        self.__estimators[pingFreq].addPing(ping)
        return self.__estimators[pingFreq].doEstimate()

    def getEstimate(self, frequency: int):
        estimator = self.__estimators[frequency]
        return estimator.getEstimate()

    def getFrequencies(self):
        '''
        Returns a list of the transmitters detected so far
        '''
        return list(self.__estimators.keys())

    def getPings(self, frequency: int):
        '''
        Returns a list of the pings associated with the specified frequency
        :param frequency:    Transmitter frequency to get pings for
        :type frequency:    int
        '''
        estimator = self.__estimators[frequency]
        return estimator.getPings()


class LocationEstimator:
    def __init__(self):
        '''
        Creates a new LocationEstimator object.
        '''

        self.__pings = []

        self.__params = None

        self.__staleEstimate = True

        self.result = None

    def addPing(self, ping: rctPing):
        self.__pings.append(ping.toNumpy())

    def doEstimate(self):
        if len(self.__pings) < 4:
            return None

        # have enough data to start
#         if self.__params is None:
        if True:
            # Pings is now the data matrix of n x 4
            # Columns are X_rx, Y_rx, Z_rx, P_rx
            pings = np.array(self.__pings)
            # first estimate, generate initial params from data
            # Location is average of current measurements
            # Power is max of measurements
            # N_0 = 4
            X_tx_0 = np.mean(pings[:, 0])
            Y_tx_0 = np.mean(pings[:, 1])
            P_tx_0 = np.max(pings[:, 3])
            n_0 = 2
            self.__params = np.array([X_tx_0, Y_tx_0, P_tx_0, n_0])
        res_x = least_squares(self.__residuals, self.__params, bounds=(
            [0, 167000, -np.inf, 2], [10000000, 833000, np.inf, np.inf]))
        # bounds=([0, 167000, -np.inf, 2], [10000000, 833000, np.inf, 6]),
        if res_x.success:
            self.__params = res_x.x
            self.__staleEstimate = False
        else:
            self.__staleEstimate = True

        self.result = res_x

        return self.__params, self.__staleEstimate

    def dToPrx(self, pingVector: np.ndarray, paramVector: np.ndarray):
        l_rx = pingVector[0:3]
        l_tx = np.array([paramVector[0], paramVector[1], 0])
        P_tx = paramVector[2]
        n = paramVector[3]

        d = np.linalg.norm(l_rx - l_tx)
        if d < 0.01:
            d = 0.01

        Prx = P_tx - 10 * n * np.log10(d)
        return Prx

    def __residuals(self, paramVect):
        result = np.zeros(len(self.__pings))

        for i in range(len(self.__pings)):
            pingVector = self.__pings[i]
            result[i] = pingVector[3] - \
                self.dToPrx(pingVector, paramVect)

        return result

    def __doPrecision(self):
        tf = np.eye(3)
        raise NotImplementedError()

    def getEstimate(self):
        if self.__params is None:
            return None
        return self.__params, self.__staleEstimate

    def _getComparator(self):
        pass

    def getPings(self):
        return self.__pings
