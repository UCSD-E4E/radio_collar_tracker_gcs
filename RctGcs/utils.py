'''RctGcs Utilities
'''
import os
import sys
from pathlib import Path


def fix_conda_path():
    """Fixes conda path at runtime
    """
    if 'CONDA_PREFIX' in os.environ:
        plugins_path = Path(sys.executable).parent.joinpath("Library", "python", "plugins")
        python_lib = Path(sys.executable).parent.joinpath("Library", "python")
        sys.path.insert(0, plugins_path.as_posix())
        sys.path.insert(0, python_lib.as_posix())
