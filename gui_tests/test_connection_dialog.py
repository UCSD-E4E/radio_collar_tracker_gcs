'''This set of tests are used to evaluate the Connection Dialog
'''

from threading import Thread
from time import sleep

from RctGcs.ui.popups import ConnectionDialog, ConnectionMode
from PyQt5.QtCore import Qt

def test_load(bare_gui):
    spec = 'serial:COM1?baud=9600'
    dialog = ConnectionDialog(transport_spec=None)
    dialog.exec_()
