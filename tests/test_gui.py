'''GUI Tests
'''
import pyautogui
import RctGcs.rctGCS
from threading import Thread
from time import sleep

def test_close():
    gui_thread = Thread(target=RctGcs.rctGCS.main, name='dut')
    gui_thread.start()
    sleep(1)
    pyautogui.hotkey('Win', 'up')
    pyautogui.hotkey('alt', 'f4')
    gui_thread.join()