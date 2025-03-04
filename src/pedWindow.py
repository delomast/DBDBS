# import pedigree records window
import mysql.connector as connector
import re
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QComboBox, 
	 QGridLayout, QRadioButton,
	 QFileDialog, QVBoxLayout, QDialog,
	 QHBoxLayout, QMessageBox
)
from .utils import (dlgError, 
	numBits, indsInPedigree, addToPedigree,
	indsInTable, getIndsFromFile, getIndIDdict, getGenoConvertDict,
	getLocusOrderInBlob, altCopiesToGeno
)
from .genotypeFileIterators import *



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
		self.updateRadio = QRadioButton("Update existing individuals", self)
		self.exportRadio = QRadioButton("Export pedigree", self)
		self.exportRadio.setChecked(True) # default is export pedigree

		# file selection button and label
		# input file is list of individual names to export genotypes for
		# one name per line, no header
		self.selectInputFile = QPushButton("Sample names file")
		self.selectInputFile.clicked.connect(self.onClickInputFile)
		self.inputFile = QLabel("")
		self.inputFile.setWordWrap(True)
		self.selectOutputFile = QPushButton("Save as")
		self.selectOutputFile.clicked.connect(self.onClickOutputFile)
		self.outputFile = QLabel("")
		self.outputFile.setWordWrap(True)

		# check for new individuals button
		self.checkIndsButton = QPushButton("Check if individuals are in the database")
		self.checkIndsButton.clicked.connect(self.checkNewInds)

		# start export button
		self.startButton = QPushButton("Go")
		self.startButton.clicked.connect(self.startAction)

		# set up layout
		self.gridLayout = QGridLayout()

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
		self.mainLayout.addLayout(self.fileSelectLayout1)
		self.mainLayout.addLayout(self.fileSelectLayout2)
		self.mainLayout.addLayout(self.gridLayout2)
		self.setLayout(self.mainLayout)


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
		
		# commit transaction after all individuals successfully added
		self.cnx.commit()

		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Pedigree import/export")
		messageBox.setText(msgTxt)
		messageBox.exec()
		self.close()
	
	def exportPedigree(self):
		# TODO
		pass
	
	def updatePedigree(self):
		# TODO
		pass

	def addNewInds(self):
		# TODO test this function
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
