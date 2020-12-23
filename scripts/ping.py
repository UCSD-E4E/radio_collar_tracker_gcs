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
# 10/05/20  ML  Added estimate precision visualization function
# 05/25/20  NH  Added getter for pings for LocationEstimator and DataManager
# 05/18/20  NH  Added logic to convert rctPing to/from rctPingPacket
# 05/05/20  NH  Added estimator
# 04/25/20  NH  Moved rctPings to own module
#
###############################################################################

import datetime as dt
import numpy as np
from scipy.optimize import least_squares
from scipy.stats import norm
import utm
import rctComms
import time
import gdal
import osr
import multiprocessing


#from Library.python.plugins.processing.tests import GdalAlgorithmsGeneralTest


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
        #print(20 * np.log10(self.amplitude))
        return np.array([easting, northing, self.alt, self.amplitude])
    
    

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
        t = packet.timestamp
        tup = t.timetuple()
        tim = time.mktime(tup)
        return rctPing(lat, lon, amp, freq, alt, tim)



def residuals(x, data):
    '''
    Calculates the error for the signal propagation model parameterized by x 
    over the data.

    @param x    Vector of signal model parameters: x[0] is the transmitter power,
                x[1] is the path loss exponent, x[2] is the x coordinate of the
                transmitter location in meters, x[3] is the y coordinate of the
                transmitter location in meters, x[4] is the system loss constant.
    @param data    Matrix of signal data.  This matrix must have shape (m, 3), 
                where m is the number of data samples.  data[:,0] is the vector
                of received signal power.  data[:,1] is the vector of x 
                coordinates of each measurement in meters.  data[:,2] is the
                vector of y coordinates of each measurement in meters.
    @returns    A vector of shape (m,) containing the difference between the 
                data and estimated data using the provided signal model 
                parameters.
    '''
    P = x[0]
    n = x[1]
    tx = x[2]
    ty = x[3]
    k = x[4]

    R = data[:,0]
    dx = data[:,1]
    dy = data[:,2]

    d = np.linalg.norm(np.array([dx - tx, dy - ty]).transpose())
    return P - 10 * n * np.log10(d) + k - R



def mse(R, x, P, n, t, k):
    '''
    Calculates the mean squared error for the signal propagation model 
    parameterized by P, n, t, and k and the data given by R and x.

    @param R    The received signal power.
    @param x    A vector of shape (2,) containing the measurement location
                for the received signal in meters.
    @param P    The transmitter power.
    @param n    The path loss exponent.
    @param t    A vector of shape (2,) containing the transmitter location in
                meters.
    @param k    The system loss constant
    @returns    The mean squared error of this measurement.
    '''
    d = np.linalg.norm(x - t)
    return (R - P + 10 * n * np.log10(d) + k) ** 2

