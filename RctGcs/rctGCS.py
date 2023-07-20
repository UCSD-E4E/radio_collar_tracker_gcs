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
# 02/18/21  ML  Refactored layer functions in map classes
# 02/11/21  ML  pruned imports
# 02/11/21  ML  Added heatmap display for live precision visualization
# 01/26/22  ML  Pruned experimental code/displays, removed all panda UI overlap
# 10/21/20  ML  Removed testing components
# 08/19/20  ML  Added config object to gcs, added appDirs for tiles output
# 08/14/20  ML  Removed excel sheet outputs
# 08/11/20  ML  Added export settings, pings, and vehicle path as json file
# 08/06/20  NH  Refactored map loading code for ease of debugging
# 07/31/20  ML  Added ability to export pings and vehicle paths as Shapefile
# 07/17/20  ML  Translated component status and upgrade displays into PyQt and
#               fixed CollapseFrame nesting issue
# 07/14/20  ML  Added ability to cache and load offline maps
# 07/09/20  ML  Refactored Map Classes to extend added MapWidget Class
# 07/09/20  ML  Converted Static Maps and WebMaps to QGIS
# 06/30/20  ML  Translated tkinter GUI into PyQt5
# 06/25/20  AG  Added more dictionaries to component status display.
# 06/19/20  AG  Added component status display and sub-display.
# 06/17/20  ML  Implemented ability to load webmap from OSM based on coordinates
# 05/29/20  ML  refactored MapControl 
# 05/25/20  NH  Fixed validate frequency call
# 05/24/20  ML  Implemented ability to load map, refactored map functions
# 05/24/20  AG  Added error messages during target frequency validation.
# 05/20/20  NH  Fixed window close action, added function to handle registering
#                 callbacks when connection established, removed unused
#                 callbacks, added advanced settings dialog, fixed logging
# 05/19/20  NH  Removed PIL, rasterio, refactored options, connectionDialog,
#                 AddTargetDialog, SystemSettingsControl, fixed exit behavior,
# 05/18/20  NH  Updated API for core
# 05/17/20  AG  Finished implementing start/stop recording button
# 05/17/20  AG  Added setting target frequencies and system connection text updates.
# 05/13/20  AG  Added ability to set and receive expert debug options
# 05/09/20  ML  Added ability to add/clear target frequencies
# 05/05/20  AG  Tied options entries to string vars
# 05/03/20  ML  Added Expert Settings popup, Added the ability to load TIFF img
# 05/03/20  AG  Added TCP connection and update options functionalities
# 04/26/20  NH  Updated API, switched from UDP to TCP
# 04/20/20  NH  Updated API and imports
# 04/17/20  NH  Updated imports and MAVModel API
# 02/15/20  NH  Initial commit
#
###############################################################################
import datetime as dt
import logging
import os
import os.path
import sys
from pathlib import Path

from PyQt5.QtWidgets import QFileDialog

from RctGcs.config import (application_directories, get_config_path,
                           get_instance)
from RctGcs.ui.display import GCS
from RctGcs.ui.popups import UserPopups
from RctGcs.utils import fix_conda_path

fix_conda_path()
from qgis.core import *
from qgis.gui import *
from qgis.utils import *


def configSetup() -> Path:
    '''
    Helper function to set up paths to QGIS lbrary files, and 
    config file
    '''    
    gcs_config_path = get_config_path()
    with get_instance(gcs_config_path) as config:
        if not config.qgis_prefix_set:
            qgis_path = Path(QFileDialog.getExistingDirectory(None, 'Select the Qgis directory', config.qgis_prefix_path.as_posix()))
            if 'qgis' not in qgis_path.as_posix():
                user_pops = UserPopups()
                user_pops.show_warning("Warning, incorrect file chosen. Map tools may not function as expected")
            config.qgis_prefix_path = qgis_path
            config.qgis_prefix_set = True
            return qgis_path
        else:
            return config.qgis_prefix_path


def main():
    start_timestamp = dt.datetime.now()
    log_file = start_timestamp.strftime('%Y.%m.%d.%H.%M.%S_gcs.log')
    log_file = '0gcs.log'
    log_path = Path(application_directories.user_log_dir, log_file)
    log_path.parent.mkdir(exist_ok=True, parents=True)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d: %(levelname)s:%(name)s: %(message)s', 
        datefmt='%Y-%M-%d %H:%m:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    ch = logging.FileHandler(log_path)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)


    app = QgsApplication([], True)

    prefix_path = configSetup()

    QgsApplication.setPrefixPath(str(prefix_path), True)

    app.initQgis()

    ex = GCS()
    ex.show()

    app.exec_()
    app.exitQgis()

if __name__ == '__main__':
    main()
