import csv
import logging
import math
import os
import os.path
import sys
from pathlib import Path
from threading import Thread

import requests
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from RctGcs.ui.controls import *
from RctGcs.ui.popups import *
from RctGcs.utils import fix_conda_path

fix_conda_path()

import qgis.gui
from qgis.core import *
from qgis.core import QgsProject
from qgis.utils import *


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
        self.rubber_band = qgis.gui.QgsRubberBand(self.canvas, True)
        self.rubber_band.setColor(QColor(0,255,255,125))
        self.rubber_band.setWidth(1)
        self.reset()

    def reset(self):
        '''
        '''
        self.start_point = self.end_point = None
        self.is_emitting_point = False
        self.rubber_band.reset(True)

    def canvasPressEvent(self, e):
        '''
        Internal callback to be called when the user's mouse
        presses the canvas
        Args:
            e: The press event
        '''
        self.start_point = self.toMapCoordinates(e.pos())
        self.end_point = self.start_point
        self.is_emitting_point = True
        self.show_rect(self.start_point, self.end_point)

    def canvasReleaseEvent(self, e):
        '''
        Internal callback called when the user's mouse releases
        over the canvas
        Args:
            e: The release event
        '''
        self.is_emitting_point = False

    def canvasMoveEvent(self, e):
        '''
        Internal callback called when the user's mouse moves
        over the canvas
        Args:
            e: The move event
        '''
        if not self.is_emitting_point:
            return

        self.end_point = self.toMapCoordinates(e.pos())
        self.show_rect(self.start_point, self.end_point)

    def show_rect(self, start_point, end_point):
        '''
        Internal function to display the rectangle being
        specified by the user
        '''
        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        if start_point.x() == end_point.x() or start_point.y() == end_point.y():
            return

        point1 = QgsPointXY(start_point.x(), start_point.y())
        point2 = QgsPointXY(start_point.x(), end_point.y())
        point3 = QgsPointXY(end_point.x(), end_point.y())
        point4 = QgsPointXY(end_point.x(), start_point.y())

        self.rubber_band.addPoint(point1, False)
        self.rubber_band.addPoint(point2, False)
        self.rubber_band.addPoint(point3, False)
        self.rubber_band.addPoint(point4, True)    # true to update canvas
        self.rubber_band.show()

    def rectangle(self):
        '''
        Function to return the rectangle that has been selected
        '''
        if self.start_point is None or self.end_point is None:
            return None
        elif (self.start_point.x() == self.end_point.x() or \
              self.start_point.y() == self.end_point.y()):
            return None

        return QgsRectangle(self.start_point, self.end_point)

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
        self.rubber_band = qgis.gui.QgsRubberBand(self.canvas,
            QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(Qt.red)
        self.rubber_band.setWidth(1)
        self.reset()

    def reset(self):
        self.start_point = self.end_point = None
        self.is_emitting_point = False
        self.rubber_band.reset(True)

    def canvasPressEvent(self, e):
        self.start_point = self.toMapCoordinates(e.pos())
        self.end_point = self.start_point
        self.is_emitting_point = True
        self.add_vertex(self.start_point, self.canvas)
        self.show_line(self.start_point, self.end_point)
        self.show_polygon()

    def canvasReleaseEvent(self, e):
        self.is_emitting_point = False

    def canvasMoveEvent(self, e):
        if not self.is_emitting_point:
            return

        self.end_point = self.toMapCoordinates(e.pos())
        self.show_line(self.start_point, self.end_point)

    def add_vertex(self, selectPoint, canvas):
        vertex = QgsPointXY(selectPoint)
        self.vertices.append(vertex)

    def show_polygon(self):
        if (len(self.vertices) > 1):
            self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            r = len(self.vertices) - 1
            for i in range(r):
                self.rubber_band.addPoint(self.vertices[i], False)
            self.rubber_band.addPoint(self.vertices[r], True)
            self.rubber_band.show()

    def show_line(self, start_point, end_point):
        self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        if start_point.x() == end_point.x() or start_point.y() == end_point.y():
            return

        point1 = QgsPointXY(start_point.x(), start_point.y())

        self.rubber_band.addPoint(point1, True)

        self.rubber_band.show()

    def deactivate(self):
        qgis.gui.QgsMapTool.deactivate(self)
        self.deactivated.emit()

class VehicleData:
    '''
    Information about displaying a vehicle on the map
    '''
    def __init__(self):
        self.ind = 0
        self.last_loc = None

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
        self.ground_truth = None
        self.map_layer = None
        self.vehicle = None
        self.vehicle_path = None
        self.precision = None
        self.cones = None
        self.vehicle_data = {}
        self.ping_layer = None
        self.ping_renderer = None
        self.estimate = None
        self.tool_polygon = None
        self.polygon_layer = None
        self.polygon_action = None
        self.heat_map = None
        self.ping_min = 800
        self.ping_max = 0
        self.cone_min = sys.float_info.max
        self.cone_max = sys.float_info.min
        self.ind = 0
        self.ind_ping = 0
        self.ind_est = 0
        self.ind_cone = 0
        self.toolbar = QToolBar()
        self.canvas = qgis.gui.QgsMapCanvas()
        self.canvas.setCanvasColor(Qt.white)

        self.transform_to_web = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsCoordinateReferenceSystem("EPSG:3857"),
                QgsProject.instance())
        self.transform = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem("EPSG:3857"),
                QgsCoordinateReferenceSystem("EPSG:4326"),
                QgsProject.instance())

    def set_up_heat_map(self):
        '''
        Sets up the heat_map map_layer
        Args:
        '''
        file_name = QFileDialog.getOpenFileName()
        print(file_name[0])
        if self.heat_map is not None:
            QgsProject.instance().removemap_layer(self.heat_map)
        if file_name is not None:
            self.heat_map = QgsRasterLayer(file_name[0], "heat_map")

            stats = self.heat_map.dataProvider().bandStatistics(1)
            max_val = stats.maximumValue
            print(max_val)
            fcn = QgsColorRampShader()
            fcn.setColorRampType(QgsColorRampShader.Interpolated)
            lst = [ QgsColorRampShader.ColorRampItem(0, QColor(0,0,0)),
                QgsColorRampShader.ColorRampItem(max_val, QColor(255,255,255)) ]
            fcn.setColorRampItemList(lst)
            shader = QgsRasterShader()
            shader.setRasterShaderFunction(fcn)

            renderer = QgsSingleBandPseudoColorRenderer(self.heat_map.dataProvider(), 1, shader)
            self.heat_map.setRenderer(renderer)

            QgsProject.instance().add_map_layer(self.heat_map)
            dest_crs = self.map_layer.crs()
            raster_crs = self.heat_map.crs()

            self.heat_map.setCrs(raster_crs)
            self.canvas.setDestinationCrs(dest_crs)


            self.canvas.setLayers([self.heat_map, self.estimate, self.ground_truth,
                               self.vehicle, self.ping_layer,
                               self.vehicle_path, self.map_layer])

    def plot_precision(self, coord, freq, num_pings):
        data_dir = 'holder'
        output_file_name = '/%s/PRECISION_%03.3f_%d_heat_map.tiff' % (data_dir, freq / 1e7, num_pings)
        file_name = QDir().currentPath() + output_file_name
        print(file_name)
        print(output_file_name)

        if self.heat_map is not None:
            QgsProject.instance().removemap_layer(self.heat_map)
        if file_name is not None:
            self.heat_map = QgsRasterLayer(file_name, "heat_map")

            stats = self.heat_map.dataProvider().bandStatistics(1)
            max_val = stats.maximumValue
            print(max_val)
            fcn = QgsColorRampShader()
            fcn.setColorRampType(QgsColorRampShader.Interpolated)
            lst = [ QgsColorRampShader.ColorRampItem(0, QColor(0,0,0)),
                QgsColorRampShader.ColorRampItem(max_val, QColor(255,255,255)) ]
            fcn.setColorRampItemList(lst)
            shader = QgsRasterShader()
            shader.setRasterShaderFunction(fcn)

            renderer = QgsSingleBandPseudoColorRenderer(self.heat_map.dataProvider(), 1, shader)
            self.heat_map.setRenderer(renderer)

            QgsProject.instance().add_map_layer(self.heat_map)
            dest_crs = self.map_layer.crs()
            raster_crs = self.heat_map.crs()

            self.heat_map.setCrs(raster_crs)
            self.canvas.setDestinationCrs(dest_crs)
            self.heat_map.renderer().setOpacity(0.7)

            self.canvas.setLayers([self.heat_map, self.estimate,
                        self.ground_truth, self.vehicle, self.ping_layer,
                        self.vehicle_path, self.map_layer])

    def adjust_canvas(self):
        '''
        Helper function to set and adjust the camvas' layers
        '''
        self.canvas.setExtent(self.map_layer.extent())
        self.canvas.setLayers([self.precision, self.estimate, self.ground_truth,
                               self.vehicle, self.ping_layer, self.cones,
                               self.vehicle_path, self.polygon_layer, self.map_layer])
        #self.canvas.setLayers([self.map_layer])
        self.canvas.zoomToFullExtent()
        self.canvas.freeze(True)
        self.canvas.show()
        self.canvas.refresh()
        self.canvas.freeze(False)
        self.canvas.repaint()

    def add_toolbar(self):
        '''
        Internal function to add tools to the map toolbar
        '''
        self.action_zoom_in = QAction("Zoom in", self)
        self.action_zoom_out = QAction("Zoom out", self)
        self.action_pan = QAction("Pan", self)

        self.action_zoom_in.setCheckable(True)
        self.action_zoom_out.setCheckable(True)
        self.action_pan.setCheckable(True)

        self.action_zoom_in.triggered.connect(self.zoom_in)
        self.action_zoom_out.triggered.connect(self.zoom_out)
        self.action_pan.triggered.connect(self.pan)

        self.toolbar.addAction(self.action_zoom_in)
        self.toolbar.addAction(self.action_zoom_out)
        self.toolbar.addAction(self.action_pan)

        # create the map tools
        self.tool_pan = qgis.gui.QgsMapToolPan(self.canvas)
        self.tool_pan.setAction(self.action_pan)
        self.tool_zoom_in =qgis.gui. QgsMapToolZoom(self.canvas, False) # false = in
        self.tool_zoom_in.setAction(self.action_zoom_in)
        self.tool_zoom_out = qgis.gui.QgsMapToolZoom(self.canvas, True) # true = out
        self.tool_zoom_out.setAction(self.action_zoom_out)

        self.polygon_action = QAction("Polygon", self)
        self.polygon_action.setCheckable(True)
        self.polygon_action.triggered.connect(self.polygon)
        self.toolbar.addAction(self.polygon_action)
        self.tool_polygon = PolygonMapTool(self.canvas)
        self.tool_polygon.setAction(self.polygon_action)

    def polygon(self):
        '''
        Helper function to set polygon tool when it is selected from
        the toolbar
        '''
        self.canvas.setMapTool(self.tool_polygon)

    def zoom_in(self):
        '''
        Helper function to set the zoom_in map tool when it is selected
        '''
        self.canvas.setMapTool(self.tool_zoom_in)

    def zoom_out(self):
        '''
        Helper function to set the zoom_out map tool when it is selected
        '''
        self.canvas.setMapTool(self.tool_zoom_out)

    def pan(self):
        '''
        Helper function to set the pan map tool when it is selected
        '''
        self.canvas.setMapTool(self.tool_pan)

    def plot_vehicle(self, id, coord):
        '''
        Function to plot the vehicle's current location on the vehicle
        map layer
        Args:
            coord: A tuple of float values indicating an EPSG:4326 lat/Long
                   coordinate pair
        '''
        lat = coord[0]
        lon = coord[1]
        point = self.transform_to_web.transform(QgsPointXY(lon, lat))
        if self.vehicle is None:
            return
        else:
            vehicle_data = VehicleData()
            if id not in self.vehicle_data:
                self.vehicle_data[id] = vehicle_data
            else:
                vehicle_data = self.vehicle_data[id]
            if vehicle_data.ind > 0:
                lpr = self.vehicle_path.dataProvider()
                lin = QgsGeometry.fromPolylineXY([vehicle_data.last_loc, point])
                line_feat = QgsFeature()
                line_feat.setGeometry(lin)
                lpr.addFeatures([line_feat])
                vpr = self.vehicle.dataProvider()
                self.vehicle.startEditing()
                self.vehicle.deleteFeature(vehicle_data.ind)
                self.vehicle.commitChanges()

            vehicle_data.last_loc = point
            vpr = self.vehicle.dataProvider()
            pnt = QgsGeometry.fromPointXY(point)
            f = QgsFeature()
            f.setGeometry(pnt)
            vpr.addFeatures([f])
            self.vehicle.updateExtents()
            self.ind = self.ind + 1
            vehicle_data.ind = self.ind

    def plot_cone(self, coord):
        lat = coord[0]
        lon = coord[1]
        heading = coord[4]
        #power = coord[3]
        #dummy power values to test calc_color
        power_arr =  [2.4, 4, 5, 2.1, 3, 8, 5.9, 2, 1, 3, 5, 4]
        aind = self.ind_cone % 12
        power = power_arr[aind]

        point = self.transform_to_web.transform(QgsPointXY(lon, lat))
        if self.cone_min > power:
            self.cone_min = power
        if self.cone_max < power:
            self.cone_max = power

        if self.cones is None:
            return
        else:
            if self.ind_cone > 4:
                self.cones.startEditing()
                self.cones.deleteFeature(self.ind_cone-5)
                self.cones.commitChanges()

            # update cone color/length based on cone_min-cone_max range
            update_ind = self.ind_cone
            opacity = 1
            updates = {}
            while update_ind >= self.ind_cone-4 and update_ind > 0:
                feature = self.cones.getFeature(update_ind)
                amp = feature.attributes()[1]
                color = self.calc_color(amp, self.cone_min, self.cone_max, opacity)
                height = self.calc_height(amp, self.cone_min, self.cone_max)
                updates[update_ind] = {2: color, 3: height}
                update_ind -= 1
                opacity -= 0.2

            #Add new cone
            cpr = self.cones.dataProvider()
            cpr.changeAttributeValues(updates)
            pnt = QgsGeometry.fromPointXY(point)
            feature = QgsFeature()
            feature.setFields(self.cones.fields())
            feature.setGeometry(pnt)
            feature.setAttribute(0, heading)
            feature.setAttribute(1, power)
            feature.setAttribute(2,
                    self.calc_color(power, self.cone_min, self.cone_max, 1))
            feature.setAttribute(3,
                    self.calc_height(power, self.cone_min, self.cone_max))
            feature.setAttribute(4, "bottom")
            cpr.addFeatures([feature])
            self.cones.updateExtents()
            self.ind_cone = self.ind_cone + 1

    def calc_color(self, amp, min_amp, max_amp, opac):
        '''
        Calculates hex color value for a cone based on variable range
        Colors range between red (strongest) and blue (weakest)
        Args:
            amp: Float containing cone signal amplitude
            min_amp: Flaot representing minimum amplitude in range
            max_amp: Float representing maximum amplitude in range
            opac: Float representing percent opacity
        '''
        if (min_amp == max_amp):
            color_ratio = 0.5
        else:
            color_ratio = (amp - min_amp)/(max_amp - min_amp)
        red = int(255 * color_ratio)
        blue = int(255 * (1-color_ratio))
        opacity = int(255 * opac)
        color = "#%02x%02x%02x%02x" % (opacity, red, 0, blue)
        return color

    def calc_height(self, amp, min_amp, max_amp):
        '''
        Calculates double value for a cone's length based on variable min_amp-max_amp range
        Args:
            amp: Float containing cone signal amplitude
            min_amp: Flaot representing minimum amplitude in range
            max_amp: Float representing maximum amplitude in range
        '''
        height = 4.0
        if (min_amp != max_amp):
            height = 3.0 * (amp - min_amp)/(max_amp - min_amp) + 1
        return height

    def plot_ping(self, coord, power):
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
        point = self.transform_to_web.transform(QgsPointXY(lon, lat))
        if self.ping_layer is None:
            return

        else:
            if power < self.ping_min:
                change = True
                self.ping_min = power
            if power > self.ping_max:
                change = True
                self.ping_max = power
            if (self.ping_max == self.ping_min):
                self.ping_max = self.ping_max + 1
            if change:
                r = self.ping_max - self.ping_min
                first = r * 0.14
                second = r * 0.28
                third = r * 0.42
                fourth = r * 0.56
                fifth = r * 0.7
                sixth = r * 0.84

                for i, range_obj in enumerate(self.ping_renderer.ranges()):
                    if range_obj.label() == 'Blue':
                        self.ping_renderer.updateRangeLowerValue(i, self.ping_min)
                        self.ping_renderer.updateRangeUpperValue(i, self.ping_min + first)
                    if range_obj.label() == 'Cyan':
                        self.ping_renderer.updateRangeLowerValue(i, self.ping_min + first)
                        self.ping_renderer.updateRangeUpperValue(i, self.ping_min + second)
                    if range_obj.label() == 'Green':
                        self.ping_renderer.updateRangeLowerValue(i, self.ping_min + second)
                        self.ping_renderer.updateRangeUpperValue(i, self.ping_min + third)
                    if range_obj.label() == 'Yellow':
                        self.ping_renderer.updateRangeLowerValue(i, self.ping_min + third)
                        self.ping_renderer.updateRangeUpperValue(i, self.ping_min + fourth)
                    if range_obj.label() == 'Orange':
                        self.ping_renderer.updateRangeLowerValue(i, self.ping_min +fourth)
                        self.ping_renderer.updateRangeUpperValue(i, self.ping_min + fifth)
                    if range_obj.label() == 'ORed':
                        self.ping_renderer.updateRangeLowerValue(i, self.ping_min +fifth)
                        self.ping_renderer.updateRangeUpperValue(i, self.ping_min + sixth)
                    if range_obj.label() == 'Red':
                        self.ping_renderer.updateRangeLowerValue(i, self.ping_min + sixth)
                        self.ping_renderer.updateRangeUpperValue(i, self.ping_max)

            vpr = self.ping_layer.dataProvider()

            #Create new ping point
            pnt = QgsGeometry.fromPointXY(point)
            feature = QgsFeature()
            feature.setFields(self.ping_layer.fields())
            feature.setGeometry(pnt)
            feature.setAttribute(0, power)
            vpr.addFeatures([feature])
            self.ping_layer.updateExtents()

    def plot_estimate(self, coord, frequency):
        '''
        Function to plot the current estimate point on the estimate map layer
        Args:
            coord: A tuple of float values indicating an EPSG:4326 lat/Long
                   coordinate pair
            frequency: the frequency that this estimate corresponds to
        '''
        lat = coord[0]
        lon = coord[1]
        point = self.transform_to_web.transform(QgsPointXY(lon, lat))

        if self.estimate is None:
            return
        if self.ind_est > 0:
            self.estimate.startEditing()
            self.estimate.deleteFeature(self.ind_est)
            self.estimate.commitChanges()

        vpr = self.estimate.dataProvider()
        pnt = QgsGeometry.fromPointXY(point)
        feature = QgsFeature()
        feature.setGeometry(pnt)
        vpr.addFeatures([feature])
        self.estimate.updateExtents()
        self.ind_est = self.ind_est + 1

