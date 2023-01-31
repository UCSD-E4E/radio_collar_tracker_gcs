import math
import sys
import os
import os.path
import requests
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from pathlib import Path
if 'CONDA_PREFIX' in os.environ:
    sys.path.insert(0, Path(sys.executable).parent.joinpath("Library", "python", "plugins").as_posix())
    sys.path.insert(0, Path(sys.executable).parent.joinpath("Library", "python").as_posix())
from qgis.core import *    
import qgis.gui
from qgis.utils import *
from qgis.core import QgsProject
from threading import Thread
import csv
from ui.popups import *
from ui.controls import *

class RectangleMapTool(qgis.gui.QgsMapToolEmitPoint):
    '''
    Custom QgsMapTool to select a rectangular area of a QgsMapCanvas
    '''
    def __init__(self, canvas):
        '''
        Creates a RectangleMapTool object
        Args:
            canvas: the QgsMapCanvas that the RectangleMapTool will be 
                    attached to
        '''
        self.canvas = canvas
        qgis.gui.QgsMapToolEmitPoint.__init__(self, self.canvas)
        self.rubberBand = qgis.gui.QgsRubberBand(self.canvas, True)
        self.rubberBand.setColor(QColor(0,255,255,125))
        self.rubberBand.setWidth(1)
        self.reset()

    def reset(self):
        '''
        '''
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(True)

    def canvasPressEvent(self, e):
        '''
        Internal callback to be called when the user's mouse 
        presses the canvas
        Args:
            e: The press event
        '''
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint
        self.isEmittingPoint = True
        self.showRect(self.startPoint, self.endPoint)

    def canvasReleaseEvent(self, e):
        '''
        Internal callback called when the user's mouse releases 
        over the canvas
        Args:
            e: The release event
        '''
        self.isEmittingPoint = False

    def canvasMoveEvent(self, e):
        '''
        Internal callback called when the user's mouse moves 
        over the canvas
        Args:
            e: The move event
        '''
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())
        self.showRect(self.startPoint, self.endPoint)

    def showRect(self, startPoint, endPoint):
        '''
        Internal function to display the rectangle being 
        specified by the user
        '''
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return
    
        point1 = QgsPointXY(startPoint.x(), startPoint.y())
        point2 = QgsPointXY(startPoint.x(), endPoint.y())
        point3 = QgsPointXY(endPoint.x(), endPoint.y())
        point4 = QgsPointXY(endPoint.x(), startPoint.y())
    
        self.rubberBand.addPoint(point1, False)
        self.rubberBand.addPoint(point2, False)
        self.rubberBand.addPoint(point3, False)
        self.rubberBand.addPoint(point4, True)    # true to update canvas
        self.rubberBand.show()

    def rectangle(self):
        '''
        function to return the rectangle that has been selected
        '''
        if self.startPoint is None or self.endPoint is None:
            return None
        elif (self.startPoint.x() == self.endPoint.x() or \
              self.startPoint.y() == self.endPoint.y()):
            return None
    
        return QgsRectangle(self.startPoint, self.endPoint)

    def deactivate(self):
        '''
        Function to deactivate the map tool
        '''
        qgis.gui.QgsMapTool.deactivate(self)
        self.deactivated.emit()

class PolygonMapTool(qgis.gui.QgsMapToolEmitPoint):
    def __init__(self, canvas):
        self.canvas = canvas
        qgis.gui.QgsMapToolEmitPoint.__init__(self, self.canvas)
        #Creating a list for all vertex coordinates
        self.vertices = []
        self.rubberBand = qgis.gui.QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setColor(Qt.red)
        self.rubberBand.setWidth(1)
        self.reset()

    def reset(self):
        self.startPoint = self.endPoint = None
        self.isEmittingPoint = False
        self.rubberBand.reset(True)

    def canvasPressEvent(self, e):
        self.startPoint = self.toMapCoordinates(e.pos())
        self.endPoint = self.startPoint
        self.isEmittingPoint = True
        self.addVertex(self.startPoint, self.canvas)
        self.showLine(self.startPoint, self.endPoint)
        self.showPolygon()

    def canvasReleaseEvent(self, e):
        self.isEmittingPoint = False

    def canvasMoveEvent(self, e):
        if not self.isEmittingPoint:
            return

        self.endPoint = self.toMapCoordinates(e.pos())
        self.showLine(self.startPoint, self.endPoint)

    def addVertex(self, selectPoint, canvas):
        vertex = QgsPointXY(selectPoint)
        self.vertices.append(vertex)

    def showPolygon(self):
        if (len(self.vertices) > 1):
            self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
            r = len(self.vertices) - 1
            for i in range(r):
                self.rubberBand.addPoint(self.vertices[i], False)
            self.rubberBand.addPoint(self.vertices[r], True)
            self.rubberBand.show()

    def showLine(self, startPoint, endPoint):
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        if startPoint.x() == endPoint.x() or startPoint.y() == endPoint.y():
            return
        
        point1 = QgsPointXY(startPoint.x(), startPoint.y())

        self.rubberBand.addPoint(point1, True)

        self.rubberBand.show()

    def deactivate(self):
        qgis.gui.QgsMapTool.deactivate(self)
        self.deactivated.emit()

class VehicleData:
    '''
    Information about displaying a vehicle on the map
    '''
    def __init__(self):
        self.ind = 0
        self.lastLoc = None

