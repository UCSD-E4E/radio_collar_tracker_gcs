'''Tests that the environment is sane
'''
import os
import sys
from pathlib import Path

from RctGcs.config import get_config_path, get_instance

if 'CONDA_PREFIX' in os.environ:
    sys.path.insert(0, Path(sys.executable).parent.joinpath("Library", "python", "plugins").as_posix())
    sys.path.insert(0, Path(sys.executable).parent.joinpath("Library", "python").as_posix())
from qgis.core import QgsApplication, QgsStyle


def test_configuration():
    default_styles = QgsStyle.defaultStyle()
    assert len(default_styles.colorRampNames()) > 0