class MapOptions(QWidget):
    '''
    Custom Widget facilitate map caching and exporting map layers
    '''
    def __init__(self):
        '''
        Creates a MapOptions widget
        '''
        QWidget.__init__(self)

        self.map_widget = None
        self.btn_cache_map = None
        self.is_web_map = False
        self.lbl_dist = None
        self.__create_widgets()
        self.created = False
        self.writer = None
        self.has_point = False
        self.user_pops = UserPopups()

    def __create_widgets(self):
        '''
        Inner function to create internal widgets
        '''
        # MAP OPTIONS
        lay_map_options = QVBoxLayout()

        lbl_map_options = QLabel('Map Options')
        lay_map_options.addWidget(lbl_map_options)

        self.btn_set_search_area = QPushButton('Set Search Area')
        self.btn_set_search_area.setEnabled(False)
        lay_map_options.addWidget(self.btn_set_search_area)

        self.btn_cache_map = QPushButton('Cache Map')
        self.btn_cache_map.clicked.connect(self.__cache_map)
        self.btn_cache_map.setEnabled(False)
        lay_map_options.addWidget(self.btn_cache_map)

        self.btn_clear_map = QPushButton('Clear Map')
        self.btn_clear_map.clicked.connect(self.clear)
        self.btn_clear_map.setEnabled(True)
        lay_map_options.addWidget(self.btn_clear_map)

        export_tab = CollapseFrame('Export')
        btn_ping_export = QPushButton('Pings')
        btn_ping_export.clicked.connect(self.export_ping)

        btn_vehicle_path_export = QPushButton('Vehicle Path')
        btn_vehicle_path_export.clicked.connect(self.export_vehicle_path)

        btn_polygon_export = QPushButton('Polygon')
        btn_polygon_export.clicked.connect(self.export_polygon)

        btn_cone_export = QPushButton('Cones')
        btn_cone_export.clicked.connect(self.export_cone)

        lay_export = QVBoxLayout()
        lay_export.addWidget(btn_ping_export)
        lay_export.addWidget(btn_vehicle_path_export)
        lay_export.addWidget(btn_polygon_export)
        lay_export.addWidget(btn_cone_export)
        export_tab.set_content_layout(lay_export)

        lay_map_options.addWidget(export_tab)

        dist_widget = QWidget()
        dist_lay = QHBoxLayout()
        lbl_dist = QLabel('Distance from Actual')
        self.lbl_dist = QLabel('')
        dist_lay.addWidget(lbl_dist)
        dist_lay.addWidget(self.lbl_dist)
        dist_widget.setLayout(dist_lay)

        lay_map_options.addWidget(dist_widget)
        self.setLayout(lay_map_options)

    def clear(self):
        '''
        Helper function to clear selected map areas
        '''
        if self.map_widget is None:
            return
        self.map_widget.tool_polygon.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        self.map_widget.tool_rect.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        self.map_widget.tool_polygon.vertices.clear()

    def __cache_map(self):
        '''
        Inner function to facilitate map caching
        '''
        if self.is_web_map:
            if (self.map_widget.tool_rect.rectangle() == None):
                self.user_pops.show_warning(
                    "Use the rect tool to choose an area on the map to cache",
                    "No specified area to cache!")
                self.map_widget.rect()
            else:
                cache_thread = Thread(target=self.map_widget.cache_map)
                cache_thread.start()
                self.map_widget.canvas.refresh()
        else:
            print("alert")

    def set_map(self, map_widget: MapWidget, is_web_map):
        '''
        Function to set the MapWidget that this object will use
        Args:
            map_widget: A MapWidget object
            is_web_map: A boolean indicating whether or not the MapWidget
                      is a WebMap
        '''
        self.is_web_map = is_web_map
        self.map_widget = map_widget
        self.btn_cache_map.setEnabled(is_web_map)

    def est_distance(self, coord, stale, res):
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

        if not self.has_point:
            point = self.map_widget.transform_to_web.transform(QgsPointXY(lon2, lat2))
            vpr = self.map_widget.ground_truth.dataProvider()
            pnt = QgsGeometry.fromPointXY(point)
            feature = QgsFeature()
            feature.setGeometry(pnt)
            vpr.addFeatures([feature])
            self.map_widget.ground_truth.updateExtents()
            self.has_point = True

        dist = self.distance(lat1, lat2, lon1, lon2)

        if not self.created:
            with open('results.csv', 'w', newline='') as csvfile:
                field_names = ['Distance', 'res.x', 'residuals']
                self.writer = csv.DictWriter(csvfile, fieldnames=field_names)
                self.writer.writeheader()
                self.created = True
                self.writer.writerow({'Distance': str(dist),
                    'res.x': str(res.x), 'residuals': str(res.fun)})
        else:
            with open('results.csv', 'a+', newline='') as csvfile:
                field_names = ['Distance', 'res.x', 'residuals']
                self.writer = csv.DictWriter(csvfile, fieldnames=field_names)
                self.writer.writerow({'Distance': str(dist),
                    'res.x': str(res.x), 'residuals': str(res.fun)})

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

    def export_ping(self):
        '''
        Method to export a MapWidget's ping_layer to a shapefile
        '''
        if self.map_widget is None:
            self.user_pops.show_warning("Load a map before exporting.")
            return

        folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        file = folder + '/pings.shp'
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"

        QgsVectorFileWriter.writeAsVectorFormatV2(self.map_widget.ping_layer,
                                file, QgsCoordinateTransformContext(), options)

    def export_vehicle_path(self):
        '''
        Method to export a MapWidget's vehicle_path to a shapefile
        '''
        if self.map_widget is None:
            self.user_pops.show_warning("Load a map before exporting.")
            return

        folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        file = folder + '/vehicle_path.shp'
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"

        QgsVectorFileWriter.writeAsVectorFormatV2(self.map_widget.vehicle_path,
                                file, QgsCoordinateTransformContext(), options)

    def export_polygon(self):
        '''
        Method to export MapWidget's Polygon shape to a shapefile
        '''
        if self.map_widget is None:
            self.user_pops.show_warning("Load a map before exporting.")
            return

        if self.map_widget.tool_polygon is None:
            return
        elif len(self.map_widget.tool_polygon.vertices) == 0:
            self.user_pops.show_warning("Use the polygon tool to choose an area on the map to export", "No specified area to export!")
            self.map_widget.polygon()
        else:
            vpr = self.map_widget.polygon_layer.dataProvider()
            points = self.map_widget.tool_polygon.vertices
            print(type(points[0]))
            polyGeom = QgsGeometry.fromPolygonXY([points])

            feature = QgsFeature()
            feature.setGeometry(polyGeom)
            vpr.addFeatures([feature])
            self.map_widget.polygon_layer.updateExtents()

            folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
            file = folder + '/polygon.shp'
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "ESRI Shapefile"

            QgsVectorFileWriter.writeAsVectorFormatV2(
                                self.map_widget.polygon_layer, file,
                                QgsCoordinateTransformContext(), options)
            vpr.truncate()

    def export_cone(self):
        '''
        Method to export a MapWidget's cones to a shapefile
        '''
        if self.map_widget is None:
            self.user_pops.show_warning("Load a map before exporting.")
            return
        folder = str(QFileDialog.getExistingDirectory(self, "Select Directory"))
        file = folder + '/cones.shp'
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "ESRI Shapefile"

        QgsVectorFileWriter.writeAsVectorFormatV2(self.map_widget.cones, file,
                                    QgsCoordinateTransformContext(), options)

