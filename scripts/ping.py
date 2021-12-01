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
# 03/11/21  ML  Added normalization to heatMapArea in precision visualization 
#               function
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
from scipy.stats import norm, zscore
import utm
import rctComms
import time
from osgeo import gdal
from osgeo import osr
import csv
import math

class rctCone:
    def __init__(self, lat: float, lon: float, amplitude: float, freq: int, alt: float, heading:float, time: float):
        self.lat = lat
        self.lon = lon
        self.amplitude = amplitude
        self.heading
        self.freq = freq
        self.alt = alt
        self.time = dt.datetime.fromtimestamp(time)

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
    
    def getNumPings(self, frequency: int):
        estimator = self.__estimators[frequency]
        return estimator.getNumPings()
    
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
        
        self.last_l_tx0 = 0
        self.last_l_tx1 = 0
        self.index = 0
        
        self.lookup = {}
        
        self.lookup[4.0] = [    0.00003,    0.00003,    0.00003,    0.00003,    0.00003,    0.00003,    0.00002,    0.00002,    0.00002,    0.00002] 
        self.lookup[3.9] = [    0.00005,    0.00005,    0.00004,    0.00004,    0.00004,    0.00004,    0.00004,    0.00004,    0.00003,    0.00003] 
        self.lookup[3.8] = [    0.00007,    0.00007,    0.00007,    0.00006,    0.00006,    0.00006,    0.00006,    0.00005,    0.00005,    0.00005] 
        self.lookup[3.7] = [    0.00011,    0.00010,    0.00010,    0.00010,    0.00009,    0.00009,    0.00008,    0.00008,    0.00008,    0.00008]
        self.lookup[3.6] = [    0.00016,    0.00015,    0.00015,    0.00014,    0.00014,    0.00013,    0.00013,    0.00012,    0.00012,    0.00011]
        self.lookup[3.5] = [    0.00023,    0.00022,    0.00022,    0.00021,    0.00020,    0.00019,    0.00019,    0.00018,    0.00017,    0.00017]
        self.lookup[3.4] = [    0.00034,    0.00032,    0.00031,    0.00030,    0.00029,    0.00028,    0.00027,    0.00026,    0.00025,    0.00024]
        self.lookup[3.3] = [    0.00048,    0.00047,    0.00045,    0.00043,    0.00042,    0.00040,    0.00039,    0.00038,    0.00036,    0.00035]
        self.lookup[3.2] = [    0.00069,    0.00066,    0.00064,    0.00062,    0.00060,    0.00058,    0.00056,    0.00054,    0.00052,    0.00050]
        self.lookup[3.1] = [    0.00097,    0.00094,    0.00090,    0.00087,    0.00084,    0.00082,    0.00079,    0.00076,    0.00074,    0.00071]
        self.lookup[3.0] = [    0.00135,    0.00131,    0.00126,    0.00122,    0.00118,    0.00114,    0.00111,    0.00107,    0.00104,    0.00100]
        self.lookup[2.9] = [    0.00187,    0.00181,    0.00175,    0.00169,    0.00164,    0.00159,    0.00154,    0.00149,    0.00144,    0.00139]
        self.lookup[2.8] = [    0.00256,    0.00248,    0.00240,    0.00233,    0.00226,    0.00219,    0.00212,    0.00205,    0.00199,    0.00193]
        self.lookup[2.7] = [    0.00347,    0.00336,    0.00326,    0.00317,    0.00307,    0.00298,    0.00289,    0.00280,    0.00272,    0.00264]
        self.lookup[2.6] = [    0.00466,    0.00453,    0.00440,    0.00427,    0.00415,    0.00402,    0.00391,    0.00379,    0.00368,    0.00357]
        self.lookup[2.5] = [    0.00621,    0.00604,    0.00587,    0.00570,    0.00554,    0.00539,    0.00523,    0.00508,    0.00494,    0.00480]
        self.lookup[2.4] = [    0.00820,    0.00798,    0.00776,    0.00755,    0.00734,    0.00714,    0.00695,    0.00676,    0.00657,    0.00639]
        self.lookup[2.3] = [    0.01072,    0.01044,    0.01017,    0.00990,    0.00964,    0.00939,    0.00914,    0.00889,    0.00866,    0.00842]
        self.lookup[2.2] = [    0.01390,    0.01355,    0.01321,    0.01287,    0.01255,    0.01222,    0.01191,    0.01160,    0.01130,    0.01101]
        self.lookup[2.1] = [    0.01786,    0.01743,    0.01700,    0.01659,    0.01618,    0.01578,    0.01539,    0.01500,    0.01463,    0.01426]
        self.lookup[2.0] = [    0.02275,    0.02222,    0.02169,    0.02118,    0.02068,    0.02018,    0.01970,    0.01923,    0.01876,    0.01831]
        self.lookup[1.9] = [    0.02872,    0.02807,    0.02743,    0.02680,    0.02619,    0.02559,    0.02500,    0.02442,    0.02385,    0.02330]
        self.lookup[1.8] = [    0.03593,    0.03515,    0.03438,    0.03362,    0.03288,    0.03216,    0.03144,    0.03074,    0.03005,    0.02938]
        self.lookup[1.7] = [    0.04457,    0.04363,    0.04272,    0.04182,    0.04093,    0.04006,    0.03920,    0.03836,    0.03754,    0.03673]
        self.lookup[1.6] = [    0.05480,    0.05370,    0.05262,    0.05155,    0.05050,    0.04947,    0.04846,    0.04746,    0.04648,    0.04551]
        self.lookup[1.5] = [    0.06681,    0.06552,    0.06426,    0.06301,    0.06178,    0.06057,    0.05938,    0.05821,    0.05705,    0.05592]
        self.lookup[1.4] = [    0.08076,    0.07927,    0.07780,    0.07636,    0.07493,    0.07353,    0.07215,    0.07078,    0.06944,    0.06811]
        self.lookup[1.3] = [    0.09680,    0.09510,    0.09342,    0.09176,    0.09012,    0.08851,    0.08692,    0.08534,    0.08379,    0.08226]
        self.lookup[1.2] = [    0.11507,    0.11314,    0.11123,    0.10935,    0.10749,    0.10565,    0.10383,    0.10204,    0.10027,    0.09853]
        self.lookup[1.1] = [    0.13567,    0.13350,    0.13136,    0.12924,    0.12714,    0.12507,    0.12302,    0.12100,    0.11900,    0.11702]
        self.lookup[1.0] = [    0.15866,    0.15625,    0.15386,    0.15151,    0.14917,    0.14686,    0.14457,    0.14231,    0.14007,    0.13786]
        self.lookup[0.9] = [    0.18406,    0.18141,    0.17879,    0.17619,    0.17361,    0.17106,    0.16853,    0.16602,    0.16354,    0.16109]
        self.lookup[0.8] = [    0.21186,    0.20897,    0.20611,    0.20327,    0.20045,    0.19766,    0.19489,    0.19215,    0.18943,    0.18673]
        self.lookup[0.7] = [    0.24196,    0.23885,    0.23576,    0.23270,    0.22965,    0.22663,    0.22363,    0.22065,    0.21770,    0.21476]
        self.lookup[0.6] = [    0.27425,    0.27093,    0.26763,    0.26435,    0.26109,    0.25785,    0.25463,    0.25143,    0.24825,    0.24510]
        self.lookup[0.5] = [    0.30854,    0.30503,    0.30153,    0.29806,    0.29460,    0.29116,    0.28774,    0.28434,    0.28096,    0.27760]
        self.lookup[0.4] = [    0.34458,    0.34090,    0.33724,    0.33360,    0.32997,    0.32636,    0.32276,    0.31918,    0.31561,    0.31207]
        self.lookup[0.3] = [    0.38209,    0.37828,    0.37448,    0.37070,    0.36693,    0.36317,    0.35942,    0.35569,    0.35197,    0.34827]
        self.lookup[0.2] = [    0.42074,    0.41683,    0.41294,    0.40905,    0.40517,    0.40129,    0.39743,    0.39358,    0.38974,    0.38591]
        self.lookup[0.1] = [    0.46017,    0.45620,    0.45224,    0.44828,    0.44433,    0.44038,    0.43644,    0.43251,    0.42858,    0.42465]
        self.lookup[0.0] = [    0.50000,    0.49601,    0.49202,    0.48803,    0.48405,    0.48006,    0.47608,    0.47210,    0.46812,    0.46414]


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
        
        #self.doPrecision()

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
            adjustedDistance = (np.linalg.norm(dx-tx)-modeledDistance)/D_std
            return math.exp((-(adjustedDistance**2)/2)) / (math.sqrt(2*math.pi) * D_std)
            
    def RSSItoDistance(self, P_rx, P_tx, n, alt=0):
        dist = 10 ** ((P_tx - P_rx) / (10 * n))
        if alt != 0:
            dist = np.sqrt(dist ** 2 - alt ** 2)
        return dist

    def doPrecision(self):
        ts = time.time()
        
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
        P_rx = pings[:,3]
        
        size = 25
        tiffXSize = size
        tiffYSize = size
        pixelSize = 1
        heatMapArea = np.ones((tiffYSize, tiffXSize)) / (tiffXSize * tiffYSize) # [y, x]
            
        self.last_l_tx0 = l_tx[0]
        self.last_l_tx1 = l_tx[1]
        self.index = len(pings) - 1

        self.minY = l_tx[1] - (size / 2)
        self.refY = l_tx[1] + (size / 2)
        self.refX = l_tx[0] - (size / 2)
        self.maxX = l_tx[0] + (size / 2)
    
        csv_dict = []
            
        for y in range(tiffYSize):
            for x in range(tiffXSize):             
                for i in range(len(pings)):
                    heatMapArea[y, x] *= self.p_d(np.array([x + self.refX, y + self.minY, 0]), pings[i,0:3], n, P_rx[i], P, stdDistances)
  
                #csv_dict.append({"easting": self.refX+x, "northing": self.minY+y, "value": (heatMapArea[y, x]), "new": (heatMapArea2[y,x])})
                csv_dict.append({"easting": self.refX+x, "northing": self.minY+y, "value": (heatMapArea[y, x])})

        sumH = heatMapArea.sum()
        heatMapArea = heatMapArea / sumH
        with open('./holder/query.csv', 'w', newline='') as csvfile:
            fieldnames = ['easting', 'northing', 'value', 'new']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_dict)
        

        outputFileName = '%s/PRECISION_%03.3f_%d_heatmap.tiff' % (data_dir, freq / 1e6, len(pings))
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
            self.refX,    # 3
            1,                      # 4
            0,
            self.refY,    # 0
            0,  # 1
            -1))                     # 2
        band = dataset.GetRasterBand(1)

        band.WriteArray(heatMapArea)
        band.SetStatistics(np.amin(heatMapArea), np.amax(heatMapArea), np.mean(heatMapArea), np.std(heatMapArea))
        dataset.FlushCache()
        dataset = None
        


    def getEstimate(self):
        if self.__params is None:
            return None
        return self.__params, self.__staleEstimate, self.result

    def _getComparator(self):
        pass

    def getPings(self):
        return self.__pings
    
    def getNumPings(self):
        return len(self.__pings)
    
    def setPings(self, pings):
        self.__pings = pings
    

