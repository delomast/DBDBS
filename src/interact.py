# Main interaction window

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
	QApplication, QMainWindow, QPushButton, QLabel, QLineEdit, QComboBox, 
	 QGridLayout, QWidget, QCheckBox, QToolBar, QInputDialog
)
import os
import sys
import mysql.connector as connector
import sqlite3
from .login import loginDialog
from .utils import dlgError, saveInfo, identifier_syntax_check, create_new_db
from . import PACKAGEDIR


class interactWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("DBDBS")

		# define menu for rare actions
		menu = self.menuBar()
		actionMenu = menu.addMenu("Actions")

		# make a new database action
		makeDB_button = QAction("Make new database", self)
		makeDB_button.setStatusTip("This creates a new database on the connected server")
		makeDB_button.triggered.connect(self.makeNewDB)
		switchDB_button = QAction("Switch databases", self)
		switchDB_button.setStatusTip("This switches to a different database on the connected server")
		switchDB_button.triggered.connect(self.switchDB)
		
		actionMenu.addActions([makeDB_button, switchDB_button])

		# repeatedly get login information until connected
		# or user closes login dialog box (closes application)
		while True:
			login = loginDialog()
			login.accepted.connect(self.dbConnect)
			login.rejected.connect(sys.exit)
			login.exec()
			if hasattr(self, "cnx"):
				break

		# define widgets
		importButton = QPushButton("Import data")
		exportButton = QPushButton("Export data")



		# Information displayed about the connection
		cnxInfoLayout = QGridLayout()
		# adding labels
		labelText = ["Host address", "Username"]
		labelValues = [self.cnx.server_host, self.cnx.user]
		for i in range(0, len(labelText)):
			cnxInfoLayout.addWidget(QLabel(labelText[i]), i, 0)
			cnxInfoLayout.addWidget(QLabel(labelValues[i]), i, 1)
		cnxInfoLayout.addWidget(QLabel("Database name"), 2, 0)
		# saving as attribute to allow later changing
		self.dbLabel = QLabel(self.cnx.database)
		cnxInfoLayout.addWidget(self.dbLabel, 2, 1)
		cnxInfoWidget = QWidget()
		cnxInfoWidget.setLayout(cnxInfoLayout)

		# set up the layout of the Window
		layout = QGridLayout()
		layout.addWidget(cnxInfoWidget, 0, 0) # info in top left
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
		if hasattr(self, "cnx") and userInfo["save"]:
			saveInfo(userInfo=userInfo)
	
	def makeNewDB(self, s = None):
		# get database name
		dbName = QInputDialog.getText(self, "Make new database", "Database name:")
		# make and switch to that database
		if dbName[1]:
			if not identifier_syntax_check(dbName[0]):
				dlgError(message="Invalid syntax, database not created.")
			else:
				retStatus = create_new_db(self.cnx, dbName[0])
				if retStatus == 1:
					dlgError(message="A database with that name already exists on this server. Switching to it.")
				self.switchDB(dbName=dbName[0])
		self.dbLabel.setText(self.cnx.database)
	
	def switchDB(self, s = None, dbName = None):
		if dbName is None:
			# list all databases on server
			# NOTE: this will later be updated to only list dbdbs databases
			with self.cnx.cursor() as curs:
				curs.execute("SHOW DATABASES")
				dbAvail = [x[0] for x in curs]
			dbName = QInputDialog.getItem(self, "Choose database", "Database name:", dbAvail, editable=False)
			if dbName[1]:
				dbName = dbName[0]
			else:
				return
		with self.cnx.cursor() as curs:
			curs.execute("USE `%s`" % dbName)
		self.dbLabel.setText(self.cnx.database)
