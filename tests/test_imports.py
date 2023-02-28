'''Tests that all packages can be imported
'''
import importlib


def test_imports():
    """Test imports
    """
    importlib.import_module('PyQt5')
    importlib.import_module('PyQt5.QtWidgets')
    importlib.import_module('PyQt5.QtCore')
    importlib.import_module('PyQt5.QtGui')
    importlib.import_module('qgis')
    importlib.import_module('qgis.core')
    importlib.import_module('qgis.gui')
    importlib.import_module('qgis.utils')
    importlib.import_module('utm')
    importlib.import_module('appdirs')
    importlib.import_module('numpy')
