# Login window

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
	QApplication, QMainWindow, QPushButton, QLabel, QLineEdit, QComboBox, 
	 QGridLayout, QWidget, QCheckBox, QDialog
)
from .utils import dlgError

# main window
class loginDialog(QDialog):
	accepted = pyqtSignal(dict)
	def __init__(self):
		super().__init__()
		self.setWindowTitle("DBDBS")

		# define widgets
		self.hostBox = QComboBox() # host address
		self.hostBox.setEditable(True)
		self.userBox = QComboBox() # user name
		self.userBox.setEditable(True)
		self.dbBox = QComboBox() # database name
		self.dbBox.setEditable(True)

		self.pwBox = QLineEdit()
		self.pwBox.setEchoMode(QLineEdit.EchoMode.Password)

		self.saveInfo = QCheckBox()
		self.saveInfo.setCheckState(Qt.CheckState.Checked)

		self.button = QPushButton("Connect")
		self.button.clicked.connect(self.onClick)

		

		# position widgets in a layout
		layout = QGridLayout()
		layout.addWidget(self.hostBox, 0, 1)
		layout.addWidget(self.userBox, 1, 1)
		layout.addWidget(self.pwBox, 2, 1)
		layout.addWidget(self.dbBox, 3, 1)
		layout.addWidget(self.saveInfo, 4, 1)
		layout.addWidget(self.button, 4, 2)
		# adding labels
		labelText = ["Host address", "Username", "Password", "Database name", "Save info"]
		for i in range(0, len(labelText)):
			layout.addWidget(QLabel(labelText[i]), i, 0)

		# set the central widget of the Window
		self.setLayout(layout)

	def onClick(self):
		self.accepted.emit({"host" : self.hostBox.currentText(),
					  "un" : self.userBox.currentText(),
					  "pw" : self.pwBox.text(),
					  "db" : self.dbBox.currentText(),
					  "save" : self.saveInfo.isChecked()})
		self.accept()
	
	def closeEvent(self, event):
		self.reject()
		