class DataManager:
    def __init__(self):
        self.__estimators = {}
        self.zone = None
        self.let = None
        self.__vehiclePath = []

    def addPing(self, ping: rctPing):
        pingFreq = ping.freq
        if pingFreq not in self.__estimators:
            self.__estimators[pingFreq] = LocationEstimator()
        self.__estimators[pingFreq].addPing(ping)
        
        if self.zone == None:
            self.setZone(ping.lat, ping.lon)
        
        return self.__estimators[pingFreq].doEstimate()
    
    def addVehicleLocation(self, coord):
        self.__vehiclePath.append(coord)
    
    def setZone(self, lat, lon):
        _, _, zone, let = utm.from_latlon(lat, lon)
        self.zone = zone
        self.let = let

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
    
    def getVehiclePath(self):
        return self.__vehiclePath
    
    def getUTMZone(self):
        return self.zone, self.let
    
    def doPrecisions(self, frequency):
        estimator = self.__estimators[frequency]
        estimator.doPrecision()


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

    def resamplePings(self):
        pings = np.array(self.__pings)
        pingCopy = None
        currInd = 0
        indSkip = np.array([])
        for ping in pings:
            if (currInd in indSkip):
                currInd = currInd + 1
                continue
            rad = 5
            ind = np.where((pings[:,0] < ping[0] + rad) & (pings[:,0] > ping[0] - rad) & (pings[:,1] < ping[1] + rad) & (pings[:,1] > ping[1]-rad))
            indSkip = np.append(indSkip, ind[0])
            currInd = currInd + 1
            if len(ind[0]) > 1:
                newArr = None
                for i in ind[0]:
                    if newArr is None:  
                        newArr = np.array([pings[i]])
                    else:     
                        newArr = np.vstack((newArr, [pings[i]]))
                newArr = np.vstack((newArr, [ping]))
                x = np.mean(newArr[:, 0])
                y = np.mean(newArr[:, 1])
                alt = np.mean(newArr[:, 2])
                power = np.mean(newArr[:, 3])
                if pingCopy is None:
                    pingCopy = np.array([[x, y, alt, power]])
                else:
                    pingCopy = np.vstack((pingCopy, [[x, y, alt, power]]))
            else:
                if pingCopy is None:
                    pingCopy = np.array([ping])
                else:
                    pingCopy = np.vstack((pingCopy, [ping]))
        return pingCopy

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
        

            X_tx_0 = np.mean(pings[:, 0])#0
            Y_tx_0 = np.mean(pings[:, 1])#1
            P_tx_0 = np.max(pings[:, 3])#3
            n_0 = 2
            self.__params = np.array([X_tx_0, Y_tx_0, P_tx_0, n_0])
            res_x = least_squares(self.__residuals, self.__params, 
            bounds=([0, 167000, -np.inf, 2], [833000, 10000000, np.inf, 2.1]))
            #bounds=([0, 167000, -np.inf, 2], [833000, 10000000, np.inf, np.inf]))

        if res_x.success:
            self.__params = res_x.x
            self.__staleEstimate = False
        else:
            self.__staleEstimate = True

        self.result = res_x

        return self.__params, self.__staleEstimate

    def dToPrx(self, pingVector: np.ndarray, paramVector: np.ndarray):
        l_rx = np.array(pingVector[0:3])
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
    
    def p_d(self, tx, dx, n, P_rx, P_tx, D_std):
            modeledDistance = self.RSSItoDistance(P_rx, P_tx, n)
            return norm.pdf(np.linalg.norm(dx - tx), loc=modeledDistance, scale=D_std)
        
    def p_d_unpack(self, args):
        return self.p_d(*args)
    
    def RSSItoDistance(self, P_rx, P_tx, n, alt=0):
        dist = 10 ** ((P_tx - P_rx) / (10 * n))
        if alt != 0:
            dist = np.sqrt(dist ** 2 - alt ** 2)
        return dist

    def doPrecision(self):
        
        data_dir = 'holder'
        freq = 17350000

        f_pings = self.__pings

        print("%03.3f has %d pings" % (freq / 1e6, len(f_pings)))

        zonenum = 11
        
        zone = 'S'

        res_x = self.__params

        
        l_tx = res_x[0:2]
        P = res_x[2]
        n = res_x[3]
        
        
        pings = np.array(f_pings)
        
        distances = np.linalg.norm(pings[:,0:3] - np.array([l_tx[0], l_tx[1], 0]), axis=1)
        calculatedDistances = self.RSSItoDistance(pings[:,3], P, n)
        
        distanceErrors = calculatedDistances - distances
        stdDistances = np.std(distanceErrors)
        
        size = 50
        tiffXSize = size
        tiffYSize = size
        pixelSize = 1
        heatMapArea = np.ones((tiffYSize, tiffXSize)) / (tiffXSize * tiffYSize) # [y, x]
        '''
        minY = l_tx[1] - np.max(distances) - margin 
        refY = l_tx[1] + np.max(distances) + margin 
        refX = l_tx[0] - np.max(distances) - margin 
        maxX = l_tx[0] + np.max(distances) + margin 
        '''
        minY = l_tx[1] - (size / 2)
        refY = l_tx[1] + (size / 2)
        refX = l_tx[0] - (size / 2)
        maxX = l_tx[0] + (size / 2)

        
        
        #pool = multiprocessing.Pool(processes=3)
        P_rx = pings[:,3]
        for x in range(tiffXSize):
            for y in range(tiffYSize):
                '''
                arguments = [[np.array([x + refX, y + minY, 0]), pings[i,0:3], n, P_rx[i], P, stdDistances] for i in range(len(pings))]
                results = pool.map(p_d_unpack, arguments)
                for i in range(len(results)):
                    heatMapArea[x,y] += results[i]
                '''
                for i in range(len(pings)):
                    heatMapArea[y, x] *= self.p_d(np.array([x + refX, y + minY, 0]), pings[i,0:3], n, P_rx[i], P, stdDistances)



        outputFileName = '%s/PRECISION_%03.3f_heatmap.tiff' % (data_dir, freq / 1e6)
        driver = gdal.GetDriverByName('GTiff')
        dataset = driver.Create(
            outputFileName,
            tiffXSize,
            tiffYSize,
            1,
            gdal.GDT_Float32, ['COMPRESS=LZW'])
        spatialReference = osr.SpatialReference()
        
        spatialReference.SetUTM(zonenum, zone >= 'N')
        spatialReference.SetWellKnownGeogCS('WGS84')
        wkt = spatialReference.ExportToWkt()
        retval = dataset.SetProjection(wkt)
        dataset.SetGeoTransform((
            refX,    # 3
            1,                      # 4
            0,
            refY,    # 0
            0,  # 1
            -1))                     # 2
        band = dataset.GetRasterBand(1)

        band.WriteArray(heatMapArea)
        band.SetStatistics(np.amin(heatMapArea), np.amax(heatMapArea), np.mean(heatMapArea), np.std(heatMapArea))
        dataset.FlushCache()
        dataset = None
        print("done")
        


    def getEstimate(self):
        if self.__params is None:
            return None
        return self.__params, self.__staleEstimate, self.result

    def _getComparator(self):
        pass

    def getPings(self):
        return self.__pings
    
    def setPings(self, pings):
        self.__pings = pings
    

