# Login window

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QLineEdit, QComboBox, 
	 QGridLayout, QCheckBox, QDialog
)
import os
import sqlite3
from . import PACKAGEDIR

# main window
class loginDialog(QDialog):
	accepted = pyqtSignal(dict)
	def __init__(self):
		super().__init__()
		self.setWindowTitle("DBDBS")

		# check if gui database exists and open
		db_exists = os.path.exists(os.path.join(PACKAGEDIR, "interface_db/dbdbs.sqlite"))
		if db_exists:
			self.gui_db = sqlite3.connect(os.path.join(PACKAGEDIR, "interface_db/dbdbs.sqlite"),
						detect_types=sqlite3.PARSE_DECLTYPES)

		# define widgets
		self.hostBox = QComboBox() # host address
		self.hostBox.setEditable(True)
		self.userBox = QComboBox() # user name
		self.userBox.setEditable(True)
		self.dbBox = QComboBox() # database name
		self.dbBox.setEditable(True)
		# pull saved values for comboboxes
		if db_exists:
			self.hostBox.addItems([x[0] for x in self.gui_db.execute("SELECT host FROM server_info")])
			self.updateComboBoxes()
			self.hostBox.currentTextChanged.connect(self.updateComboBoxes)

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
	
	def updateComboBoxes(self):
		curs_host = self.gui_db.execute("SELECT host_id FROM server_info WHERE host = ?", (self.hostBox.currentText(),))
		select_host_id = next(curs_host, [""])[0]
		curs_host.close()
		self.userBox.clear()
		self.userBox.addItems([x[0] for x in self.gui_db.execute("SELECT user_name FROM user_info WHERE host_id = ?", (select_host_id,))])
		self.dbBox.clear()
		self.dbBox.addItems([x[0] for x in self.gui_db.execute("SELECT db_name FROM db_info WHERE host_id = ?", (select_host_id,))])
