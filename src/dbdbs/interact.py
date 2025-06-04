# Main interaction window

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
	QMainWindow, QPushButton, QLabel, 
	 QGridLayout, QWidget, QInputDialog,
	 QFileDialog, QMessageBox
)
import os
import subprocess
import shutil
import mysql.connector as connector
from .login import loginDialog
from .utils import dlgError, saveInfo, identifier_syntax_check, getConnection, removePartialPanel, removePartialPhenoTable
from . import PACKAGEDIR
from .newPanelWindow import newPanelWindow
from .importGenoWindow import importGenoWindow
from .exportGenoWindow import exportGenoWindow
from .pedWindow import pedWindow
from .newPhenoTableWindow import newPhenoTableWindow
from .importPhenoWindow import importPhenoWindow
from .exportPhenoWindow import exportPhenoWindow
from .deleteDataWindow import deleteDataWindow


class interactWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("DBDBS")

		self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
		self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
		self.setMinimumSize(500, 400) # trying to avoid :"Unable to set geometry" warning

		# define menu for rare actions
		menu = self.menuBar()
		actionMenu = menu.addMenu("Actions")
		backupMenu = menu.addMenu("Backups")

		# make a new database action
		makeDB_button = QAction("Make new database", self)
		makeDB_button.setStatusTip("This creates a new database on the connected server")
		makeDB_button.triggered.connect(self.makeNewDB)
		# switch databases action
		switchDB_button = QAction("Switch databases", self)
		switchDB_button.setStatusTip("This switches to a different database on the connected server")
		switchDB_button.triggered.connect(self.switchDB)
		# add a new genotyping panel
		makePanel_button = QAction("Add a new genotype panel", self)
		makePanel_button.setStatusTip("This creates a new genotype panel in the current database")
		makePanel_button.triggered.connect(self.makePanel)
		# remove an empty genotyping panel
		removeEmptyPanel_button = QAction("Remove an empty genotype panel", self)
		removeEmptyPanel_button.setStatusTip("This can remove a genotype panel that does not have any genotypes in it")
		removeEmptyPanel_button.triggered.connect(self.removeEmptyPanel)
		# add a new phenotype table
		makePhenoTable_button = QAction("Add a new phenotype table", self)
		makePhenoTable_button.setStatusTip("This creates a new phenotype table in the current database")
		makePhenoTable_button.triggered.connect(self.makePhenoTable)
		# remove an empty phenotype table
		removeEmptyPhenoTable_button = QAction("Remove an empty phenotype table", self)
		removeEmptyPhenoTable_button.setStatusTip("This can remove a phenotype table that does not have any phenotypes in it")
		removeEmptyPhenoTable_button.triggered.connect(self.removeEmptyPhenoTable)

		# create a backup file with mysqldump
		createBackupdump_button = QAction("Create a database backup file - mysqldump", self)
		createBackupdump_button.setStatusTip("This uses a local copy of the mysqldump program to create a backup file")
		createBackupdump_button.triggered.connect(self.createBackupMysqldump)
		# load a mysqldump backup file
		useBackupdump_button = QAction("Create a new database from a mysqldump SQL backup file", self)
		useBackupdump_button.setStatusTip("This uses a backup file created by mysqldump to create a new database")
		useBackupdump_button.triggered.connect(self.useBackupMysqldump)
		# create a backup file with mysqlsh
		createBackupsh_button = QAction("Create a database backup file - mysqlsh", self)
		createBackupsh_button.setStatusTip("This uses a local copy of the mysqlsh program to create a backup file")
		createBackupsh_button.triggered.connect(self.createBackupMysqlsh)
		# load a mysqlsh backup file
		useBackupsh_button = QAction("Restore a database from a mysqlsh backup folder", self)
		useBackupsh_button.setStatusTip("This uses a backup folder created by mysqlsh to create a new database")
		useBackupsh_button.triggered.connect(self.useBackupMysqlsh)
		
		actionMenu.addActions([makeDB_button, switchDB_button, makePanel_button, removeEmptyPanel_button, makePhenoTable_button, removeEmptyPhenoTable_button])
		backupMenu.addActions([createBackupdump_button, useBackupdump_button, createBackupsh_button, useBackupsh_button])

		# define widgets
		loginToServerButton = QPushButton("Login to server") # login button
		loginToServerButton.clicked.connect(self.login)
		importGenoButton = QPushButton("Import genotype data")
		importGenoButton.clicked.connect(self.importGeno)
		exportGenoButton = QPushButton("Export genotype data")
		exportGenoButton.clicked.connect(self.exportGeno)
		importExportPedButton = QPushButton("Import or export pedigree")
		importExportPedButton.clicked.connect(self.importExportPed)
		importPhenoButton = QPushButton("Import phenotype data")
		importPhenoButton.clicked.connect(self.importPheno)
		exportPhenoButton = QPushButton("Export phenotype data")
		exportPhenoButton.clicked.connect(self.exportPheno)
		deleteDataButton = QPushButton("Delete data")
		deleteDataButton.clicked.connect(self.deleteData)

		# TODO documentation
		# TODO table info screen/export
		# TODO genotype info screen/export
		# TODO pedigree export options
		#  current is selected inds and all ancestors
		#  add 1)just selected inds
		#  2) selected inds and descendents
		#  3) selected inds and all relatives (ancestors and descendents)
		# TODO multi and hyper genotype export as codes and translation list
		# TODO plink binary input and output 


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
		layout.addWidget(exportGenoButton, 3, 0)
		layout.addWidget(importExportPedButton, 4, 0)
		layout.addWidget(importPhenoButton, 5, 0)
		layout.addWidget(exportPhenoButton, 6, 0)
		layout.addWidget(deleteDataButton, 1, 1)
		# make columns equally sized when sufficient space is available
		for i in range(0,layout.columnCount()):
			layout.setColumnStretch(i, 1)
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
			with self.cnx.cursor() as curs:
				curs.execute("SELECT TABLE_SCHEMA FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'intdbpedigree'")
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
	def create_new_db(self, newDB : str):
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
		self.cnx.commit()
		
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
	
	# open window to define a new phenotype panel
	def makePhenoTable(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		# open the add a new panel window
		self.nptWindow = newPhenoTableWindow(cnx = self.cnx, userInfo = self.userInfo)
		self.nptWindow.exec()

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
		retVal = removePartialPanel(self.userInfo, panel)
		if retVal == 1:
			dlgError(parent=self, message="Panel contains genotypes. Panel was NOT removed.")
		elif retVal == 0:
			msgBox = QMessageBox(parent=self)
			msgBox.setWindowTitle("Panel removed")
			msgBox.setText("If it existed, panel was successfully removed")
			msgBox.exec()
	
	# remove a partial or full phenotype table with no phenotypes, if it exists
	def removeEmptyPhenoTable(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		table = QInputDialog.getText(self, "Remove an empty phenotype table", "Table name:")
		if table[1] and table[0] != "":
			table = table[0]
		else:
			return
		retVal = removePartialPhenoTable(self.userInfo, table)
		if retVal == 1:
			dlgError(parent=self, message="Table contains phenotypes. Table was NOT removed.")
		elif retVal == 0:
			msgBox = QMessageBox(parent=self)
			msgBox.setWindowTitle("Table removed")
			msgBox.setText("If it existed, table was successfully removed")
			msgBox.exec()

	# open import genotypes window
	def importGeno(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		self.igWindow = importGenoWindow(cnx = self.cnx, userInfo = self.userInfo)
		self.igWindow.exec()
	
	# open export genotypes window
	def exportGeno(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		self.egWindow = exportGenoWindow(cnx = self.cnx, userInfo = self.userInfo)
		self.egWindow.exec()

	def importExportPed(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		self.epWindow = pedWindow(cnx = self.cnx, userInfo = self.userInfo)
		self.epWindow.exec()
	
	# open import phenotype data window
	def importPheno(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		self.iphenWindow = importPhenoWindow(cnx = self.cnx, userInfo = self.userInfo)
		self.iphenWindow.exec()

	# open import phenotype data window
	def exportPheno(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		self.ephenWindow = exportPhenoWindow(cnx = self.cnx, userInfo = self.userInfo)
		self.ephenWindow.exec()
	
	# open delete data window
	def deleteData(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Warning")
		messageBox.setText("You are now entering the DANGER ZONE.\nThis allows you to permanently delete data " +
					 "from the database. There is no undo functionality. Please consider backing up the database " +
					 "before proceeding.")
		messageBox.exec()
		self.delWindow = deleteDataWindow(cnx = self.cnx, userInfo = self.userInfo)
		self.delWindow.exec()
	
	# create a backup file using mysqldump
	def createBackupMysqldump(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		# warnings
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Warnings")
		messageBox.setText("This function will use your password on the command line in a relatively unsecure manner." + 
					" The program 'mysqldump' will be used. This may be slow and result in a very large file. An alternative option" +
					" for backing up the database is to use the 'MySQL Shell' utilities 'util.dumpSchemas()' to generate backup files and" +
					 " 'util.loadDump()' to load the backup files as needed.")
		messageBox.exec()

		# get output file name
		tempFile = QFileDialog.getSaveFileName(self, "Save output as", "/home/")[0]
		if tempFile == "":
			return
		# find mysqldump
		mysqldumpPath = shutil.which("mysqldump")
		if mysqldumpPath is None:
			messageBox = QMessageBox(parent=self)
			messageBox.setWindowTitle("mysqldump location")
			messageBox.setText("The program 'mysqldump' was not found in the system path. Please select the program location.")
			messageBox.exec()
			mysqldumpPath = QFileDialog.getOpenFileName(self, "Select mysqldump program", "/home/")[0]
			if mysqldumpPath == "":
				dlgError(parent=None, message="mysqldump not found or selected")
				return
		# create backup
		argList = [mysqldumpPath, "-p%s" % self.userInfo["pw"], "-u", self.userInfo["un"], "-h", self.userInfo["host"], "-r", tempFile, self.cnx.database]
		# print(subprocess.list2cmdline(argList))
		shellOut = subprocess.run(argList)
		messageBox = QMessageBox(parent=self)
		if shellOut.returncode == 0:
			messageBox.setWindowTitle("Complete")
			messageBox.setText("Backup file created.")
		else:
			messageBox.setWindowTitle("Error")
			messageBox.setText("Error creating backup file.")
		messageBox.exec()
	
	# create a new database using an sql backup file created
	# for ONE database with mysqldump
	def useBackupMysqldump(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		# issue warning message
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Warnings")
		messageBox.setText("This function will use your password on the command line in a relatively unsecure manner." + 
					 " This function will create a new database and execute the provided SQL file within that database. The SQL file should be generated" +
					 " by mysqldump for ONE database only. Files generated for multiple databases could cause unexpectd issues." + 
					 " Do not use this funciton with an SQL file of unknown source that could contain malicious code. All code in the provided file" +
					 " will be executed with the privileges of the active user account.")
		messageBox.exec()

		# get new database name
		dbName = QInputDialog.getText(self, "Make new database from backup", "New database name:")
		if not dbName[1]:
			return
		newDB = dbName[0]
		if not identifier_syntax_check(newDB):
			dlgError(parent=self, message="Database name has invalid syntax")
			return
		
		# get backup file
		backupFile = QFileDialog.getOpenFileName(self, "Select mysqldump backup (dump) file", "/home/")[0]
		if backupFile == "":
			dlgError(parent = self, message="Dump file not selected.")
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
				dlgError(parent = self, message="A database with that name already exists on this server.")
				return
			# make database on MySQL server
			curs.execute("CREATE DATABASE `%s`" % newDB)

		self.cnx.commit()

		# execute backup file
		# find mysql
		mysqlPath = shutil.which("mysql")
		if mysqlPath is None:
			messageBox = QMessageBox(parent=self)
			messageBox.setWindowTitle("mysql location")
			messageBox.setText("The program 'mysql' was not found in the system path. Please select the program location.")
			messageBox.exec()
			mysqlPath = QFileDialog.getOpenFileName(self, "Select mysql program", "/home/")[0]
			if mysqlPath == "":
				dlgError(parent=None, message="mysql not found or selected")
				return
		# SOURCE file
		argList = [mysqlPath, "-p%s" % self.userInfo["pw"], "-u", self.userInfo["un"], "-h", self.userInfo["host"], "-D", newDB, "-e", "SOURCE %s" % backupFile]
		# print(subprocess.list2cmdline(argList))
		shellOut = subprocess.run(argList)
		messageBox = QMessageBox(parent=self)
		if shellOut.returncode == 0:
			with self.cnx.cursor() as curs:
				curs.execute("USE `%s`" % newDB)
			# update values for database being used
			self.userInfo["db"] = self.cnx.database
			self.labelValues[2].setText(self.cnx.database)
			
			messageBox.setWindowTitle("Complete")
			messageBox.setText("Backup file executed and now using the new database.")
		else:
			# drop new database
			with self.cnx.cursor() as curs:
				curs.execute("DROP DATABASE `%s`" % newDB)
			messageBox.setWindowTitle("Error")
			messageBox.setText("Error executing backup file.")
		self.cnx.commit()
		messageBox.exec()

	# Putting examples of using mysql shell on the command line for backup here as an easy reference
	# mysqlsh # start mysql shell
	# \js # enter javascript mode
	# util.dumpSchemas(["cvir_test"], "C:/cvirTestDump") # generate backup of one database

	# mysqlsh # start mysql shell
	# SET GLOBAL local_infile = 'ON'; # set variable allowing loading from a file
	# \js # start javascript mode
	# util.loadDump("C:/cvirTestDump") # load in backup

	# create a backup folder using mysql shell
	def createBackupMysqlsh(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		# warnings
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Warnings")
		messageBox.setText(" The program 'mysqlsh' will be used. Depending on your system and database, this could be slow and result in very large files. An alternative option" +
					" is to use the 'MySQL Shell' utilities directly ('util.dumpSchemas()' to generate backup files and" +
					 " 'util.loadDump()' to load the backup files as needed) for more control.")
		messageBox.exec()

		# get output folder name
		tempFile = QFileDialog.getSaveFileName(self, "Save output as", "/home/")[0]
		if tempFile == "":
			return
		# find mysqlsh
		mysqlshPath = shutil.which("mysqlsh")
		if mysqlshPath is None:
			messageBox = QMessageBox(parent=self)
			messageBox.setWindowTitle("mysqlsh location")
			messageBox.setText("The program 'mysqlsh' was not found in the system path. Please select the program location.")
			messageBox.exec()
			mysqlshPath = QFileDialog.getOpenFileName(self, "Select mysqlsh program", "/home/")[0]
			if mysqlshPath == "":
				dlgError(parent=None, message="mysqlsh not found or selected")
				return
		# create backup
		argList = [mysqlshPath, "--passwords-from-stdin", "--js", "-u", self.userInfo["un"], "-h", self.userInfo["host"],
			 "-e", 'util.dumpSchemas(["%s"], "%s")' % (self.cnx.database, tempFile)]
		# print(subprocess.list2cmdline(argList))
		# sending password as stdin
		shellOut = subprocess.run(argList, input=self.userInfo["pw"], text=True)
		messageBox = QMessageBox(parent=self)
		if shellOut.returncode == 0:
			messageBox.setWindowTitle("Complete")
			messageBox.setText("Backup created.")
		else:
			messageBox.setWindowTitle("Error")
			messageBox.setText("Error creating backup.")
		messageBox.exec()

	# import from a backup folder using mysql shell
	def useBackupMysqlsh(self):
		if (not hasattr(self, "cnx")) or self.cnx.database == "" or self.cnx.database is None:
			dlgError(parent = self, message="Error, not connected to a database")
			return
		# warnings
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Warnings")
		messageBox.setText(" The program 'mysqlsh' will be used. Depending on your system and database, this could be slow. An alternative option" +
					" is to use the 'MySQL Shell' utilities directly ('util.dumpSchemas()' to generate backup files and" +
					 " 'util.loadDump()' to load the backup files as needed) for more control.")
		messageBox.exec()

		# get backup directory
		backupFile = QFileDialog.getExistingDirectory(self, "Select mysqlsh backup folder", "/home/")
		if backupFile == "":
			dlgError(parent = self, message="Backup folder not selected.")
			return
		# find mysqlsh
		mysqlshPath = shutil.which("mysqlsh")
		if mysqlshPath is None:
			messageBox = QMessageBox(parent=self)
			messageBox.setWindowTitle("mysqlsh location")
			messageBox.setText("The program 'mysqlsh' was not found in the system path. Please select the program location.")
			messageBox.exec()
			mysqlshPath = QFileDialog.getOpenFileName(self, "Select mysqlsh program", "/home/")[0]
			if mysqlshPath == "":
				dlgError(parent=None, message="mysqlsh not found or selected")
				return
		mod_infile = False # tracking whether switched global variable 'local_infile'
		# check setting
		with self.cnx.cursor() as curs:
			curs.execute("SHOW GLOBAL VARIABLES LIKE 'local_infile'")
			local_infile = curs.fetchone()[1]
			# modify if needed
			if local_infile != "ON":
				mod_infile = True
			curs.execute("SET GLOBAL local_infile = 'ON'")

		# load backup
		argList = [mysqlshPath, "--passwords-from-stdin", "--js", "-u", self.userInfo["un"], "-h", self.userInfo["host"],
			 "-e", 'util.loadDump("%s")' % (backupFile)]
		# print(subprocess.list2cmdline(argList))
		# sending password as stdin
		shellOut = subprocess.run(argList, input=self.userInfo["pw"], text=True)

		# change back local_infile setting if needed
		if mod_infile:
			with self.cnx.cursor() as curs:
				curs.execute("SET GLOBAL local_infile = '%s'" % local_infile)

		messageBox = QMessageBox(parent=self)
		if shellOut.returncode == 0:
			messageBox.setWindowTitle("Complete")
			messageBox.setText("Backup imported.")
		else:
			messageBox.setWindowTitle("Error")
			messageBox.setText("Error importing from backup.")
		messageBox.exec()
