'''Tests that the environment is sane
'''
import os
import sys
from pathlib import Path

if 'CONDA_PREFIX' in os.environ:
    sys.path.insert(0, Path(sys.executable).parent.joinpath("Library", "python", "plugins").as_posix())
    sys.path.insert(0, Path(sys.executable).parent.joinpath("Library", "python").as_posix())
from qgis.core import QgsApplication, QgsStyle

# from scripts.config import get_instance


# def test_configuration():
#     with get_instance(Path('gcsConfig.ini')) as config:
#         prefix_path = config.qgis_prefix_path
#     QgsApplication.setPrefixPath(str(prefix_path), True)
#     default_styles = QgsStyle.defaultStyle()
#     assert len(default_styles.colorRampNames()) > 0
