'''GUI Test Support
'''
from PyQt5.QtWidgets import QApplication

from pytest import fixture

@fixture(name='bare_gui')
def create_bare_app() -> QApplication:
    """Creates a bare Qt Application for dialog testing

    Returns:
        QApplication: Empty application
    """
    app = QApplication([])
    return app