class MapWidget(QWidget):
    '''
    Custom Widget that is used to display a map
    '''
    def __init__(self, root):
        '''
        Creates a MapWidget
        Args:
            root: The root widget of the application
        '''
        QWidget.__init__(self)
        self.holder = QVBoxLayout()
        self.groundTruth = None
        self.mapLayer = None
        self.vehicle = None
        self.vehiclePath = None
        self.precision = None
        self.cones = None
        self.vehicleData = {}
        self.pingLayer = None
        self.pingRenderer = None
        self.estimate = None
        self.toolPolygon = None
        self.polygonLayer = None
        self.polygonAction = None
        self.heatMap = None
        self.pingMin = 800
        self.pingMax = 0
        self.coneMin = sys.float_info.max
        self.coneMax = sys.float_info.min
        self.ind = 0
        self.indPing = 0
        self.indPing = 0
        self.indEst = 0
        self.indCone = 0
        self.toolbar = QToolBar()
        self.canvas = qgis.gui.QgsMapCanvas()
        self.canvas.setCanvasColor(Qt.white)

        self.transformToWeb = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsCoordinateReferenceSystem("EPSG:3857"), 
                QgsProject.instance())
        self.transform = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:3857"), 
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance())
        
    
    def setupHeatMap(self):
        '''
        Sets up the heatMap maplayer
        Args:
        '''
        fileName = QFileDialog.getOpenFileName()
        print(fileName[0])
        if self.heatMap is not None:
            QgsProject.instance().removeMapLayer(self.heatMap)
        if fileName is not None:
            self.heatMap = QgsRasterLayer(fileName[0], "heatMap")   
            
            stats = self.heatMap.dataProvider().bandStatistics(1)
            maxVal = stats.maximumValue
            print(maxVal)
            fcn = QgsColorRampShader()
            fcn.setColorRampType(QgsColorRampShader.Interpolated)
            lst = [ QgsColorRampShader.ColorRampItem(0, QColor(0,0,0)), QgsColorRampShader.ColorRampItem(maxVal, QColor(255,255,255)) ]
            fcn.setColorRampItemList(lst)
            shader = QgsRasterShader()
            shader.setRasterShaderFunction(fcn)
            
            renderer = QgsSingleBandPseudoColorRenderer(self.heatMap.dataProvider(), 1, shader)
            self.heatMap.setRenderer(renderer)
            
            QgsProject.instance().addMapLayer(self.heatMap)
            destCrs = self.mapLayer.crs()
            rasterCrs = self.heatMap.crs()
            
            self.heatMap.setCrs(rasterCrs)
            self.canvas.setDestinationCrs(destCrs)
            

            self.canvas.setLayers([self.heatMap, self.estimate, self.groundTruth,
                               self.vehicle, self.pingLayer, 
                               self.vehiclePath, self.mapLayer]) 
            
            
    def plotPrecision(self, coord, freq, numPings):
        data_dir = 'holder'
        outputFileName = '/%s/PRECISION_%03.3f_%d_heatmap.tiff' % (data_dir, freq / 1e7, numPings)
        fileName = QDir().currentPath() + outputFileName
        print(fileName)
        print(outputFileName)

        
        if self.heatMap is not None:
            QgsProject.instance().removeMapLayer(self.heatMap)
        if fileName is not None:
            self.heatMap = QgsRasterLayer(fileName, "heatMap")   
            
            
            stats = self.heatMap.dataProvider().bandStatistics(1)
            maxVal = stats.maximumValue
            print(maxVal)
            fcn = QgsColorRampShader()
            fcn.setColorRampType(QgsColorRampShader.Interpolated)
            lst = [ QgsColorRampShader.ColorRampItem(0, QColor(0,0,0)), QgsColorRampShader.ColorRampItem(maxVal, QColor(255,255,255)) ]
            fcn.setColorRampItemList(lst)
            shader = QgsRasterShader()
            shader.setRasterShaderFunction(fcn)
            
            renderer = QgsSingleBandPseudoColorRenderer(self.heatMap.dataProvider(), 1, shader)
            self.heatMap.setRenderer(renderer)
            
            
            QgsProject.instance().addMapLayer(self.heatMap)
            destCrs = self.mapLayer.crs()
            rasterCrs = self.heatMap.crs()
            
            self.heatMap.setCrs(rasterCrs)
            self.canvas.setDestinationCrs(destCrs)
            self.heatMap.renderer().setOpacity(0.7)
            

            self.canvas.setLayers([self.heatMap, self.estimate, self.groundTruth,
                               self.vehicle, self.pingLayer, 
                               self.vehiclePath, self.mapLayer]) 

        
    def adjustCanvas(self):
        '''
        Helper function to set and adjust the camvas' layers
        '''
        self.canvas.setExtent(self.mapLayer.extent())  
        self.canvas.setLayers([self.precision, self.estimate, self.groundTruth, 
                               self.vehicle, self.pingLayer, self.cones,
                               self.vehiclePath, self.polygonLayer, self.mapLayer]) 
        #self.canvas.setLayers([self.mapLayer])
        self.canvas.zoomToFullExtent()   
        self.canvas.freeze(True)  
        self.canvas.show()     
        self.canvas.refresh()       
        self.canvas.freeze(False)    
        self.canvas.repaint()

    def addToolBar(self):
        '''
        Internal function to add tools to the map toolbar
        '''
        self.actionZoomIn = QAction("Zoom in", self)
        self.actionZoomOut = QAction("Zoom out", self)
        self.actionPan = QAction("Pan", self)

        self.actionZoomIn.setCheckable(True)
        self.actionZoomOut.setCheckable(True)
        self.actionPan.setCheckable(True)

        self.actionZoomIn.triggered.connect(self.zoomIn)
        self.actionZoomOut.triggered.connect(self.zoomOut)
        self.actionPan.triggered.connect(self.pan)

        self.toolbar.addAction(self.actionZoomIn)
        self.toolbar.addAction(self.actionZoomOut)
        self.toolbar.addAction(self.actionPan)

        # create the map tools
        self.toolPan = qgis.gui.QgsMapToolPan(self.canvas)
        self.toolPan.setAction(self.actionPan)
        self.toolZoomIn =qgis.gui. QgsMapToolZoom(self.canvas, False) # false = in
        self.toolZoomIn.setAction(self.actionZoomIn)
        self.toolZoomOut = qgis.gui.QgsMapToolZoom(self.canvas, True) # true = out
        self.toolZoomOut.setAction(self.actionZoomOut)

        self.polygonAction = QAction("Polygon", self)
        self.polygonAction.setCheckable(True)
        self.polygonAction.triggered.connect(self.polygon)
        self.toolbar.addAction(self.polygonAction)
        self.toolPolygon = PolygonMapTool(self.canvas)
        self.toolPolygon.setAction(self.polygonAction)

    def polygon(self):
        '''
        Helper function to set polygon tool when it is selected from 
        the toolbar
        '''
        self.canvas.setMapTool(self.toolPolygon)



    def zoomIn(self):
        '''
        Helper function to set the zoomIn map tool when it is selected
        '''
        self.canvas.setMapTool(self.toolZoomIn)

    def zoomOut(self):
        '''
        Helper function to set the zoomOut map tool when it is selected
        '''
        self.canvas.setMapTool(self.toolZoomOut)

    def pan(self):
        '''
        Helper function to set the pan map tool when it is selected
        '''
        self.canvas.setMapTool(self.toolPan)

    def plotVehicle(self, id, coord):
        '''
        Function to plot the vehicle's current location on the vehicle 
        map layer
        Args:
            coord: A tuple of float values indicating an EPSG:4326 lat/Long 
                   coordinate pair
        '''
        lat = coord[0]
        lon = coord[1]
        point = self.transformToWeb.transform(QgsPointXY(lon, lat))
        if self.vehicle is None:
            return
        else:
            vData = VehicleData()
            if id not in self.vehicleData:
                self.vehicleData[id] = vData
            else:
                vData = self.vehicleData[id]
            if vData.ind > 0:
                lpr = self.vehiclePath.dataProvider()
                lin = QgsGeometry.fromPolylineXY([vData.lastLoc, point])
                lineFeat = QgsFeature()
                lineFeat.setGeometry(lin)
                lpr.addFeatures([lineFeat])
                vpr = self.vehicle.dataProvider()
                self.vehicle.startEditing()
                self.vehicle.deleteFeature(vData.ind)
                self.vehicle.commitChanges()
            
            vData.lastLoc = point
            vpr = self.vehicle.dataProvider()
            pnt = QgsGeometry.fromPointXY(point)
            f = QgsFeature()
            f.setGeometry(pnt)
            vpr.addFeatures([f])
            self.vehicle.updateExtents()
            self.ind = self.ind + 1
            vData.ind = self.ind
    
    def plotCone(self, coord):
        lat = coord[0]
        lon = coord[1]
        heading = coord[4]
        #power = coord[3]
        #dummy power values to test calcColor
        pArr =  [2.4, 4, 5, 2.1, 3, 8, 5.9, 2, 1, 3, 5, 4]        
        aind = self.indCone % 12
        power = pArr[aind]

        point = self.transformToWeb.transform(QgsPointXY(lon, lat))
        if self.coneMin > power:
            self.coneMin = power
        if self.coneMax < power:
            self.coneMax = power

        if self.cones is None:
            return
        else:
            if self.indCone > 4:
                self.cones.startEditing()
                self.cones.deleteFeature(self.indCone-5)
                self.cones.commitChanges()
            
            
            # update cone color/length based on coneMin-coneMax range
            updateInd = self.indCone
            opacity = 1
            updates = {}
            while updateInd >= self.indCone-4 and updateInd > 0:
                feature = self.cones.getFeature(updateInd)
                amp = feature.attributes()[1]
                color = self.calcColor(amp, self.coneMin, self.coneMax, opacity)
                height = self.calcHeight(amp, self.coneMin, self.coneMax)
                updates[updateInd] = {2: color, 3: height}
                updateInd -= 1
                opacity -= 0.2

            #Add new cone
            cpr = self.cones.dataProvider()
            cpr.changeAttributeValues(updates)
            pnt = QgsGeometry.fromPointXY(point)
            f = QgsFeature()
            f.setFields(self.cones.fields())
            f.setGeometry(pnt)
            f.setAttribute(0, heading)
            f.setAttribute(1, power)
            f.setAttribute(2, self.calcColor(power, self.coneMin, self.coneMax, 1))
            f.setAttribute(3, self.calcHeight(power, self.coneMin, self.coneMax))
            f.setAttribute(4, "bottom")
            cpr.addFeatures([f])
            self.cones.updateExtents()
            self.indCone = self.indCone + 1
            
    def calcColor(self, amp, minAmp, maxAmp, opac):
        '''
        Calculates hex color value for a cone based on variable range
        Colors range between red (strongest) and blue (weakest)
        Args:
            amp: Float containing cone signal amplitude
            minAmp: Flaot representing minimum amplitude in range
            maxAmp: Float representing maximum amplitude in range
            opac: Float representing percent opacity
        '''
        if (minAmp == maxAmp):
            colorRatio = 0.5
        else:
            colorRatio = (amp - minAmp)/(maxAmp - minAmp)
        red = int(255 * colorRatio)
        blue = int(255 * (1-colorRatio))
        opacity = int(255 * opac)
        color = "#%02x%02x%02x%02x" % (opacity, red, 0, blue)
        return color

    def calcHeight(self, amp, minAmp, maxAmp):
        '''
        Calculates double value for a cone's length based on variable minAmp-maxAmp range
        Args:
            amp: Float containing cone signal amplitude
            minAmp: Flaot representing minimum amplitude in range
            maxAmp: Float representing maximum amplitude in range
        '''
        height = 4.0
        if (minAmp != maxAmp):
            height = 3.0 * (amp - minAmp)/(maxAmp - minAmp) + 1
        return height

    def plotPing(self, coord, power):
        '''
        Function to plot a new ping on the ping map layer
        Args:
            coord: A tuple of float values indicating an EPSG:4326 lat/Long 
                   coordinate pair
            amp: The amplitude of the ping
        '''
        lat = coord[0]
        lon = coord[1]
        
        
        change = False
        point = self.transformToWeb.transform(QgsPointXY(lon, lat))
        if self.pingLayer is None:
            return

        else:
            if power < self.pingMin:
                change = True
                self.pingMin = power
            if power > self.pingMax:
                change = True
                self.pingMax = power
            if (self.pingMax == self.pingMin):
                self.pingMax = self.pingMax + 1
            if change:
                r = self.pingMax - self.pingMin
                first = r * 0.14
                second = r * 0.28
                third = r * 0.42
                fourth = r * 0.56
                fifth = r * 0.7
                sixth = r * 0.84
                
                for i, rangeObj in enumerate(self.pingRenderer.ranges()):
                    if rangeObj.label() == 'Blue':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + first)
                    if rangeObj.label() == 'Cyan':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin + first)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + second)
                    if rangeObj.label() == 'Green':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin + second)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + third)
                    if rangeObj.label() == 'Yellow':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin + third)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + fourth)
                    if rangeObj.label() == 'Orange':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin +fourth)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + fifth)
                    if rangeObj.label() == 'ORed':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin +fifth)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMin + sixth)
                    if rangeObj.label() == 'Red':
                        self.pingRenderer.updateRangeLowerValue(i, self.pingMin + sixth)
                        self.pingRenderer.updateRangeUpperValue(i, self.pingMax)

            vpr = self.pingLayer.dataProvider()
            
            #Create new ping point
            pnt = QgsGeometry.fromPointXY(point)
            f = QgsFeature()
            f.setFields(self.pingLayer.fields())
            f.setGeometry(pnt)
            f.setAttribute(0, power)
            vpr.addFeatures([f])
            self.pingLayer.updateExtents()
            
    def plotEstimate(self, coord, frequency):
        '''
        Function to plot the current estimate point on the estimate map layer
        Args:
            coord: A tuple of float values indicating an EPSG:4326 lat/Long 
                   coordinate pair
            frequency: the frequency that this estimate corresponds to
        '''
        lat = coord[0]
        lon = coord[1]
        
        
        point = self.transformToWeb.transform(QgsPointXY(lon, lat))
        if self.estimate is None:
            return
        else:
            if self.indEst > 0:
                self.estimate.startEditing()
                self.estimate.deleteFeature(self.indEst)
                self.estimate.commitChanges()
            
            vpr = self.estimate.dataProvider()
            pnt = QgsGeometry.fromPointXY(point)
            f = QgsFeature()
            f.setGeometry(pnt)
            vpr.addFeatures([f])
            self.estimate.updateExtents()
            self.indEst = self.indEst + 1
       
