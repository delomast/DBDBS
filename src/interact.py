# Main interaction window

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
	QMainWindow, QPushButton, QLabel, QLineEdit, QComboBox, 
	 QGridLayout, QWidget, QCheckBox, QToolBar, QInputDialog,
	 QFileDialog
)
import os
import sys
import mysql.connector as connector
import sqlite3
from .login import loginDialog
from .utils import dlgError, saveInfo, identifier_syntax_check, getConnection
from . import PACKAGEDIR
from .newPanelWindow import newPanelWindow


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
		# switch databases action
		switchDB_button = QAction("Switch databases", self)
		switchDB_button.setStatusTip("This switches to a different database on the connected server")
		switchDB_button.triggered.connect(self.switchDB)
		# add a new genotyping panel
		makePanel_button = QAction("Add a new genotyping panel", self)
		makePanel_button.setStatusTip("This creates a new genotype panel in the current database")
		makePanel_button.triggered.connect(self.makePanel)
		
		actionMenu.addActions([makeDB_button, switchDB_button, makePanel_button])

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
		# TODO: add buttons for import and export functions here
		# TODO: add define new tables here?
		widget = QWidget()
		widget.setLayout(layout)
		self.setCentralWidget(widget)

	def dbConnect(self, userInfo):
		# try to connect to database
		try:
			self.cnx = getConnection(userInfo)
		except Exception as e:
			dlgError(parent = self, message="Failed to connect to MySQL database")
			# raise e
		# if login was successful, store connection information, save if requested
		if hasattr(self, "cnx"):
			self.userInfo = userInfo
			if userInfo["save"]:
				saveInfo(userInfo=userInfo)
	
	def makeNewDB(self, s = None):
		# get database name
		dbName = QInputDialog.getText(self, "Make new database", "Database name:")
		# make and switch to that database
		if dbName[1]:
			self.create_new_db(dbName[0])

	def switchDB(self, dbName = None):
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
		self.userInfo["db"] = dbName
		self.dbLabel.setText(self.cnx.database)
	
	# create a new database
	# newDB: name of the new database
	def create_new_db(self, newDB : str) -> int:
		if not identifier_syntax_check(newDB):
			dlgError(parent=self, message="Database name has invalid syntax")
			return
		
		with self.cnx.cursor() as curs:
			curs.execute("SHOW DATABASES")
			db_exists = False
			for x in curs:
				if x[0] == newDB:
					db_exists = True
					self.cnx.consume_results()
					break
			if db_exists:
				dlgError(parent = self, message="A database with that name already exists on this server. Switching to it.")
				self.switchDB(dbName = newDB)
				return
			# make database on MySQL server
			curs.execute("CREATE DATABASE `%s`" % newDB)
		
		# switch to the new database
		self.switchDB(dbName = newDB)

		# create information tables and pedigree table
		with self.cnx.cursor() as curs:
			with open(os.path.join(PACKAGEDIR, "sql/create_database.sql"), mode="r", encoding = "utf-8") as f:
				for res in curs.execute(f.read(), multi = True):
					pass # have to iterate through to execute all statements
		return

	# define a table for a new genotype panel
	def makePanel(self, s = None):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		# open the add a new panel window
		self.npWindow = newPanelWindow(userInfo = self.userInfo)
		self.npWindow.show()

	# close the whole application when the main window closes
	# prevents other windows remaining open when the main window is closed
	def closeEvent(self, event):
		sys.exit()