class WebMap(MapWidget):
    '''
    Custom MapWidget to facilititate displaying online or offline
    web maps
    '''
    def __init__(self, root, p1_lat, p1_lon, p2_lat, p2_lon, load_cached):
        '''
        Creates a WebMap widget
        Args:
            root: the root widget of the Application
            p1_lat: float lat value
            p1_lon: float lon value
            p2_lat: float lat value
            p2_lon: float lon value
            load_cached: boolean value to indicate tile source
        '''
        # Initialize WebMapFrame
        MapWidget.__init__(self, root)
        self.__log = logging.getLogger('WebMap')
        self.load_cached = load_cached

        self.add_layers()

        self.adjust_canvas()
        r = QgsRectangle(p1_lon, p2_lat, p2_lon, p1_lat)
        rect = self.transform_to_web.transformBoundingBox(r)
        self.canvas.zoomToFeatureExtent(rect)

        self.add_toolbar()
        self.add_rect_tool()
        self.pan()

        self.holder.addWidget(self.toolbar)
        self.holder.addWidget(self.canvas)
        self.setLayout(self.holder)

        root.addWidget(self, 0, 1, 1, 2)
        self.root = root

    def set_up_estimate(self):
        '''
        Sets up the Estimate map_layer
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

    def set_up_ground_truth(self):
        '''
        Sets up the ground_truth map_layer
        Args:
        '''
        uri = "Point?crs=epsg:3857"
        layer = QgsVectorLayer(uri, 'Estimate', "memory")
        symbol = QgsMarkerSymbol.createSimple({'name':'square', 'color':'cyan'})
        layer.renderer().setSymbol(symbol)

        return layer

    def set_up_vehicle_layers(self):
        '''
        Sets up the vehicle and vehicle path layers
        Args:
        '''
        uri = "Point?crs=epsg:3857"
        uri_line = "Linestring?crs=epsg:3857"
        vehicle_layer = QgsVectorLayer(uri, 'Vehicle', "memory")
        vehicle_path_layer = QgsVectorLayer(uri_line, 'vehicle_path', "memory")

        # Set drone image for marker symbol
        path = QDir().filePath('resources/vehicleSymbol.svg')
        symbol_svg = QgsSvgMarkerSymbolLayer(path)
        symbol_svg.setSize(4)
        symbol_svg.setFillColor(QColor('#0000ff'))
        symbol_svg.setStrokeColor(QColor('#ff0000'))
        symbol_svg.setStrokeWidth(1)
        vehicle_layer.renderer().symbol().changeSymbolLayer(0, symbol_svg)

        #set autorefresh
        vehicle_layer.setAutoRefreshInterval(500)
        vehicle_layer.setAutoRefreshEnabled(True)
        vehicle_path_layer.setAutoRefreshInterval(500)
        vehicle_path_layer.setAutoRefreshEnabled(True)
        return vehicle_layer, vehicle_path_layer

    def set_up_cone_layer(self):
        uri = "Point?crs=epsg:3857"
        cone_layer = QgsVectorLayer(uri, 'Cone', "memory")
        path = QDir().filePath('resources/searchingTriangle.svg')
        symbol_svg = QgsSvgMarkerSymbolLayer(path)
        symbol_svg.setSize(4)
        symbol_svg.setFillColor(QColor('#ff0000'))
        symbol_svg.setStrokeColor(QColor('#ff0000'))
        #symbol_svg.setStrokeWidth(1)
        symbol_svg.setDataDefinedProperty(QgsSymbolLayer.PropertyFillColor,
                                        QgsProperty.fromField("Color"))
        symbol_svg.setDataDefinedProperty(QgsSymbolLayer.PropertyHeight,
                                        QgsProperty.fromField("Height"))
        symbol_svg.setDataDefinedProperty(QgsSymbolLayer.PropertyVerticalAnchor,
                                        QgsProperty.fromField("VAnchor"))
        cone_layer.renderer().symbol().changeSymbolLayer(0, symbol_svg)
        cone_layer.renderer().symbol().setDataDefinedAngle(
                                        QgsProperty().fromField("Heading"))
        #cone_layer.renderer().symbol().setDataDefinedProperty(QgsProperty().fromField("Opacity"))

        cpr = cone_layer.dataProvider()
        cpr.addAttributes([
                        QgsField(name='Heading', type=QVariant.Double, len=30),
                        QgsField(name="Amp", type=QVariant.Double, len=30),
                        QgsField(name='Color', type=QVariant.String, len=30),
                        QgsField(name="Height", type=QVariant.Double, len=30),
                        QgsField(name="VAnchor", type=QVariant.String, len=30)])
        cone_layer.updateFields()
        cone_layer.setAutoRefreshInterval(500)
        cone_layer.setAutoRefreshEnabled(True)
        return cone_layer

    def set_up_ping_layer(self):
        '''
        Sets up the ping layer and renderer.
        Args:
        '''
        ranges = []
        uri = "Point?crs=epsg:3857"
        layer = QgsVectorLayer(uri, 'Pings', 'memory')

        # make symbols
        symbol_blue = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol_blue.setColor(QColor('#0000FF'))

        symbol_cyan = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol_cyan.setColor(QColor('#00FFFF'))

        symbol_green = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol_green.setColor(QColor('#00FF00'))

        symbol_yellow = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol_yellow.setColor(QColor('#FFFF00'))

        symbol_orange = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol_orange.setColor(QColor('#FFC400'))

        symbol_orange_red = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol_orange_red.setColor(QColor('#FFA000'))

        symbol_red = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol_red.setColor(QColor('#FF0000'))

        # make ranges
        range_blue = QgsRendererRange(0, 10, symbol_blue, 'Blue')
        range_cyan = QgsRendererRange(10, 20, symbol_cyan, 'Cyan')
        range_green = QgsRendererRange(20, 40, symbol_green, 'Green')
        range_yellow = QgsRendererRange(40, 60, symbol_yellow, 'Yellow')
        range_orange = QgsRendererRange(60, 80, symbol_orange, 'Orange')
        range_orange_red = QgsRendererRange(80, 90, symbol_orange_red, 'ORed')
        range_red = QgsRendererRange(90, 100, symbol_red, 'Red')
        ranges.append(range_blue)
        ranges.append(range_cyan)
        ranges.append(range_green)
        ranges.append(range_yellow)
        ranges.append(range_orange)
        ranges.append(range_orange_red)
        ranges.append(range_red)

        # set renderer to set symbol based on amplitude
        ping_renderer = QgsGraduatedSymbolRenderer('Amp', ranges)

        style = QgsStyle.defaultStyle()
        default_color_ramp_names = style.colorRampNames()
        ramp = style.colorRamp(default_color_ramp_names[22])
        ping_renderer.setSourceColorRamp(ramp)
        ping_renderer.setSourceSymbol( QgsSymbol.defaultSymbol(
                                            layer.geometryType()))
        ping_renderer.sortByValue()

        vpr = layer.dataProvider()
        vpr.addAttributes([QgsField(name='Amp', type=QVariant.Double, len=30)])
        layer.updateFields()

        # set the renderer and allow the map_layer to auto refresh
        layer.setRenderer(ping_renderer)
        layer.setAutoRefreshInterval(500)
        layer.setAutoRefreshEnabled(True)

        return layer, ping_renderer

    def set_up_precision_layer(self):
        path = QDir().currentPath()
        uri = 'file:///' + path + \
            '/holder/query.csv?encoding=%s&delimiter=%s&xField=%s&yField=%s&crs=%s&value=%s' \
            % ("UTF-8",",", "easting", "northing","epsg:32611", "value")

        csv_layer= QgsVectorLayer(uri, "query", "delimitedtext")
        csv_layer.setOpacity(0.5)

        heat_map = Qgsheat_mapRenderer()
        heat_map.setWeightExpression('value')
        heat_map.setRadiusUnit(QgsUnitTypes.RenderUnit.RenderMetersInMapUnits)
        heat_map.setRadius(3)
        csv_layer.setRenderer(heat_map)

        csv_layer.setAutoRefreshInterval(500)
        csv_layer.setAutoRefreshEnabled(True)
        return csv_layer

    def set_up_polygon_layer(self):
        uri = "Polygon?crs=epsg:3857"
        polygon_point_layer = QgsVectorLayer(uri, 'Polygon', "memory")
        return polygon_point_layer

    def add_layers(self):
        '''
        Helper method to add map layers to map canvas
        '''
        if self.estimate is None:
            self.estimate = self.set_up_estimate()

        if self.vehicle is None:
            self.vehicle, self.vehicle_path = self.set_up_vehicle_layers()

        if self.ping_layer is None:
            self.ping_layer, self.ping_renderer = self.set_up_ping_layer()

        if self.ground_truth is None:
            self.ground_truth = self.set_up_ground_truth()

        if self.cones is None:
            self.cones = self.set_up_cone_layer()

        if self.polygon_layer is None:
            self.polygon_layer = self.set_up_polygon_layer()

        #load from cached tiles if true, otherwise loads from web
        if self.load_cached:
            path = QDir().currentPath()
            url_with_params = 'type=xyz&url=file:///' + path + \
                '/tiles/%7Bz%7D/%7Bx%7D/%7By%7D.png'
        else:
            url_with_params = 'type=xyz&url=http://a.tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=19&zmin=0&crs=EPSG3857'
        self.map_layer = QgsRasterLayer(url_with_params, 'OpenStreetMap', 'wms')
        '''
        if self.precision is None:
            self.precision = self.set_up_precision_layer()
            dest_crs = self.map_layer.crs()
            raster_crs = self.precision.crs()
            self.precision.setCrs(raster_crs)
            self.canvas.setDestinationCrs(dest_crs)
        '''
        if self.map_layer.isValid():
            crs = self.map_layer.crs()
            crs.createFromString("EPSG:3857")
            self.map_layer.setCrs(crs)

            #add all layers to map
            QgsProject.instance().addMapLayer(self.map_layer)
            QgsProject.instance().addMapLayer(self.ground_truth)
            QgsProject.instance().addMapLayer(self.estimate)
            QgsProject.instance().addMapLayer(self.vehicle)
            QgsProject.instance().addMapLayer(self.vehicle_path)
            QgsProject.instance().addMapLayer(self.ping_layer)
            QgsProject.instance().addMapLayer(self.cones)
            #QgsProject.instance().add_map_layer(self.precision)
            self.__log.info('Valid map_layer')
        else:
            self.__log.error('Invalid map_layer')
            raise RuntimeError('Invalid map_layer')

    def add_rect_tool(self):
        '''
        Helper function to add the rectangle tool to the toolbar
        '''
        self.rect_action = QAction("Rect", self)
        self.rect_action.setCheckable(True)
        self.rect_action.triggered.connect(self.rect)
        self.toolbar.addAction(self.rect_action)
        self.tool_rect = RectangleMapTool(self.canvas)
        self.tool_rect.setAction(self.rect_action)

    def rect(self):
        '''
        Helper function to set rect tool when it is selected from
        the toolbar
        '''
        self.canvas.setMapTool(self.tool_rect)

    def degree_to_tile_num(self, lat_deg, lon_deg, zoom):
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

    def cache_map(self):
        '''
        Function to facilitate caching map tiles
        '''
        if (self.tool_rect.rectangle() == None):
            return
        else:
            rect = self.tool_rect.rectangle()
            r = self.transform.transformBoundingBox(self.tool_rect.rectangle(),
                                QgsCoordinateTransform.ForwardTransform, True)
            print("Rectangle:", r.xMinimum(), r.yMinimum(),
                                r.xMaximum(), r.yMaximum() )
            if (r != None):
                zoom_start = 17
                tile_count = 0
                for zoom in range(zoom_start, 19, 1):
                    x_min, y_min = self.degree_to_tile_num(
                            float(r.yMinimum()), float(r.xMinimum()), zoom)
                    x_max, y_max = self.degree_to_tile_num(
                            float(r.yMaximum()), float(r.xMaximum()), zoom)
                    print("Zoom:", zoom)
                    print(x_min, x_max, y_min, y_max)
                    for x in range(x_min, x_max + 1, 1):
                        for y in range(y_max, y_min + 1, 1):
                            if (tile_count < 200):
                                time.sleep(1)
                                downloaded = self.download_tile(x, y, zoom)
                                if downloaded:
                                    tile_count = tile_count + 1
                            else:
                                print("Tile count exceeded, please try again in a few minutes")
                                return
                print("Download Complete")
            else:
                print("Download Failed")

    def download_tile(self, x_tile, y_tile, zoom):
        '''
        Helper Function to facilitate the downloading of web tiles
        '''
        url = "http://c.tile.openstreetmap.org/%d/%d/%d.png" % \
            (zoom, x_tile, y_tile)
        dir_path = "tiles/%d/%d/" % (zoom, x_tile)
        download_path = "tiles/%d/%d/%d.png" % (zoom, x_tile, y_tile)

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

        self.file_name = None
        self.__get_file_name()

        self.__add_layers()
        self.adjust_canvas()
        self.add_toolbar()
        self.pan()

        self.holder.addWidget(self.toolbar)
        self.holder.addWidget(self.canvas)
        self.setLayout(self.holder)

        root.addWidget(self, 0, 1, 1, 2)
        self.root = root

    def __get_file_name(self):
        '''
        inner function to retrieve a user specified raster file
        '''
        self.file_name = QFileDialog.getOpenFileName()

    def __add_layers(self):
        '''
        Helper funciton to add layers to the map canvas
        '''
        if(self.file_name == None):
            return

        self.map_layer = QgsRasterLayer(self.file_name[0], "SRTM layer name")
        if not self.map_layer.crs().isValid():
            raise FileNotFoundError("Invalid file, loading from web...")
        print(self.map_layer.crs())

        if self.estimate is None:
            uri = "Point?crs=epsg:4326"
            self.estimate = QgsVectorLayer(uri, 'Estimate', "memory")

            symbol = QgsMarkerSymbol.createSimple({'name': 'diamond',
                                                    'color': 'blue'})
            self.estimate.renderer().setSymbol(symbol)

            self.estimate.setAutoRefreshInterval(500)
            self.estimate.setAutoRefreshEnabled(True)

        if self.vehicle is None:
            uri = "Point?crs=epsg:4326"
            uri_line = "Linestring?crs=epsg:4326"

            self.vehicle = QgsVectorLayer(uri, 'Vehicle', "memory")
            self.vehicle_path = QgsVectorLayer(uri_line, 'vehicle_path', "memory")

            # Set drone image for marker symbol
            path = QDir().currentPath()
            full = path +'/camera.svg'
            symbol_svg = QgsSvgMarkerSymbolLayer(full)
            symbol_svg.setSize(4)
            symbol_svg.setFillColor(QColor('#0000ff'))
            symbol_svg.setStrokeColor(QColor('#ff0000'))
            symbol_svg.setStrokeWidth(1)

            self.vehicle.renderer().symbol().changeSymbolLayer(0, symbol_svg )
            #set autorefresh
            self.vehicle.setAutoRefreshInterval(500)
            self.vehicle.setAutoRefreshEnabled(True)
            self.vehicle_path.setAutoRefreshInterval(500)
            self.vehicle_path.setAutoRefreshEnabled(True)

        if self.ping_layer is None:
            ranges = []
            uri = "Point?crs=epsg:4326"
            self.ping_layer = QgsVectorLayer(uri, 'Pings', 'memory')

            # make symbols
            symbol_blue = QgsSymbol.defaultSymbol(
                    self.ping_layer.geometryType())
            symbol_blue.setColor(QColor('#0000FF'))
            symbol_green = QgsSymbol.defaultSymbol(
                    self.ping_layer.geometryType())
            symbol_green.setColor(QColor('#00FF00'))
            symbol_yellow = QgsSymbol.defaultSymbol(
                    self.ping_layer.geometryType())
            symbol_yellow.setColor(QColor('#FFFF00'))
            symbol_orange = QgsSymbol.defaultSymbol(
                    self.ping_layer.geometryType())
            symbol_orange.setColor(QColor('#FFA500'))
            symbol_red = QgsSymbol.defaultSymbol(
                    self.ping_layer.geometryType())
            symbol_red.setColor(QColor('#FF0000'))

            # make ranges
            range_blue = QgsRendererRange(0, 20, symbol_blue, 'Blue')
            range_green = QgsRendererRange(20, 40, symbol_green, 'Green')
            range_yellow = QgsRendererRange(40, 60, symbol_yellow, 'Yellow')
            range_orange = QgsRendererRange(60, 80, symbol_orange, 'Orange')
            range_red = QgsRendererRange(80, 100, symbol_red, 'Red')

            ranges.append(range_blue)
            ranges.append(range_green)
            ranges.append(range_yellow)
            ranges.append(range_orange)
            ranges.append(range_red)

            # set renderer to set symbol based on amplitude
            self.ping_renderer = QgsGraduatedSymbolRenderer('Amp', ranges)
            my_classification_method = QgsApplication.classificationMethodRegistry().method("EqualInterval")
            self.ping_renderer.setClassificationMethod(my_classification_method)
            self.ping_renderer.setClassAttribute('Amp')
            vpr = self.ping_layer.dataProvider()
            vpr.addAttributes([QgsField(name='Amp', type=QVariant.Double, len=30)])
            self.ping_layer.updateFields()

            # set the renderer and allow the layerayer to auto refresh
            self.ping_layer.setRenderer(self.ping_renderer)
            self.ping_layer.setAutoRefreshInterval(500)
            self.ping_layer.setAutoRefreshEnabled(True)

        if self.map_layer.isValid():
            QgsProject.instance().add_map_layer(self.map_layer)
            QgsProject.instance().add_map_layer(self.estimate)
            QgsProject.instance().add_map_layer(self.vehicle)
            QgsProject.instance().add_map_layer(self.vehicle_path)
            QgsProject.instance().add_map_layer(self.ping_layer)
            print('valid layer')
        else:
            print('invalid layer')