class MapOptions(QWidget):
    '''
    Custom Widget facilitate map caching and exporting map layers
    '''
    def __init__(self):
        '''
        Creates a MapOptions widget
        '''
        QWidget.__init__(self)

        self.mapWidget = None
        self.btn_cacheMap = None
        self.isWebMap = False
        self.lbl_dist = None
        self.__createWidgets()
        self.created = False
        self.writer = None
        self.hasPoint = False
        


    def __createWidgets(self):
        '''
        Inner function to create internal widgets
        '''
        # MAP OPTIONS
        lay_mapOptions = QVBoxLayout()

        lbl_mapOptions = QLabel('Map Options')
        lay_mapOptions.addWidget(lbl_mapOptions)

        self.btn_setSearchArea = QPushButton('Set Search Area')
        self.btn_setSearchArea.setEnabled(False)
        lay_mapOptions.addWidget(self.btn_setSearchArea)

        self.btn_cacheMap = QPushButton('Cache Map')
        self.btn_cacheMap.clicked.connect(self.__cacheMap)
        self.btn_cacheMap.setEnabled(False)
        lay_mapOptions.addWidget(self.btn_cacheMap)

        self.btn_clearMap = QPushButton('Clear Map')
        self.btn_clearMap.clicked.connect(self.clear)
        self.btn_clearMap.setEnabled(True)
        lay_mapOptions.addWidget(self.btn_clearMap)

        exportTab = CollapseFrame('Export')
        btn_pingExport = QPushButton('Pings')
        btn_pingExport.clicked.connect(self.exportPing)

        btn_vehiclePathExport = QPushButton('Vehicle Path')
        btn_vehiclePathExport.clicked.connect(self.exportVehiclePath)

        btn_polygonExport = QPushButton('Polygon')
        btn_polygonExport.clicked.connect(self.exportPolygon)

        btn_coneExport = QPushButton('Cones')
        btn_coneExport.clicked.connect(self.exportCone)
        
        lay_export = QVBoxLayout()
        lay_export.addWidget(btn_pingExport)
        lay_export.addWidget(btn_vehiclePathExport)
        lay_export.addWidget(btn_polygonExport)
        lay_export.addWidget(btn_coneExport)
        exportTab.setContentLayout(lay_export)
        
        lay_mapOptions.addWidget(exportTab)        
        
        distWidg = QWidget()
        distLay = QHBoxLayout()
        lbl_dist = QLabel('Distance from Actual')
        self.lbl_dist = QLabel('')
        distLay.addWidget(lbl_dist)
        distLay.addWidget(self.lbl_dist)
        distWidg.setLayout(distLay)

        lay_mapOptions.addWidget(distWidg)

        self.setLayout(lay_mapOptions)

    def clear(self):
        '''
        Helper function to clear selected map areas
        '''
        if self.mapWidget is None:
            return
        self.mapWidget.toolPolygon.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        self.mapWidget.toolRect.rubberBand.reset(QgsWkbTypes.PolygonGeometry)
        self.mapWidget.toolPolygon.vertices.clear()


    def __cacheMap(self):
        '''
        Inner function to facilitate map caching
        '''
        if self.isWebMap:
            if (self.mapWidget.toolRect.rectangle() == None):
                WarningMessager.showWarning("Use the rect tool to choose an area on the map to cache", "No specified area to cache!")
                self.mapWidget.rect()
            else:
                cacheThread = Thread(target=self.mapWidget.cacheMap)
                cacheThread.start()
                self.mapWidget.canvas.refresh()
        else:
            print("alert")

    def setMap(self, mapWidg: MapWidget, isWebMap):
        '''
        Function to set the MapWidget that this object will use
        Args:
            mapWidg: A MapWidget object
            isWebMap: A boolean indicating whether or not the mapWidget 
                      is a WebMap
        '''
        self.isWebMap = isWebMap
        self.mapWidget = mapWidg
        
        self.btn_cacheMap.setEnabled(isWebMap)
        
    def estDistance(self, coord, stale, res):
        '''
        An inner function to display the distance from the 
        current estimate point to the ground truth
        Args:
            coord: A tuple of float values indicating an EPSG:4326 lat/Long 
                   coordinate pair
            stale: A boolean
            res: The residuals vector
        '''
        lat1 = coord[0]
        lon1 = coord[1]
        lat2 = 32.885889
        lon2 = -117.234028
        
        # Center
        #lat2 = 32.88736856384841
        #lon2 = -117.23403141301122
        
        #20m beyond
        #lat2 = 32.886060596190255
        #lon2 = -117.23402797486396
        
        #20m right
        #lat2 = 32.88736896379847
        #lon2 = -117.23381758959809
        
        #50m right
        #lat2 = 32.88736956303811
        #lon2 = -117.23349685447043
        
        #diagonal
        #lat2 = 32.88606139568502
        #lon2 = -117.23360033431585
        
        if not self.hasPoint:
            point = self.mapWidget.transformToWeb.transform(QgsPointXY(lon2, lat2))
            vpr = self.mapWidget.groundTruth.dataProvider()
            pnt = QgsGeometry.fromPointXY(point)
            f = QgsFeature()
            f.setGeometry(pnt)
            vpr.addFeatures([f])
            self.mapWidget.groundTruth.updateExtents()
            self.hasPoint = True

        
        dist = self.distance(lat1, lat2, lon1, lon2)
        
        if not self.created:
            with open('results.csv', 'w', newline='') as csvfile:
                fieldnames = ['Distance', 'res.x', 'residuals']
                self.writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                self.writer.writeheader()
                self.created = True
                self.writer.writerow({'Distance': str(dist), 'res.x': str(res.x), 'residuals': str(res.fun)})
        else:
            with open('results.csv', 'a+', newline='') as csvfile:
                fieldnames = ['Distance', 'res.x', 'residuals']
                self.writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                self.writer.writerow({'Distance': str(dist), 'res.x': str(res.x), 'residuals': str(res.fun)})
                
       
        
        d = '%.3f'%(dist)

        self.lbl_dist.setText(d + '(m.)')
        
    def distance(self, lat1, lat2, lon1, lon2): 
        '''
        Helper function to calculate distance
        Args:
            lat1: float value indicating the lat value of a point
            lat2: float value indicating the lat value of a second point
            lon1: float value indicating the long value of a point
            lon2: float value indicating the long value of a second point
        '''
        lon1 = math.radians(lon1)
        lon2 = math.radians(lon2)
        lat1 = math.radians(lat1)
        lat2 = math.radians(lat2)

        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2

        c = 2 * math.asin(math.sqrt(a))

        # Radius of earth in kilometers. Use 3956 for miles
        r = 6371

        return(c * r * 1000)

    def exportPing(self):
        '''
        Method to export a MapWidget's pingLayer to a shapefile
        '''
        if self.mapWidget is None:
            WarningMessager.showWarning("Load a map before exporting.")
            return

        folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        file = folder + '/pings.shp'
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"

        QgsVectorFileWriter.writeAsVectorFormatV2(self.mapWidget.pingLayer,
                                        file,
                                        QgsCoordinateTransformContext(), options)

    def exportVehiclePath(self):
        '''
        Method to export a MapWidget's vehiclePath to a shapefile
        '''
        if self.mapWidget is None:
            WarningMessager.showWarning("Load a map before exporting.")
            return

        folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        file = folder + '/vehiclePath.shp'
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"

        QgsVectorFileWriter.writeAsVectorFormatV2(self.mapWidget.vehiclePath,
                                        file,
                                        QgsCoordinateTransformContext(), options)


    def exportPolygon(self):
        '''
        Method to export MapWidget's Polygon shape to a shapefile
        '''
        if self.mapWidget is None:
            WarningMessager.showWarning("Load a map before exporting.")
            return

        if self.mapWidget.toolPolygon is None:
            return
        elif len(self.mapWidget.toolPolygon.vertices) == 0:
            WarningMessager.showWarning("Use the polygon tool to choose an area on the map to export", "No specified area to export!")
            self.mapWidget.polygon()
        else:

            vpr = self.mapWidget.polygonLayer.dataProvider()
            pts = self.mapWidget.toolPolygon.vertices
            print(type(pts[0]))
            polyGeom = QgsGeometry.fromPolygonXY([pts])

            feature = QgsFeature()
            feature.setGeometry(polyGeom)
            vpr.addFeatures([feature])
            self.mapWidget.polygonLayer.updateExtents()

            folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
            file = folder + '/polygon.shp'
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "ESRI Shapefile"

            QgsVectorFileWriter.writeAsVectorFormatV2(self.mapWidget.polygonLayer, file,
                                                    QgsCoordinateTransformContext(), options)

            vpr.truncate()

    def exportCone(self):
        '''
        Method to export a MapWidget's cones to a shapefile
        '''
        if self.mapWidget is None:
            WarningMessager.showWarning("Load a map before exporting.")
            return
        folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        file = folder + '/cones.shp'
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"

        QgsVectorFileWriter.writeAsVectorFormatV2(self.mapWidget.cones, file,
                                                QgsCoordinateTransformContext(),
                                                options)

