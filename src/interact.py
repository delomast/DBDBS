# Main interaction window

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
	QApplication, QMainWindow, QPushButton, QLabel, QLineEdit, QComboBox, 
	 QGridLayout, QWidget, QCheckBox
)
import os
import sys
import mysql.connector as connector
import sqlite3
from .login import loginDialog
from .utils import dlgError, saveInfo
from . import PACKAGEDIR


class interactWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("DBDBS")
		# repeatedly get login information until connected
		self.cnx = None
		while True:
			login = loginDialog()
			login.accepted.connect(self.dbConnect)
			login.rejected.connect(sys.exit)
			login.exec()
			if self.cnx is not None:
				break

		# define widgets


		# position widgets in a layout
		layout = QGridLayout()

		# adding labels
		labelText = ["Host address", "Username", "Password", "Database name", "Save info", "you are connected"]
		for i in range(0, len(labelText)):
			layout.addWidget(QLabel(labelText[i]), i, 0)

		# set the central widget of the Window
		widget = QWidget()
		widget.setLayout(layout)
		self.setCentralWidget(widget)

	def dbConnect(self, userInfo):
		# try to connect to database
		try:
			self.cnx = connector.connect(user=userInfo["un"], password=userInfo["pw"], 
								host=userInfo["host"], database=userInfo["db"])
		except Exception as e:
			dlgError(parent=self, message="Failed to connect to MySQL database")
			# raise e
		# if login was successful, save information if requested
		if self.cnx is not None and userInfo["save"]:
			saveInfo(userInfo=userInfo)
	

