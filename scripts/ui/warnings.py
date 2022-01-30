from PyQt5.QtWidgets import QMessageBox

class WarningMessager:
    
    def showWarning(text: str, title: str ="Warning"):
        '''
        Creates warning popups
        Args: 
            title: message header
            text: message body
        '''
        msg = QMessageBox()
        msg.setText(title)
        msg.setWindowTitle("Alert")
        msg.setInformativeText(text)
        msg.setIcon(QMessageBox.Critical)
        msg.addButton(QMessageBox.Ok)
        msg.exec_()