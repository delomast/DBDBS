# import pedigree records window
import mysql.connector as connector
from PyQt6.QtWidgets import (
	QPushButton, QLabel, 
	 QGridLayout, QRadioButton,
	 QFileDialog, QVBoxLayout, QDialog,
	 QHBoxLayout, QMessageBox
)
from .utils import (dlgError, 
	indsInPedigree, addToPedigree,
	getIndsFromFile, getIndIDdict
)


# using QDialog class and exec to block other windows - only one active window at a time
class pedWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Import or export pedigree")
		self.cnx = cnx
		self.userInfo = userInfo

		self.setMinimumSize(500, 400) # trying to avoid :"Unable to set geometry" warning

		# import new, update existing, or export radio buttons
		self.addNewRadio = QRadioButton("Add new individuals", self)
		self.addNewRadio.toggled.connect(self.onActionSelectionChange)
		self.updateRadio = QRadioButton("Update existing individuals", self)
		self.updateRadio.toggled.connect(self.onActionSelectionChange)
		self.exportRadio = QRadioButton("Export pedigree", self)
		self.exportRadio.setChecked(True) # default is export pedigree
		self.exportRadio.toggled.connect(self.onActionSelectionChange)

		# file selection button and label
		# input file is list of individual names to export genotypes for
		# one name per line, no header
		self.selectInputFile = QPushButton("Choose input file")
		self.selectInputFile.clicked.connect(self.onClickInputFile)
		self.inputFile = QLabel("")
		self.inputFile.setWordWrap(True)
		self.inputFileHeaderInfo = QLabel("")
		self.selectOutputFile = QPushButton("Save export as")
		self.selectOutputFile.clicked.connect(self.onClickOutputFile)
		self.outputFile = QLabel("")
		self.outputFile.setWordWrap(True)

		# check for new individuals button
		self.checkIndsButton = QPushButton("Check if individuals are in the database")
		self.checkIndsButton.clicked.connect(self.checkNewInds)

		# start import or export button
		self.startButton = QPushButton("Start import or export")
		self.startButton.clicked.connect(self.startAction)

		# set up layout
		self.gridLayout = QGridLayout()
		self.gridLayout.addWidget(self.addNewRadio, 0, 0)
		self.gridLayout.addWidget(self.updateRadio, 1, 0)
		self.gridLayout.addWidget(self.exportRadio, 2, 0)

		# layout for input/export file buttons and display of selected file names
		self.fileSelectLayout1 = QHBoxLayout()
		self.fileSelectLayout1.addWidget(self.selectInputFile)
		self.fileSelectLayout1.addWidget(self.inputFile)
		
		self.fileSelectLayout2 = QHBoxLayout()
		self.fileSelectLayout2.addWidget(self.selectOutputFile)
		self.fileSelectLayout2.addWidget(self.outputFile)

		# set up action button layout
		self.gridLayout2 = QGridLayout()
		self.gridLayout2.addWidget(self.checkIndsButton, 0, 0)
		self.gridLayout2.addWidget(self.startButton, 1, 0)

		# add grid layout as top layout in main layout
		self.mainLayout = QVBoxLayout()
		self.mainLayout.addLayout(self.gridLayout)
		self.mainLayout.addWidget(self.inputFileHeaderInfo)
		self.mainLayout.addLayout(self.fileSelectLayout1)
		self.mainLayout.addLayout(self.fileSelectLayout2)
		self.mainLayout.addLayout(self.gridLayout2)
		self.setLayout(self.mainLayout)
		
		# write label text for initial selection
		self.onActionSelectionChange()

	# change info about header in input file
	def onActionSelectionChange(self):
		if self.exportRadio.isChecked():
			self.inputFileHeaderInfo.setText("Input file optional, no header row")
		elif self.addNewRadio.isChecked() or self.updateRadio.isChecked():
			self.inputFileHeaderInfo.setText("Three column input file (Ind, Sire, Dam), header row required")
		else:
			self.inputFileHeaderInfo.setText("")

	# open file dialog for user to select an input file
	def onClickInputFile(self):
		tempFile = QFileDialog.getOpenFileName(self, "Select input file", "/home/")[0]
		if tempFile == "":
			return
		self.inputFile.setText(tempFile)

	# open file dialog for user to select an output file path
	def onClickOutputFile(self):
		tempFile = QFileDialog.getSaveFileName(self, "Save output as", "/home/")[0]
		if tempFile == "":
			return
		self.outputFile.setText(tempFile)
	
	def startAction(self):
		if self.exportRadio.isChecked():
			msgTxt = self.exportPedigree()
		elif self.updateRadio.isChecked():
			msgTxt = self.updatePedigree()
		elif self.addNewRadio.isChecked():
			msgTxt = self.addNewInds()
		else:
			dlgError(parent=self, message="Error, one action must be selected")
			return
		
		if msgTxt is None:
			return # keeps window open
		
		# commit transaction after all individuals successfully added or updated
		if self.updateRadio.isChecked() or self.addNewRadio.isChecked():
			self.cnx.commit()

		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Pedigree import/export")
		messageBox.setText(msgTxt)
		messageBox.exec()
		self.close()
	
	# this should probably be converted to a utility function to allow other export routines (genotype or phenotype export)
	# to call it
	# export the pedigree
	# either 1) the entire pedigree or 
	# 2) a group of individuals and their ancestors
	# considering adding - 3) a group of individuals and all their 
	# relatives (ancestors and descendents)
	def exportPedigree(self):
		# get pedigree
		curs = self.cnx.cursor()
		if self.inputFile.text() == "":
			# if no input list of individuals, export the entire pedigree
			# select ind name, sire name, dam name
			# sire name and dam name are from left joins
			curs.execute("SELECT p.ind, sire.ind AS sire, dam.ind AS dam FROM intDBpedigree AS p LEFT JOIN intDBpedigree AS dam ON p.dam = dam.ind_id " + 
				"LEFT JOIN intDBpedigree AS sire ON p.sire = sire.ind_id ORDER BY p.ind_id")
		else:
			# check for duplicate inds and make sure all are in pedigree
			inds = getIndsFromFile(self.inputFile.text(), "forExport")
			if inds[1]:
				dlgError(parent=self, message="Duplicate individual names in the input file")
				return
			inds = inds[0]
			indsInPed = indsInPedigree(self.cnx, inds)

			# make sure all are in the pedigree already
			if len(indsInPed[1]) > 0:
				dlgError(parent=self, message="One or more individuals is not in the pedigree")
				return
			
			# iteratively getting pedigree
			# first selects the individuals requested
			# then iteratively selects the sires and dams
			# does not repeat rows
			# then translates id integers to original ids
			# orders by ind_id, which is order inds were added to the database
			# cte_max_recursion_depth is the number of generations it will go back 
			# before throwing an error
			curs.execute("""WITH RECURSIVE cte (ind_id, sire, dam) AS(
SELECT ind_id, sire, dam FROM intDBpedigree 
WHERE ind IN (%s)
UNION DISTINCT
SELECT p2.ind_id, p2.sire, p2.dam 
FROM intDBpedigree AS p2, cte AS c 
WHERE p2.ind_id = c.sire OR p2.ind_id = c.dam
)
SELECT /*+ SET_VAR(cte_max_recursion_depth = 10000) */ tp.ind AS ind, sire.ind AS sire, dam.ind AS dam 
FROM cte 
LEFT JOIN 
intDBpedigree AS tp ON cte.ind_id = tp.ind_id
LEFT JOIN 
intDBpedigree AS sire ON cte.sire = sire.ind_id
LEFT JOIN
intDBpedigree AS dam ON cte.dam = dam.ind_id
ORDER BY cte.ind_id;""" % ", ".join(["'%s'" % x for x in inds]))
		
		# write out pedigree
		with open(self.outputFile.text(), "w") as outFile:
			outFile.write("Ind\tSire\tDam\n")
			for row in curs:
				outFile.write("\t".join([x if x is not None else "" for x in row]) + "\n")
		# close cursor
		curs.close()
		return "Pedigree export completed"

	
	# update dam and sire for individuals in the pedigree
	def updatePedigree(self):
		if self.inputFile.text() == "":
			dlgError(parent=self, message="No input file is selected")
			return None

		# check if inds are in pedigree
		inds = getIndsFromFile(self.inputFile.text(), "pedImport") # get list of inds
		if inds[1]:
			dlgError(parent=self, message="Duplicate individual names in the input file")
			return None
		inds = list(inds[0])
		pedStatus = indsInPedigree(self.cnx, inds) # check if in pedigree
		if len(pedStatus[1]) > 0:
			dlgError(parent=self, message="Some individuals in the input are not in the pedigree")
			return None
		
		# make sure all sires and dams are in the pedigree
		sireDamInds = list(set(getIndsFromFile(self.inputFile.text(), "sireDam")[0])) # get a list of the sires and dams
		pedStatusSD = indsInPedigree(self.cnx, sireDamInds) # check if in pedigree
		if len(pedStatusSD[1]) > 0:
			dlgError(parent=self, message="Some sires and/or dams are not already in the pedigree")
			return None
		
		# update the pedigree
		inds = []
		sires = []
		dams = []
		with open(self.inputFile.text(), "r") as f:
			header = f.readline() # skip header
			for line in f:
				sep = line.rstrip("\n").split("\t")
				inds.append(sep[0])
				sires.append(sep[1])
				dams.append(sep[2])
		# translate to IDs
		IDdict = getIndIDdict(self.cnx, list(set(inds + sireDamInds)))
		# translate names to ids
		indID = [IDdict[x] for x in inds]
		damID = []
		sireID = []
		for d in dams:
			if d == "":
				damID.append("NULL")
			else:
				damID.append(IDdict[d])
		for s in sires:
			if s == "":
				sireID.append("NULL")
			else:
				sireID.append(IDdict[s])
		with self.cnx.cursor() as curs:
			for i, s, d in zip(indID, sireID, damID):
				curs.execute("UPDATE `intDBpedigree` SET sire = %s, dam = %s WHERE ind_id = %s" % (s, d, i))
		# return a message to show the user
		return "The pedigree was successfully updated"


	# add new individuals to the pedigree
	def addNewInds(self):
		if self.inputFile.text() == "":
			dlgError(parent=self, message="No input file is selected")
			return None

		# check if inds are in pedigree
		inds = getIndsFromFile(self.inputFile.text(), "pedImport") # get list of inds
		if inds[1]:
			dlgError(parent=self, message="Duplicate individual names in the input file")
			return None
		inds = list(inds[0])
		pedStatus = indsInPedigree(self.cnx, inds) # check if in pedigree
		if len(pedStatus[0]) > 0:
			dlgError(parent=self, message="Some individuals in the input are already in the pedigree")
			return None
		
		# make sure all sires and dams are in the pedigree
		sireDamInds = list(set(getIndsFromFile(self.inputFile.text(), "sireDam")[0])) # get a list of the sires and dams
		pedStatusSD = indsInPedigree(self.cnx, sireDamInds) # check if in pedigree
		if len(pedStatusSD[1]) > 0:
			dlgError(parent=self, message="Some sires and/or dams are not already in the pedigree")
			return None
		
		# add new individuals to pedigree
		inds = []
		sires = []
		dams = []
		with open(self.inputFile.text(), "r") as f:
			header = f.readline() # skip header
			for line in f:
				sep = line.rstrip("\n").split("\t")
				inds.append(sep[0])
				sires.append(sep[1])
				dams.append(sep[2])
		retValue = addToPedigree(self.cnx, inds, sires, dams)
		if retValue != 0:
			# error
			dlgError(parent=self, message="Error trying to add individuals to the pedigree")
			return None
		
		# return a message to show the user
		return "New individuals successfully added to the pedigree"
	

	# user action to check if individuals are in the pedigee
	# and optionally write a file detailing status of all individuals in the 
	# input file
	def checkNewInds(self):
		if self.inputFile.text() == "":
			dlgError(parent=self, message="No input file is selected")
			return
		# get list of inds
		if self.exportRadio.isChecked():
			fileType = "forExport"
		else:
			fileType = "pedImport"
		inds = getIndsFromFile(self.inputFile.text(), fileType)
		if inds[1]:
			dlgError(parent=self, message="Duplicate individual names in the input file")
			return
		inds = list(inds[0])
		# check if inds are in pedigree
		pedStatus = indsInPedigree(self.cnx, inds)
		
		# show summary message and ask whether to write a report
		writeReportBox = QMessageBox(parent=self)
		writeReportBox.setWindowTitle("Individual check")
		msgTxt = "Of %s total individuals, %s are already in the pedigree. " % \
		(len(inds), len(pedStatus[0]))
		msgTxt += "Write report to " + self.inputFile.text() + "_indReport.txt?"
		writeReportBox.setText(msgTxt)
		writeReportBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
		writeReport = writeReportBox.exec()

		# write report
		if writeReport == QMessageBox.StandardButton.Yes:
			with open(self.inputFile.text() + "_indReport.txt", "w") as fout:
				fout.write("ind\tinPedigree\n") # write header line
				# in ped
				for name in pedStatus[0]:
					fout.write("\t".join([name, "TRUE"]) + "\n")
				# not in ped
				for name in pedStatus[1]:
					fout.write("\t".join([name, "FALSE"]) + "\n")

		
		# check if dams and sires are in pedigree
		if not self.exportRadio.isChecked():
			# get a list of all the sires and dams in the file with no duplicates
			sireDamInds = list(set(getIndsFromFile(self.inputFile.text(), "sireDam")[0]))
			# check if in pedigree
			pedStatusSD = indsInPedigree(self.cnx, sireDamInds)
		
			writeReportBox = QMessageBox(parent=self)
			writeReportBox.setWindowTitle("Individual check")
			msgTxt = "Of %s total sires and dams, %s are already in the pedigree. " % \
			(len(sireDamInds), len(pedStatusSD[0]))
			msgTxt += "Write report to " + self.inputFile.text() + "_sireDamReport.txt?"
			writeReportBox.setText(msgTxt)
			writeReportBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
			writeReport = writeReportBox.exec()

			# write report
			if writeReport == QMessageBox.StandardButton.Yes:
				with open(self.inputFile.text() + "_sireDamReport.txt", "w") as fout:
					fout.write("ind\tinPedigree\n") # write header line
					# in ped
					for name in pedStatusSD[0]:
						fout.write("\t".join([name, "TRUE"]) + "\n")
					# not in ped
					for name in pedStatusSD[1]:
						fout.write("\t".join([name, "FALSE"]) + "\n")
