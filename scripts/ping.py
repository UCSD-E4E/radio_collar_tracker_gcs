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
# 04/25/20  NH  Moved rctPings to own module
#
###############################################################################

import datetime as dt


class rctPing:
    def __init__(self, lat: float, lon: float, amplitude: float, freq: int, alt: float, time: float):
        self.lat = lat
        self.lon = lon
        self.amplitude = amplitude
        self.freq = freq
        self.alt = alt
        self.time = dt.datetime.fromtimestamp(time)

    def toDict(self):
        d = {}
        d['lat'] = self.lat * 1e7
        d['lon'] = self.lon * 1e7
        d['amp'] = self.amplitude
        d['txf'] = self.freq
        d['alt'] = self.alt
        d['time'] = self.time.timestamp()

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
        time = int(timeStr)

        return rctPing(lat, lon, amp, freq, alt, time)
