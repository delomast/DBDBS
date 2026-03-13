# import phenotype data window
import mysql.connector as connector
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QComboBox, 
	 QFileDialog, QVBoxLayout, QDialog,
	 QRadioButton, QHBoxLayout, QMessageBox
)
from .utils import (dlgError, getIndIDdict
)

# using QDialog class and exec to block other windows - only one active window at a time
class deleteDataWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Delete data")
		self.cnx = cnx
		self.userInfo = userInfo

		self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
		self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
		self.setMinimumSize(500, 400) # trying to avoid :"Unable to set geometry" warning
		
		# select what type of data to delete
		self.genoRadio = QRadioButton("Genotype", self)
		self.genoRadio.clicked.connect(self.changeType)
		self.phenoRadio = QRadioButton("Phenotype", self)
		self.phenoRadio.clicked.connect(self.changeType)
		self.pedRadio = QRadioButton("Pedigree", self)
		self.pedRadio.clicked.connect(self.changeType)

		# table selection dropbox
		self.tableComboBox = QComboBox()
		with cnx.cursor() as curs:
			curs.execute("SELECT table_name FROM intDBpheno_overview")
			tables = [x for x in curs]
		self.tables = [x[0] for x in tables]
		
		# panel selection dropbox
		self.panelComboBox = QComboBox()
		with cnx.cursor() as curs:
			curs.execute("SELECT panel_name FROM intDBgeno_overview")
			panels = [x for x in curs]
		self.panels = [x[0] for x in panels]
		
		self.radioLayout = QHBoxLayout()
		self.radioLayout.addWidget(self.genoRadio)
		self.radioLayout.addWidget(self.phenoRadio)
		self.radioLayout.addWidget(self.pedRadio)

		self.dropBoxLayout = QHBoxLayout()
		self.dropBoxLayout.addWidget(QLabel("Genotype panel: "))
		self.dropBoxLayout.addWidget(self.panelComboBox)
		self.dropBoxLayout.addWidget(QLabel("Phenotype table: "))
		self.dropBoxLayout.addWidget(self.tableComboBox)

		self.fileLayout = QHBoxLayout()
		self.fileLayout.addWidget(QLabel("Input file: "))
		self.inputFile = QLabel("")
		self.inputFile.setWordWrap(True)
		self.fileLayout.addWidget(self.inputFile)

		self.selectFileButton = QPushButton("Select input file")
		self.selectFileButton.clicked.connect(self.onClickInputFile)

		self.checkFileButton = QPushButton("Check input file")
		self.checkFileButton.clicked.connect(self.checkFile)

		self.deleteDataButton = QPushButton("Delete data")
		self.deleteDataButton.clicked.connect(self.deleteData)


		# add radio layout and table/panel selection layout to main layout
		self.mainLayout = QVBoxLayout()
		self.mainLayout.addWidget(QLabel("WARNING\nThis will delete data from the database.\nThere is no undo functionality."))
		self.mainLayout.addLayout(self.radioLayout)
		self.mainLayout.addLayout(self.dropBoxLayout)
		self.mainLayout.addWidget(self.selectFileButton)
		self.mainLayout.addLayout(self.fileLayout)
		self.mainLayout.addWidget(self.checkFileButton)
		self.mainLayout.addWidget(self.deleteDataButton)

		self.setLayout(self.mainLayout)


	def changeType(self):
		# clear what is user selectable
		if self.genoRadio.isChecked():
			self.panelComboBox.addItems(self.panels)
			self.tableComboBox.clear()
		elif self.phenoRadio.isChecked():
			self.panelComboBox.clear()
			self.tableComboBox.addItems(self.tables)
		else:
			self.panelComboBox.clear()
			self.tableComboBox.clear()

	# open file dialog for user to select an input file
	def onClickInputFile(self):
		tempFile = QFileDialog.getOpenFileName(self, "Select input file", "/home/")[0]
		if tempFile == "":
			return
		self.inputFile.setText(tempFile)
	
	def checkFile(self):
		self.deleteData(dryRun=True)
	
	# check how many input lines correspond to entries in the table to be deleted
	# optionally write a report
	# file should have no header, columns of ind name (or sire name, dam name), (obs date or datetime)
	# dryRun True to report count of rows to be deleted, False to delete rows
	def deleteData(self, s = None, dryRun = False):
		if not self.checkStatus():
			return
		with open(self.inputFile.text(), "r") as inFile:
			toRem = [x.rstrip("\n").split("\t") for x in inFile]
		if self.phenoRadio.isChecked():
			# determine if family or individual data
			with self.cnx.cursor() as curs:
				curs.execute("SELECT ind_name_col, sire_name_col FROM intDBpheno_overview WHERE table_name = %s", (self.tableComboBox.currentText(),))
				info =[x for x in curs.fetchone()]
				if info[0] is None:
					famTable = True
				else:
					famTable = False
				# get dict to change ind names to ids
				if famTable is True:
					inds = set([x[0] for x in toRem]).union(set([x[1] for x in toRem]))
				else:
					inds = set([x[0] for x in toRem])
				indIDdict = getIndIDdict(self.cnx, list(inds))
				# change names to ids and build sql statement
				if dryRun:
					sqlState = "SELECT COUNT(*) FROM `%s` WHERE " % self.tableComboBox.currentText()
				else:
					sqlState = "DELETE FROM `%s` WHERE " % self.tableComboBox.currentText()
				if famTable:
					sqlState += "(intDBsire, intDBdam, intDBu_DTobs) IN ("
				else:
					sqlState += "(intDBind_id, intDBu_DTobs) IN ("
				for x in toRem:
					y = x.copy()
					y[0] = str(indIDdict[y[0]])
					if famTable:
						y[1] = str(indIDdict[y[1]])
						y[2] = "'%s'" % y[2]
					else:
						y[1] = "'%s'" % y[1]
					sqlState += "(%s)," % ",".join(y)
				curs.execute(sqlState.rstrip(",") + ")")
				if dryRun:
					toDelCount = curs.fetchone()[0]
		elif self.genoRadio.isChecked() or self.pedRadio.isChecked():
			if self.pedRadio.isChecked():
				tableName = "intDBpedigree"
			else:
				tableName = self.panelComboBox.currentText()
			# get dict to change ind names to ids
			toRem = [x[0] for x in toRem]
			indIDdict = getIndIDdict(self.cnx, toRem)
			# change names to ids and build sql statement
			if dryRun:
				sqlState = "SELECT COUNT(*) FROM `%s` WHERE ind_id IN (" % tableName
			else:
				sqlState = "DELETE FROM `%s` WHERE ind_id IN (" % tableName
			toRem = [str(indIDdict[x]) for x in toRem]
			sqlState += ",".join(toRem) + ")"
			with self.cnx.cursor() as curs:
				try:
					curs.execute(sqlState)
				except Exception as e:
					if not dryRun and self.pedRadio.isChecked():
						dlgError(parent=None, message="Deletion from pedigree failed. Are there genotypes or phenotypes for one or more of these individuals still in the database?")
						repr(e)
						return
					else:
						raise e
				if dryRun:
					toDelCount = curs.fetchone()[0]
		else:
			return # defensive
		
		# write message
		if dryRun:
			messageBox = QMessageBox(parent=self)
			messageBox.setWindowTitle("Count to delete")
			messageBox.setText("%s input rows detected, %s rows will be deleted." % (len(toRem), toDelCount))
			messageBox.exec()
		else:
			self.cnx.commit()
			messageBox = QMessageBox(parent=self)
			messageBox.setWindowTitle("Deletion completed")
			messageBox.setText("Data deletion completed.")
			messageBox.exec()

	# check if user has provided inputs for functions to proceed
	def checkStatus(self):
		if self.inputFile.text() == "":
			dlgError(parent=self, message="No input file is selected")
			return False
		if not self.phenoRadio.isChecked() and not self.genoRadio.isChecked() and not self.pedRadio.isChecked():
			dlgError(parent=self, message="No data type is selected")
			return False
		return True
