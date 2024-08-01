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
from .utils import dlgError, saveInfo, identifier_syntax_check, getConnection, removePartialPanel
from . import PACKAGEDIR
from .newPanelWindow import newPanelWindow
from .importGenoWindow import importGenoWindow


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
		# remove an empty genotyping panel
		removeEmptyPanel_button = QAction("Remove an empty genotype panel", self)
		removeEmptyPanel_button.setStatusTip("This can remove a genotype panel that does not have any genotypes in it")
		removeEmptyPanel_button.triggered.connect(self.removeEmptyPanel)
		
		actionMenu.addActions([makeDB_button, switchDB_button, makePanel_button, removeEmptyPanel_button])

		# define widgets
		loginToServerButton = QPushButton("Login to server") # login button
		loginToServerButton.clicked.connect(self.login)
		importGenoButton = QPushButton("Import genotype data")
		importGenoButton.clicked.connect(self.importGeno)
		exportButton = QPushButton("Export data")



		# Information displayed about the connection
		self.cnxInfoLayout = QGridLayout()
		# adding labels
		labelText = ["Host address", "Username", "Database name"]
		# saving as connection info labels as attribute to allow later changing
		self.labelValues = []
		for i in range(0, len(labelText)):
			self.labelValues += [QLabel("")]
			self.cnxInfoLayout.addWidget(QLabel(labelText[i]), i, 0)
			self.cnxInfoLayout.addWidget(self.labelValues[i], i, 1)

		cnxInfoWidget = QWidget()
		cnxInfoWidget.setLayout(self.cnxInfoLayout)

		# set up the layout of the Window
		layout = QGridLayout()
		layout.addWidget(cnxInfoWidget, 0, 0) # info in top left
		layout.addWidget(loginToServerButton, 1, 0)
		layout.addWidget(importGenoButton, 2, 0)
		# TODO: add buttons for import and export functions here
		# TODO: add define new tables here?
		widget = QWidget()
		widget.setLayout(layout)
		self.setCentralWidget(widget)

	def login(self):
		login = loginDialog()
		login.accepted.connect(self.dbConnect)
		login.exec()

	def dbConnect(self, userInfo : dict):
		# try to connect to database
		try:
			self.cnx = getConnection(userInfo)
		except Exception as e:
			dlgError(parent = self, message = "Failed to connect to MySQL database")
			return
			# raise e
		
		# update labels
		tempVal = [self.cnx.server_host, self.cnx.user, self.cnx.database]
		for i in range(0, len(self.labelValues)):
			self.labelValues[i].setText(tempVal[i])
		
		# store connection information for session
		self.userInfo = userInfo
		# save for later sessions if requested
		if userInfo["save"]:
			saveInfo(userInfo = userInfo)
	
	def makeNewDB(self, s = None):
		if not hasattr(self, "cnx"):
			dlgError(parent = self, message = "Error, not connected to a server")
			return
		# get database name
		dbName = QInputDialog.getText(self, "Make new database", "Database name:")
		# make and switch to that database
		if dbName[1]:
			self.create_new_db(dbName[0])

	def switchDB(self, s = None, dbName = None):
		if not hasattr(self, "cnx"):
			dlgError(parent = self, message="Error, not connected to a server")
			return
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
			# test if database is a DBDBS database
			curs.execute("SHOW TABLES FROM `%s` LIKE 'intDBpedigree'" % dbName)
			if next(curs, [None])[0] is None:
				dlgError(parent = self, message = "The selected database is not a DBDBS database.")
				return
			# switch
			curs.execute("USE `%s`" % dbName)
		self.userInfo["db"] = self.cnx.database
		self.labelValues[2].setText(self.cnx.database)
	
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
			curs.execute("USE `%s`" % newDB)

			# create information tables and pedigree table
			with open(os.path.join(PACKAGEDIR, "sql/create_database.sql"), mode="r", encoding = "utf-8") as f:
				for res in curs.execute(f.read(), multi = True):
					pass # have to iterate through to execute all statements
		
		# update values
		self.userInfo["db"] = self.cnx.database
		self.labelValues[2].setText(self.cnx.database)	

	# open window to define a new genotype panel
	def makePanel(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		# open the add a new panel window
		self.npWindow = newPanelWindow(cnx = self.cnx, userInfo = self.userInfo)
		self.npWindow.exec()
	
	# remove a partial or full panel with no genotypes, if it exists
	def removeEmptyPanel(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		panel = QInputDialog.getText(self, "Remove an empty panel", "Panel name:")
		if panel[1] and panel[0] != "":
			panel = panel[0]
		else:
			return
		removePartialPanel(self.userInfo, panel)

	# open import genotypes window
	def importGeno(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		self.igWindow = importGenoWindow(cnx = self.cnx, userInfo = self.userInfo)
		self.igWindow.exec()
	