class WebMap(MapWidget):
    '''
    Custom MapWidget to facilititate displaying online or offline
    web maps
    '''
    def __init__(self, root, p1lat, p1lon, p2lat, p2lon, loadCached):
        '''
        Creates a WebMap widget
        Args:
            root: the root widget of the Application
            p1lat: float lat value
            p1lon: float lon value
            p2lat: float lat value
            p2lon: float lon value
            loadCached: boolean value to indicate tile source
        '''
        # Initialize WebMapFrame
        MapWidget.__init__(self, root)

        self.loadCached = loadCached

        
        self.addLayers()
           
        self.adjustCanvas()
        r = QgsRectangle(p1lon, p2lat, p2lon, p1lat)
        rect = self.transformToWeb.transformBoundingBox(r)
        self.canvas.zoomToFeatureExtent(rect)

        self.addToolBar()
        self.addRectTool()
        self.pan()

        self.holder.addWidget(self.toolbar)
        self.holder.addWidget(self.canvas)
        self.setLayout(self.holder)

        root.addWidget(self, 0, 1, 1, 2)
        self.root = root


    def setupEstimate(self):
        '''
        Sets up the Estimate mapLayer
        Args:
        '''
        uri = "Point?crs=epsg:3857"
        layer = QgsVectorLayer(uri, 'Estimate', "memory")
        symbol = QgsMarkerSymbol.createSimple({'name':'diamond', 
                'color':'blue'})
        layer.renderer().setSymbol(symbol)
        layer.setAutoRefreshInterval(500)
        layer.setAutoRefreshEnabled(True)
        
        return layer
    
    def setupGroundTruth(self):
        '''
        Sets up the groundTruth maplayer
        Args:
        '''
        uri = "Point?crs=epsg:3857"
        layer = QgsVectorLayer(uri, 'Estimate', "memory")
        symbol = QgsMarkerSymbol.createSimple({'name':'square', 
                'color':'cyan'})
        layer.renderer().setSymbol(symbol)
        
        return layer

   
        

    def setupVehicleLayers(self):
        '''
        Sets up the vehicle and vehicle path layers
        Args:
        '''
        uri = "Point?crs=epsg:3857"
        uriLine = "Linestring?crs=epsg:3857"
        vehicleLayer = QgsVectorLayer(uri, 'Vehicle', "memory")
        vehiclePathlayer = QgsVectorLayer(uriLine, 'VehiclePath', "memory")
        
        # Set drone image for marker symbol
        path = QDir().filePath('../resources/vehicleSymbol.svg')
        symbolSVG = QgsSvgMarkerSymbolLayer(path)
        symbolSVG.setSize(4)
        symbolSVG.setFillColor(QColor('#0000ff'))
        symbolSVG.setStrokeColor(QColor('#ff0000'))
        symbolSVG.setStrokeWidth(1)
        vehicleLayer.renderer().symbol().changeSymbolLayer(0, symbolSVG)
        
        #set autorefresh
        vehicleLayer.setAutoRefreshInterval(500)
        vehicleLayer.setAutoRefreshEnabled(True)
        vehiclePathlayer.setAutoRefreshInterval(500)
        vehiclePathlayer.setAutoRefreshEnabled(True)
        return vehicleLayer, vehiclePathlayer

    def setupConeLayer(self):
        uri = "Point?crs=epsg:3857"
        coneLayer = QgsVectorLayer(uri, 'Cone', "memory")
        path = QDir().filePath('../resources/searchingTriangle.svg')
        symbolSVG = QgsSvgMarkerSymbolLayer(path)
        symbolSVG.setSize(4)
        symbolSVG.setFillColor(QColor('#ff0000'))
        symbolSVG.setStrokeColor(QColor('#ff0000'))
        #symbolSVG.setStrokeWidth(1)
        symbolSVG.setDataDefinedProperty(QgsSymbolLayer.PropertyFillColor, QgsProperty.fromField("Color"))
        symbolSVG.setDataDefinedProperty(QgsSymbolLayer.PropertyHeight, QgsProperty.fromField("Height"))
        symbolSVG.setDataDefinedProperty(QgsSymbolLayer.PropertyVerticalAnchor, QgsProperty.fromField("VAnchor"))
        coneLayer.renderer().symbol().changeSymbolLayer(0, symbolSVG)
        coneLayer.renderer().symbol().setDataDefinedAngle(QgsProperty().fromField("Heading"))
        #coneLayer.renderer().symbol().setDataDefinedProperty(QgsProperty().fromField("Opacity"))

        cpr = coneLayer.dataProvider()
        cpr.addAttributes([QgsField(name='Heading', type=QVariant.Double, len=30),
                            QgsField(name="Amp", type=QVariant.Double, len=30),
                            QgsField(name='Color', type=QVariant.String, len=30),
                            QgsField(name="Height", type=QVariant.Double, len=30),
                            QgsField(name="VAnchor", type=QVariant.String, len=30)])
        coneLayer.updateFields()
        coneLayer.setAutoRefreshInterval(500)
        coneLayer.setAutoRefreshEnabled(True)
        return coneLayer


    def setupPingLayer(self):
        '''
        Sets up the ping layer and renderer.
        Args:
        '''
        ranges = []
        uri = "Point?crs=epsg:3857"
        layer = QgsVectorLayer(uri, 'Pings', 'memory')
        
        
        # make symbols
        symbolBlue = QgsSymbol.defaultSymbol(layer.geometryType())
        symbolBlue.setColor(QColor('#0000FF'))
        symbolCyan = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolCyan.setColor(QColor('#00FFFF'))
        symbolGreen = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolGreen.setColor(QColor('#00FF00'))
        symbolYellow = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolYellow.setColor(QColor('#FFFF00'))
        symbolOrange = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolOrange.setColor(QColor('#FFC400'))
        symbolORed = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolORed.setColor(QColor('#FFA000'))
        symbolRed = QgsSymbol.defaultSymbol(
            layer.geometryType())
        symbolRed.setColor(QColor('#FF0000'))
    
        # make ranges
        rBlue = QgsRendererRange(0, 10, symbolBlue, 'Blue')
        rCyan = QgsRendererRange(10, 20, symbolCyan, 'Cyan')
        rGreen = QgsRendererRange(20, 40, symbolGreen, 'Green')
        rYellow = QgsRendererRange(40, 60, symbolYellow, 'Yellow')
        rOrange = QgsRendererRange(60, 80, symbolOrange, 'Orange')
        rORed = QgsRendererRange(80, 90, symbolORed, 'ORed')
        rRed = QgsRendererRange(90, 100, symbolRed, 'Red')
        ranges.append(rBlue)
        ranges.append(rCyan)
        ranges.append(rGreen)
        ranges.append(rYellow)
        ranges.append(rOrange)
        ranges.append(rORed)
        ranges.append(rRed)

        # set renderer to set symbol based on amplitude
        pingRenderer = QgsGraduatedSymbolRenderer('Amp', ranges)
        
        
        style = QgsStyle.defaultStyle()
        defaultColorRampNames = style.colorRampNames()
        ramp = style.colorRamp(defaultColorRampNames[22])
        pingRenderer.setSourceColorRamp(ramp)
        pingRenderer.setSourceSymbol( QgsSymbol.defaultSymbol(layer.geometryType()))
        pingRenderer.sortByValue()
        
        
        vpr = layer.dataProvider()
        vpr.addAttributes([QgsField(name='Amp', type=QVariant.Double, len=30)])
        layer.updateFields()
    
        # set the renderer and allow the mapLayer to auto refresh
        layer.setRenderer(pingRenderer)
        layer.setAutoRefreshInterval(500)
        layer.setAutoRefreshEnabled(True)
        
        return layer, pingRenderer
    
    def setupPrecisionLayer(self):
        path = QDir().currentPath()
        uri = 'file:///' + path + '/holder/query.csv?encoding=%s&delimiter=%s&xField=%s&yField=%s&crs=%s&value=%s' % ("UTF-8",",", "easting", "northing","epsg:32611", "value")
        
        csv_layer= QgsVectorLayer(uri, "query", "delimitedtext")
        
        csv_layer.setOpacity(0.5)
        
        heatmap = QgsHeatmapRenderer()
        heatmap.setWeightExpression('value')
        heatmap.setRadiusUnit(QgsUnitTypes.RenderUnit.RenderMetersInMapUnits)
        heatmap.setRadius(3)
        csv_layer.setRenderer(heatmap)
        
        csv_layer.setAutoRefreshInterval(500)
        csv_layer.setAutoRefreshEnabled(True)
        
        return csv_layer

    def setUpPolygonLayer(self):
        uri = "Polygon?crs=epsg:3857"
        polygonPointLayer = QgsVectorLayer(uri, 'Polygon', "memory")
        return polygonPointLayer

    def addLayers(self):
        '''
        Helper method to add map layers to map canvas
        '''
        if self.estimate is None:
            self.estimate = self.setupEstimate()
            
            
        if self.vehicle is None:
            self.vehicle, self.vehiclePath = self.setupVehicleLayers()
            
        if self.pingLayer is None:
            self.pingLayer, self.pingRenderer = self.setupPingLayer()
            
        if self.groundTruth is None:
            self.groundTruth = self.setupGroundTruth()
            
        if self.cones is None:
            self.cones = self.setupConeLayer()

        if self.polygonLayer is None:
            self.polygonLayer = self.setUpPolygonLayer()
        
        
        #load from cached tiles if true, otherwise loads from web    
        if self.loadCached:
            path = QDir().currentPath()
            urlWithParams = 'type=xyz&url=file:///'+ path+'/tiles/%7Bz%7D/%7Bx%7D/%7By%7D.png'
        else:
            urlWithParams = 'type=xyz&url=http://a.tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0&crs=EPSG3857'    
        self.mapLayer = QgsRasterLayer(urlWithParams, 'OpenStreetMap', 'wms') 
        '''
        if self.precision is None:
            self.precision = self.setupPrecisionLayer()
            destCrs = self.mapLayer.crs()
            rasterCrs = self.precision.crs()
            self.precision.setCrs(rasterCrs)
            self.canvas.setDestinationCrs(destCrs)
        ''' 
        if self.mapLayer.isValid():   
            crs = self.mapLayer.crs()
            crs.createFromString("EPSG:3857")  
            self.mapLayer.setCrs(crs)
            
            #add all layers to map
            QgsProject.instance().addMapLayer(self.mapLayer)
            QgsProject.instance().addMapLayer(self.groundTruth)
            QgsProject.instance().addMapLayer(self.estimate)
            QgsProject.instance().addMapLayer(self.vehicle)
            QgsProject.instance().addMapLayer(self.vehiclePath)
            QgsProject.instance().addMapLayer(self.pingLayer)
            QgsProject.instance().addMapLayer(self.cones)
            #QgsProject.instance().addMapLayer(self.precision)
            print('valid mapLayer')
        else:
            print('invalid mapLayer')
            raise RuntimeError



    def addRectTool(self):
        '''
        Helper function to add the rectangle tool to the toolbar
        '''
        self.rectAction = QAction("Rect", self)
        self.rectAction.setCheckable(True)
        self.rectAction.triggered.connect(self.rect)
        self.toolbar.addAction(self.rectAction)
        self.toolRect = RectangleMapTool(self.canvas)
        self.toolRect.setAction(self.rectAction)

    def rect(self):
        '''
        Helper function to set rect tool when it is selected from 
        the toolbar
        '''
        self.canvas.setMapTool(self.toolRect)

    def deg2num(self, lat_deg, lon_deg, zoom):
        '''
        Helper function to calculate the map tile number for a given 
        location
        Args:
            lat_deg: float latitude value
            lon_deg: float longitude value
            zoom: integer zoom value
        '''
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        x = int((lon_deg + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (x,y)
        

    def cacheMap(self):
        '''
        Function to facilitate caching map tiles
        '''
        if (self.toolRect.rectangle() == None):
            return
        else:
            rect = self.toolRect.rectangle()
            r = self.transform.transformBoundingBox(self.toolRect.rectangle(), 
                                QgsCoordinateTransform.ForwardTransform, True)
            print("Rectangle:", r.xMinimum(),
                    r.yMinimum(), r.xMaximum(), r.yMaximum()
                 )
            
            if (r != None):
                zoomStart = 17
                tilecount = 0
                for zoom in range(zoomStart, 19, 1):
                    xmin, ymin = self.deg2num(float(r.yMinimum()),float(r.xMinimum()),zoom)
                    xmax, ymax = self.deg2num(float(r.yMaximum()),float(r.xMaximum()),zoom)
                    print("Zoom:", zoom)
                    print(xmin, xmax, ymin, ymax)
                    for x in range(xmin, xmax+1, 1):
                        for y in range(ymax, ymin+1, 1):
                            if (tilecount < 200):
                                time.sleep(1)
                                downloaded = self.downloadTile(x,y,zoom)
                                if downloaded:
                                    tilecount = tilecount + 1
                            else:
                                print("tile count exceeded, pls try again in a few minutes")
                                return
                print("Download Complete")
            else:
                print("Download Failed")
            
            
    def downloadTile(self, xtile, ytile, zoom):
        '''
        Helper Function to facilitate the downloading of web tiles
        '''
        url = "http://c.tile.openstreetmap.org/%d/%d/%d.png" % (zoom, xtile, ytile)
        dir_path = "tiles/%d/%d/" % (zoom, xtile)
        download_path = "tiles/%d/%d/%d.png" % (zoom, xtile, ytile)
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        
        if(not os.path.isfile(download_path)):
            print("downloading %r" % url)
            # requires up to date user agent
            source = requests.get(url, headers = {'User-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36'})
            cont = source.content
            source.close()
            destination = open(download_path,'wb')
            destination.write(cont)
            destination.close()
            return True
        else: 
            print("skipped %r" % url)
            return False

        return True

class StaticMap(MapWidget):
    '''
    Custom MapWidget to facilititate displaying a static raster file
    '''
    def __init__(self, root):
        '''
        Creates a StaticMap object
        Args:
            root: the root widget of the application
        '''
        MapWidget.__init__(self, root)

        self.fileName = None

        self.__getFileName()
        self.__addLayers()

        self.adjustCanvas()
        self.addToolBar()
        self.pan()

        self.holder.addWidget(self.toolbar)
        self.holder.addWidget(self.canvas)
        self.setLayout(self.holder)

        root.addWidget(self, 0, 1, 1, 2)
        self.root = root


    def __getFileName(self):
        '''
        inner function to retrieve a user specified raster file
        '''
        self.fileName = QFileDialog.getOpenFileName()      

    def __addLayers(self):
        '''
        Helper funciton to add layers to the map canvas
        '''
        if(self.fileName == None):
            return

        self.mapLayer = QgsRasterLayer(self.fileName[0], "SRTM layer name")
        if not self.mapLayer.crs().isValid():
            raise FileNotFoundError("Invalid file, loading from web...")
        print(self.mapLayer.crs())

        if self.estimate is None:
            uri = "Point?crs=epsg:4326"

            self.estimate = QgsVectorLayer(uri, 'Estimate', "memory")

            symbol = QgsMarkerSymbol.createSimple({'name': 'diamond', 'color': 'blue'})
            self.estimate.renderer().setSymbol(symbol)


            self.estimate.setAutoRefreshInterval(500)
            self.estimate.setAutoRefreshEnabled(True)


        if self.vehicle is None:
            uri = "Point?crs=epsg:4326"
            uriLine = "Linestring?crs=epsg:4326"

            self.vehicle = QgsVectorLayer(uri, 'Vehicle', "memory")
            self.vehiclePath = QgsVectorLayer(uriLine, 'VehiclePath', "memory")

            # Set drone image for marker symbol
            path = QDir().currentPath()
            full = path +'/camera.svg'
            symbolSVG = QgsSvgMarkerSymbolLayer(full)
            symbolSVG.setSize(4)
            symbolSVG.setFillColor(QColor('#0000ff'))
            symbolSVG.setStrokeColor(QColor('#ff0000'))
            symbolSVG.setStrokeWidth(1)
            
            self.vehicle.renderer().symbol().changeSymbolLayer(0, symbolSVG )
            
            #set autorefresh
            self.vehicle.setAutoRefreshInterval(500)
            self.vehicle.setAutoRefreshEnabled(True)
            self.vehiclePath.setAutoRefreshInterval(500)
            self.vehiclePath.setAutoRefreshEnabled(True)
            
        if self.pingLayer is None:
            ranges = []
            uri = "Point?crs=epsg:4326"
            self.pingLayer = QgsVectorLayer(uri, 'Pings', 'memory')

            # make symbols
            symbolBlue = QgsSymbol.defaultSymbol(
                    self.pingLayer.geometryType())
            symbolBlue.setColor(QColor('#0000FF'))
            symbolGreen = QgsSymbol.defaultSymbol(
                    self.pingLayer.geometryType())
            symbolGreen.setColor(QColor('#00FF00'))
            symbolYellow = QgsSymbol.defaultSymbol(
                    self.pingLayer.geometryType())
            symbolYellow.setColor(QColor('#FFFF00'))
            symbolOrange = QgsSymbol.defaultSymbol(
                    self.pingLayer.geometryType())
            symbolOrange.setColor(QColor('#FFA500'))
            symbolRed = QgsSymbol.defaultSymbol(
                    self.pingLayer.geometryType())
            symbolRed.setColor(QColor('#FF0000'))

            # make ranges
            rBlue = QgsRendererRange(0, 20, symbolBlue, 'Blue')
            rGreen = QgsRendererRange(20, 40, symbolGreen, 'Green')
            rYellow = QgsRendererRange(40, 60, symbolYellow, 'Yellow')
            rOrange = QgsRendererRange(60, 80, symbolOrange, 'Orange')
            rRed = QgsRendererRange(80, 100, symbolRed, 'Red')

            ranges.append(rBlue)
            ranges.append(rGreen)
            ranges.append(rYellow)
            ranges.append(rOrange)
            ranges.append(rRed)

            # set renderer to set symbol based on amplitude
            self.pingRenderer = QgsGraduatedSymbolRenderer('Amp', ranges)
            myClassificationMethod = QgsApplication.classificationMethodRegistry().method("EqualInterval")
            self.pingRenderer.setClassificationMethod(myClassificationMethod)
            self.pingRenderer.setClassAttribute('Amp')
            vpr = self.pingLayer.dataProvider()
            vpr.addAttributes([QgsField(name='Amp', type=QVariant.Double, len=30)])
            self.pingLayer.updateFields()

            # set the renderer and allow the layerayer to auto refresh
            self.pingLayer.setRenderer(self.pingRenderer)
            self.pingLayer.setAutoRefreshInterval(500)
            self.pingLayer.setAutoRefreshEnabled(True)

        if self.mapLayer.isValid():
            QgsProject.instance().addMapLayer(self.mapLayer)
            QgsProject.instance().addMapLayer(self.estimate)
            QgsProject.instance().addMapLayer(self.vehicle)
            QgsProject.instance().addMapLayer(self.vehiclePath)
            QgsProject.instance().addMapLayer(self.pingLayer)
            print('valid layer')
        else:
            print('invalid layer')
