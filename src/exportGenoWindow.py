# export genotype data window
import mysql.connector as connector
import re
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QComboBox, 
	 QGridLayout,
	 QFileDialog, QVBoxLayout, QDialog,
	 QHBoxLayout, QMessageBox
)
from .utils import (dlgError, 
	numBits, indsInPedigree,
	indsInTable, getIndsFromFile, getIndIDdict, getGenoConvertDict,
	getLocusOrderInBlob, altCopiesToGeno
)
from .genotypeFileIterators import *


# TODO add option to export PLINK format with accurate pedigree

# using QDialog class and exec to block other windows - only one active window at a time
class exportGenoWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Export genotypes")
		self.cnx = cnx
		self.userInfo = userInfo

		self.setMinimumSize(500, 400) # trying to avoid :"Unable to set geometry" warning

		# panel selection dropbox
		self.panelComboBox = QComboBox()
		with cnx.cursor() as curs:
			curs.execute("SELECT panel_name FROM intDBgeno_overview")
			panels = [x for x in curs]
		if len(panels) == 0:
			dlgError(parent=self, message="No genotype panels are defined in the database")
			return
		panels = [x[0] for x in panels]
		self.panelComboBox.addItems(panels)
		self.panelComboBox.currentTextChanged.connect(self.panelSelectionChange)

		# display information in the window about the selected panel
		self.panelTypeLabel = QLabel("")
		self.panelPloidyLabel = QLabel("")
		self.panelSizeLabel = QLabel("")

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

		# file format dropbox
		self.fileFormat = QComboBox()
		# 2col: tab-delimited, 1 column per allele (2col per call for alleles)
		# first col is individual name
		# with header line
		# locus names pulled from header for first column, optionally stripping [\.-_][aA]1
		# long: tab delimited, columns of ind name, locus name, allele1, allele2, ..., allele n
		# with header line
		self.fileFormat.addItems(["2col", "PLINK ped", "long"])
		self.fileFormat.currentTextChanged.connect(self.changeFormat)

		# check for new individuals button
		self.checkIndsButton = QPushButton("Check if individuals are in the database")
		self.checkIndsButton.clicked.connect(self.checkNewInds)

		# start export button
		self.exportButton = QPushButton("Export genotypes")
		self.exportButton.clicked.connect(self.exportGenotypes)

		# set up layout
		self.gridLayout = QGridLayout()
		self.gridLayout.addWidget(QLabel("Panel name"), 0, 0)
		self.gridLayout.addWidget(self.panelComboBox, 0, 1)
		self.gridLayout.addWidget(QLabel("Panel type"), 0, 2)
		self.gridLayout.addWidget(self.panelTypeLabel, 0, 3)
		self.gridLayout.addWidget(QLabel("File format"), 1, 0)
		self.gridLayout.addWidget(self.fileFormat, 1, 1)
		self.gridLayout.addWidget(QLabel("Panel ploidy"), 1, 2)
		self.gridLayout.addWidget(self.panelPloidyLabel, 1, 3)
		self.gridLayout.addWidget(QLabel("Number of loci"), 2, 2)
		self.gridLayout.addWidget(self.panelSizeLabel, 2, 3)
		# extra row and column to stretch and account for extra space
		# allows sizing of other rows and columns to be constant
		self.gridLayout.setRowStretch(self.gridLayout.rowCount(), 1)
		# self.gridLayout.setColumnStretch(self.gridLayout.columnCount(), 1)

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
		self.gridLayout2.addWidget(self.exportButton, 1, 0)

		# add grid layout as top layout in main layout
		self.mainLayout = QVBoxLayout()
		self.mainLayout.addLayout(self.gridLayout)
		self.mainLayout.addLayout(self.fileSelectLayout1)
		self.mainLayout.addLayout(self.fileSelectLayout2)
		self.mainLayout.addLayout(self.gridLayout2)
		self.setLayout(self.mainLayout)

		# update labels with values for default selections
		self.panelSelectionChange() 
		self.changeFormat()


	# export file format specific options
	def changeFormat(self):
		# here in case need in the future
		return

	# update labels with information from new panel
	def panelSelectionChange(self):
		with self.cnx.cursor() as curs:
			curs.execute("SELECT number_of_loci, ploidy, panel_type FROM intDBgeno_overview WHERE panel_name = %s", (self.panelComboBox.currentText(),))
			info =[str(x) for x in curs.fetchone()]
			# update panel type label
			self.panelTypeLabel.setText(info[2])
			# update panel ploidy label and int
			self.panelPloidyLabel.setText(info[1])
			self.panelPloidy = int(info[1])
			# update number of loci label
			self.panelSizeLabel.setText(info[0])

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
	
	# check if individuals are 1) in pedigee and 2) in genotype panel
	def checkNewInds(self):
		if self.inputFile.text() == "":
			dlgError(parent=self, message="No input file is selected")
			return
		# get list of inds
		inds = getIndsFromFile(self.inputFile.text(), "forExport")
		if inds[1]:
			dlgError(parent=self, message="Duplicate individual names in the input file")
			return
		inds = list(inds[0])
		# check if inds are in pedigree
		pedStatus = indsInPedigree(self.cnx, inds)
		if len(pedStatus[0]) == 0:
			# if none in ped, then none in genotype table
			genoStatus = (tuple(), tuple(inds))
		else:
			# check if inds in pedigree are in the genotype panel
			genoStatus = indsInTable(self.cnx, pedStatus[0], "intDB" + self.panelComboBox.currentText() + "_gt")
		
		# show summary message and ask whether to write a report
		writeReportBox = QMessageBox(parent=self)
		writeReportBox.setWindowTitle("Individual check")
		msgTxt = "Of %s total individuals, %s are already in the pedigree and %s are already in the genotype table. " % \
		(len(inds), len(pedStatus[0]), len(genoStatus[0]))
		msgTxt += "Write report to " + self.inputFile.text() + "_indReport.txt?"
		writeReportBox.setText(msgTxt)
		writeReportBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
		writeReport = writeReportBox.exec()

		# write report
		if writeReport == QMessageBox.StandardButton.Yes:
			with open(self.inputFile.text() + "_indReport.txt", "w") as fout:
				fout.write("ind\tinPedigree\tinGenotypePanel\n") # write header line
				# in both
				for name in genoStatus[0]:
					fout.write("\t".join([name, "TRUE", "TRUE"]) + "\n")
				# not in panel but in ped
				for name in set(genoStatus[1]).intersection(set(pedStatus[0])):
					fout.write("\t".join([name, "TRUE", "FALSE"]) + "\n")
				# not in either
				for name in pedStatus[1]:
					fout.write("\t".join([name, "FALSE", "FALSE"]) + "\n")


	# export genotypes
	def exportGenotypes(self):
		# make sure output file has been chosen
		if self.outputFile.text() == "":
			dlgError(parent=self, message="No output file name specified")
			return
		
		if self.inputFile.text() != "":
			# check for duplicate inds and make sure all are in pedigree
			inds = getIndsFromFile(self.inputFile.text(), "forExport")
			if inds[1]:
				dlgError(parent=self, message="Duplicate individual names in the input file")
				return
			inds = inds[0]
			indsInPed = indsInPedigree(self.cnx, inds)

			# make sure all are in the pedigree already
			if len(indsInPed[1]) > 0:
				dlgError(parent=self, message="You are trying to export genotypes but one or more individuals is not in the pedigree")
				return
			
			# check for presence of individuals in the genotype table
			tableCheck = indsInTable(self.cnx, inds, "intDB" + self.panelComboBox.currentText() + "_gt")
			if len(tableCheck[1]) > 0:
				dlgError(parent=self, message="You are trying to export genotypes but one or more individuals is not already in the genotype table")
				return
		else:
			# if no individual list specified, export entire genotype table
			with self.cnx.cursor() as curs:
				curs.execute("SELECT p.ind FROM intDBpedigree AS p INNER JOIN `intDB%s_gt` AS gt ON p.ind_id = gt.ind_id" % self.panelComboBox.currentText())
				inds = [x[0] for x in curs]
		
		# build dictionary of ind names and ind_id
		indIDlookup = getIndIDdict(self.cnx, inds)

		# get locus order - tuple of locus names in order of blob
		locusOrder = getLocusOrderInBlob(self.cnx, self.panelComboBox.currentText())

		# build dictionary of key = locus name, 
		# value = dict with key = genotype/allele, value of genotype/allele id
		# OR
		# value = tuple(ref allele, alt allele)
		genoConvertDict = getGenoConvertDict(self.cnx, self.panelComboBox.currentText(), None)
		# reverse lookup if needed
		revGenoConvertDict = {} # just making a new dict to avoid shallow copy issues with dictionaries
		if self.panelTypeLabel.text() == "Hyperallelic" or self.panelTypeLabel.text() == "Multiallelic":
			for lname in locusOrder:
				revGenoConvertDict[lname] = {}
				for k, v in genoConvertDict[lname].items():
					revGenoConvertDict[lname][v] = k
			# revGenoConvertDict is now dict with key = locus name,
			# value = dict with key = integer value of genotype/allele id, 
			# and value = text representation, sorted tuple of alleles (multi) or allele (hyper)
			# text representation of missing genotype/allele will be empty string, ""
		else:
			# if biallelic, leave as it is
			revGenoConvertDict = genoConvertDict
			# calculate once if needed
			nb = numBits(2, self.panelPloidy)
			# binaryFormatString = "0%sb" % nb
			missInt = self.panelPloidy + 1 # missing genotype value in database
		
		# initiate file
		outFile = open(self.outputFile.text(), "w")
		# write header and other files as needed
		if self.fileFormat.currentText() == "2col":
			# write header
			outFile.write("ind_name\t" + "\t".join(["%s.a%s" % (lname, x) for lname in locusOrder for x in range(1, self.panelPloidy + 1)]) + "\n")
		elif self.fileFormat.currentText() == "PLINK ped":
			if self.panelPloidy != 2:
				dlgError(parent=self, message="PLINK format is only defined for diploid data")
				return
			# no header line for ped file
			# write map file
			with open(re.sub(".ped$", "", self.outputFile.text()) + ".map", "w") as mapFile:
				# no header line
				for lname in locusOrder:
					# chrom, variant name, position in cM, position in bp
					mapFile.write("1\t" + lname + "\t0\t0\n")
		elif self.fileFormat.currentText() == "long":
			# write header
			outFile.write("ind_name\tlocus\t" + "\t".join(["allele_%s" % x for x in range(1, self.panelPloidy + 1)]) + "\n")

		# write genotypes for each individual
		curs = self.cnx.cursor() # open cursor to retrieve genotypes
		for indName in inds:
			# get genotypes
			curs.execute("SELECT genotypes FROM `intDB%s_gt` WHERE ind_id = %s" % (self.panelComboBox.currentText(), indIDlookup[indName]))
			# convert to integers
			if self.panelTypeLabel.text() == "Biallelic":
				# convert to binary 
				blobInts = "".join([format(x, "08b") for x in curs.fetchone()[0]])
				# unpack bitwise into loci and convert to ints representing alt allele copies
				# note we are ignoring padding on the right
				blobInts = [int(blobInts[x:(x + nb)], 2) for x in range(0, len(locusOrder) * nb, nb)] 
			else:
				# convert bytes to ints
				blobInts = [x for x in curs.fetchone()[0]]
			# convert to text representation of alleles
			genoText = []
			if self.panelTypeLabel.text() == "Biallelic":
				# one int for each genotype
				for genoInt, lname in zip(blobInts, locusOrder):
					genoText.extend(altCopiesToGeno(genoInt, revGenoConvertDict[lname], self.panelPloidy))
			elif self.panelTypeLabel.text() == "Multiallelic":
				# one int for each genotype
				for genoInt, lname in zip(blobInts, locusOrder):
					genoText.extend(revGenoConvertDict[lname][genoInt])
			else:
				# one int for each allele
				for lname, start, end in zip(locusOrder, 
								 range(0, len(blobInts), self.panelPloidy), 
								 range(self.panelPloidy, len(blobInts) + 1, self.panelPloidy)):
					for i in range(start, end, 1):
						genoText.append(revGenoConvertDict[lname][blobInts[i]])
			# write out
			if self.fileFormat.currentText() == "2col":
				outFile.write(indName + "\t" + "\t".join(genoText) + "\n")
			elif self.fileFormat.currentText() == "PLINK ped":
				# convert missing to "0"
				genoText = ["0" if x == "" else x for x in genoText]
				# TODO add option to export PLINK format with accurate pedigree
				outFile.write("\t".join([indName, indName, "0", "0", "0", "0"]) + "\t" + "\t".join(genoText) + "\n")
			elif self.fileFormat.currentText() == "long":
				for lname, start, end in zip(locusOrder, range(0, len(genoText), self.panelPloidy), 
								 range(self.panelPloidy, len(genoText) + 1, self.panelPloidy)):
					outFile.write(indName + "\t" + lname + "\t" + "\t".join(genoText[start:end]) + "\n")


		curs.close()
		outFile.close()
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Genotype export")
		messageBox.setText("Genotype export complete")
		messageBox.exec()
		self.close()
