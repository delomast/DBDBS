# import genotype data window
import mysql.connector as connector
import re
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
	QMainWindow, QPushButton, QLabel, QLineEdit, QComboBox, 
	 QGridLayout, QWidget, QCheckBox, QInputDialog,
	 QFileDialog, QVBoxLayout, QSpinBox, QTextEdit, QDialog,
	 QRadioButton, QHBoxLayout, QMessageBox
)
from .utils import (dlgError, identifier_syntax_check, getCursLoci, 
	getCursLociAlleles, getConnection, numBits, numGenotypes, indsInPedigree,
	indsInTable, getIndsFromFile, addToPedigree, getIndIDdict, getGenoConvertDict,
	genoToAltCopies, getLocusOrderInBlob
)
from .genotypeFileIterators import *
from itertools import combinations_with_replacement
from statistics import fmean

# using QDialog class and exec to block other windows - only one active window at a time
class importGenoWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Import genotypes")
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

		# allele verify button
		self.alleleVerifyButton = QPushButton("Check that alleles are recognized")
		self.alleleVerifyButton.clicked.connect(self.verifyAlleles)

		# add new alleles button (uses results of alleleVerify)
		self.addNewAllelesButton = QPushButton("Add new alleles")
		self.addNewAllelesButton.clicked.connect(self.addNewAlleles)

		# file selection button and label
		self.selectInputFile = QPushButton("Select input file")
		self.selectInputFile.clicked.connect(self.onClickInputFile)
		self.inputFile = QLabel("")
		self.inputFile.setWordWrap(True)

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
		self.stripA1Checkbox = QCheckBox(r"Drop [\.-_][aA]1")

		# check for new individuals button
		self.checkIndsButton = QPushButton("Check if individuals are in the database")
		self.checkIndsButton.clicked.connect(self.checkNewInds)

		# check that locus names match the selected panel
		self.checkLociButton = QPushButton("Verify locus names")
		self.checkLociButton.clicked.connect(self.checkLociNames)

		# add new genotypes or update existing individuals on import radio buttons
		self.addNewRadio = QRadioButton("Add new genotypes", self)
		self.addNewRadio.setChecked(True) # default is add new individuals
		self.updateRadio = QRadioButton("Update existing genotypes", self)

		# start import button
		self.genoConcordanceButton = QPushButton("Check genotype concordance for updates")
		self.genoConcordanceButton.clicked.connect(self.genoConcordance)

		# batch size spinbox - number of lines to process at once
		self.batchSizeSpinbox = QSpinBox()
		self.batchSizeSpinbox.setRange(1,1000000)
		self.batchSizeSpinbox.setValue(1) # default is one line at a time

		# start import button
		self.importButton = QPushButton("Import genotypes")
		self.importButton.clicked.connect(self.importGenotypes)

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
		self.gridLayout.addWidget(QLabel("Batch size"), 2, 0)
		self.gridLayout.addWidget(self.batchSizeSpinbox, 2, 1)
		self.gridLayout.addWidget(QLabel("Number of loci"), 2, 2)
		self.gridLayout.addWidget(self.panelSizeLabel, 2, 3)
		self.gridLayout.addWidget(self.stripA1Checkbox, 3, 0)
		self.gridLayout.addWidget(self.addNewRadio, 4, 0)
		self.gridLayout.addWidget(self.updateRadio, 4, 1)

		# layout for input file button and display of selected file name
		self.fileSelectLayout = QHBoxLayout()
		self.fileSelectLayout.addWidget(self.selectInputFile)
		self.fileSelectLayout.addWidget(self.inputFile)

		# set up action button layout
		self.gridLayout2 = QGridLayout()
		self.gridLayout2.addWidget(self.checkLociButton, 0, 0)
		self.gridLayout2.addWidget(self.checkIndsButton, 1, 0)
		self.gridLayout2.addWidget(self.alleleVerifyButton, 2, 0)
		self.gridLayout2.addWidget(self.addNewAllelesButton, 2, 1)
		self.gridLayout2.addWidget(self.genoConcordanceButton, 3, 0)
		self.gridLayout2.addWidget(self.importButton, 4, 0)

		# add grid layout as top layout in main layout
		self.mainLayout = QVBoxLayout()
		self.mainLayout.addLayout(self.gridLayout)
		self.mainLayout.addLayout(self.fileSelectLayout)
		self.mainLayout.addLayout(self.gridLayout2)
		self.setLayout(self.mainLayout)

		# update labels with values for default selections
		self.panelSelectionChange() 
		self.changeFormat()


	# input file format specific options
	def changeFormat(self):
		if self.fileFormat.currentText() == "2col":
			self.stripA1Checkbox.setCheckable(True)
			self.stripA1Checkbox.setCheckState(Qt.CheckState.Checked)
		else:
			self.stripA1Checkbox.setCheckable(False)

	# check that alleles are valid
	def verifyAlleles(self):
		# get alleles for each locus defined in panel
		panelAlleles = {} # dict with key of locusName, set of valid alleles
		with self.cnx.cursor() as curs:
			if self.panelTypeLabel.text() == "Multiallelic":
				sqlState = "SELECT DISTINCT panelInfo.intDBlocus_name, lookup.allele_1 FROM `{0}` AS panelInfo LEFT JOIN `intDB{0}_lt` AS lookup ON panelInfo.intDBlocus_id = lookup.locus_id"
			elif self.panelTypeLabel.text() == "Hyperallelic":
				sqlState = "SELECT panelInfo.intDBlocus_name, lookup.allele FROM `{0}` AS panelInfo LEFT JOIN `intDB{0}_lt` AS lookup ON panelInfo.intDBlocus_id = lookup.locus_id"
			elif self.panelTypeLabel.text() == "Biallelic":
				sqlState = "SELECT intDBlocus_name, intDBref_allele, intDBalt_allele FROM `{0}`"
			curs.execute(sqlState.format(self.panelComboBox.currentText()))
			if self.panelTypeLabel.text() == "Biallelic":
				for res in curs:
					panelAlleles[res[0]] = {res[1], res[2]}
			else:
				for res in curs:
					if res[0] in panelAlleles:
						panelAlleles[res[0]].add(res[1])
					elif res[1] is None:
						# checking res[1] b/c locus name is returned in res[0], but alleles are NULL from join
						# this occurs when no alleles have been defined for this locus
						panelAlleles[res[0]] = set()
					else:
						panelAlleles[res[0]] = {res[1]}
		
		# get alleles for each locus in input file
		genoIter = self.getGenoIter()
		inputAlleleDict = {} # key is locus name, value is set() containing alleles
		for g in genoIter:
			for k,v in g.genoDict.items():
				if v.count("") > 0:
					if v.count("") < self.panelPloidy:
						dlgError(parent=self, message="Individual %s has a genotype with a missing allele but not all alleles are missing" % g.indName)
						return
					else:
						continue
				# add alleles to set
				if k not in inputAlleleDict:
					inputAlleleDict[k] = set()
				for al in v:
					inputAlleleDict[k].add(al)
		totalLociInput = len(inputAlleleDict)
		# there shouldn't be any missing genotypes, b/c skipping them above
		# remove missing genotype (empty string) from allele list if present
		# for k in inputAlleleDict:
		# 	inputAlleleDict[k].discard("")

		# remove alleles that are already defined in the panel
		# and save any new ones
		self.newAlleles = {}
		for k,v in inputAlleleDict.items():
			v.difference_update(panelAlleles[k])
			# if new alleles, save them
			if len(v) > 0:
				self.newAlleles[k] = v
		del panelAlleles
		del inputAlleleDict # defensive, b/c will point to some of the same objects as self.newAlleles

		# display summary message and ask about writing a report
		writeReportBox = QMessageBox(parent=self)
		writeReportBox.setWindowTitle("Allele check")
		msgTxt = "Of %s total loci in the input file, %s have new alleles. " % (totalLociInput, len(self.newAlleles))
		msgTxt += "Write report to " + self.inputFile.text() + "_newAlleleReport.txt?"
		writeReportBox.setText(msgTxt)
		writeReportBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
		writeReport = writeReportBox.exec()

		# write report
		if writeReport == QMessageBox.StandardButton.Yes:
			with open(self.inputFile.text() + "_newAlleleReport.txt", "w") as fout:
				fout.write("locus\tnewAlleles\n") # write header line
				for k,v in self.newAlleles.items():
					fout.write(k + "\t" + ",".join(v) + "\n")


	# add new alleles to multi or hyper allelic panel
	def addNewAlleles(self):
		if not hasattr(self, "newAlleles"):
			dlgError(parent=self, message="You must first \"Check that alleles are recognized\" to identify new alleles")
			return
		if self.panelTypeLabel.text() == "Biallelic":
			dlgError(parent=self, message="Cannot add new alleles to loci in a biallelic panel")
			return
		
		with self.cnx.cursor() as curs:
			# for each locus with new alleles
			for locName,newA in self.newAlleles.items():
				# get alleles already defined
				# could speed up by performing once for all loci and splitting and storing locally
				if self.panelTypeLabel.text() == "Multiallelic":
					sqlSub = "allele_1"
				else:
					sqlSub = "allele"
				# get locus_id
				# need to save value for later and may not be in lt if no alleles previously defined
				# so running this as a separate command
				curs.execute("SELECT intDBlocus_id FROM `%s` WHERE intDBlocus_name = '%s'" % (self.panelComboBox.currentText(), locName))
				locus_id = curs.fetchone()[0]
				# get currently defined alleles
				sqlState = "SELECT DISTINCT %s FROM `intDB%s_lt` WHERE locus_id = %s" % (sqlSub, self.panelComboBox.currentText(), locus_id)
				curs.execute(sqlState.format())
				curAlleles = [x[0] for x in curs]
				# check that there is space
				if self.panelTypeLabel.text() == "Multiallelic" and numGenotypes(len(curAlleles) + len(newA), self.panelPloidy) > 255:
					dlgError(parent=self, message="skipping locus %s: %s is too many alleles to be stored in a Multiallelic panel." % (locName, len(curAlleles) + len(newA)))
					continue
				if self.panelTypeLabel.text() == "Hyperallelic" and (len(curAlleles) + len(newA)) > 255:
					dlgError(parent=self, message="skipping locus %s: %s is too many alleles to be stored in a Hyperallelic panel." % (locName, len(curAlleles) + len(newA)))
					continue

				# add
				if self.panelTypeLabel.text() == "Multiallelic":
					colNameString = "(" + ",".join(["locus_id", "genotype_id"] + ["allele_%s" % i for i in range(1, self.panelPloidy + 1)]) + ")"
					sqlState = "INSERT INTO `%s` %s VALUES" % ("intDB" + self.panelComboBox.currentText() + "_lt", colNameString)
					newGeno_id = numGenotypes(len(curAlleles), self.panelPloidy) + 1
					for a in newA:
						for i in range(0, self.panelPloidy):
							copiesNewA = [a for x in range(0, self.panelPloidy - i)]
							genos = [copiesNewA + list(x) for x in combinations_with_replacement(curAlleles, i)]
							for j in range(0, len(genos)):
								genos[j].sort() # make sure alleles in genotypes are sorted
							genos.sort()
							for j in range(0, len(genos)):
								sqlState += "(%s,%s,%s)," % (locus_id, newGeno_id, ",".join(["'%s'" % x for x in genos[j]]))
								newGeno_id += 1
						curAlleles += [a]
					curs.execute(sqlState.rstrip(","))
				else:
					# hyperallelic
					newAllele_id = len(curAlleles) + 1
					sqlState = "INSERT INTO `%s` (locus_id, allele_id, allele) VALUES" % ("intDB" + self.panelComboBox.currentText() + "_lt")
					for a in newA:
						sqlState += " (%s, %s, '%s')," % (locus_id, newAllele_id, a)
						newAllele_id += 1
					curs.execute(sqlState.rstrip(","))
		
		
		msgBox = QMessageBox(parent=self)
		msgBox.setWindowTitle("Add new alleles")
		msgBox.setText("Successfully added new alleles for %s loci." % len(self.newAlleles))
		self.newAlleles = {} # zero out the newAlleles dictionary
		msgBox.exec()

	def panelSelectionChange(self):
		# clear new allele information
		self.clearNewAlleles()
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

	# prevent alleles discovered with one panel being added to a different panel
	def clearNewAlleles(self):
		if hasattr(self, "newAlleles"):
			del self.newAlleles

	# open file dialog for user to select an input file
	def onClickInputFile(self):
		tempFile = QFileDialog.getOpenFileName(self, "Select input file", "/home/")[0]
		if tempFile == "":
			return
		self.inputFile.setText(tempFile)
		self.clearNewAlleles()
	
	# return a genotype iterator
	def getGenoIter(self):
		if self.fileFormat.currentText() == "2col":
			genoIter = genoIter_2col(self.inputFile.text(), self.stripA1Checkbox.isChecked(), self.panelPloidy)
		elif self.fileFormat.currentText() == "PLINK ped":
			genoIter = genoIter_plinkPEDMAP(self.inputFile.text())
		elif self.fileFormat.currentText() == "long":
			genoIter = genoIter_long(self.inputFile.text(), self.batchSizeSpinbox.value())
		else:
			raise Exception("Interal error, not set up for this file format")
		return genoIter

	# check if individuals are 1) in pedigee and 2) in genotype panel
	def checkNewInds(self):
		# get list of inds
		inds = getIndsFromFile(self.inputFile.text(), self.fileFormat.currentText())
		if inds[1]:
			dlgError(parent=self, message="Dupliate individual names in the input file")
			return
		inds = inds[0]
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

	def checkLociNames(self, s = None, interact = True):
		# get locus names from import file
		if self.fileFormat.currentText() == "long":
			h = set()
			with open(self.inputFile.text(), "r") as fileIn:
				header = fileIn.readline()
				for line in fileIn:
					h.add(line.rstrip("\n").split("\t")[1])
		else:
			genoIter = self.getGenoIter()
			h = genoIter.loci
			del genoIter
			oldLen = len(h)
			h = set(h)
			if len(h) < oldLen:
				if interact:
					dlgError(parent=self, message="One or more loci are repeated in the file")
					return
				else:
					return (2,None)
		if len(h) < 1:
			if interact:
				dlgError(parent=self, message="No loci in the file")
				return
			else:
				return (3,None)

		# get locus names from panel
		with self.cnx.cursor() as curs:
			curs.execute("SELECT intDBlocus_name FROM `%s`" % self.panelComboBox.currentText())
			inPanel = set([x[0] for x in curs])

		# loci in panel but not in file
		onlyInPanel = inPanel.difference(h)
		# loci in file but not in panel
		onlyInFile = h.difference(inPanel)

		if interact:
			messageBox = QMessageBox(parent=self)
			messageBox.setWindowTitle("Locus name check")
			if len(onlyInFile) == 0 and len(onlyInPanel) == 0:
				msgTxt = "Locus names in the file match those in the panel. "
			else:
				if len(onlyInFile) > 10 or len(onlyInFile) == 0:
					onlyInFile = [str(len(onlyInFile)) + " loci"]
				if len(onlyInPanel) > 10 or len(onlyInPanel) == 0:
					onlyInPanel = [str(len(onlyInPanel)) + " loci"]
				msgTxt = "%s named only in the file \n\n %s missing from the file" % (",".join(onlyInFile), ",".join(onlyInPanel))
			messageBox.setText(msgTxt)
			messageBox.exec()
			return
		
		if len(onlyInFile) == 0 and len(onlyInPanel) == 0:
			return (0,h)
		elif len(onlyInFile) == 0:
			return (1,h)
		else:
			return (4,h)
	# TODO fix this function
	# check concordance of genotypes in file before updating genotypes of 
	# previously genotyped individuals
	def genoConcordance(self):
		if not self.updateRadio.isChecked():
			dlgError(parent=self, message="This function is only for when you intend to update previously genotyped individuals")
			return
		
		# store values as dictionary with key of ind name
		concorDict = {}

		# get genotype iterator
		genoIter = self.getGenoIter()
		# for each individual
		with self.cnx.cursor() as curs:
			# predefining variables if we know all loci and they stay constant
			if self.fileFormat.currentText() != "long":
				# list column names in order of genoIter.loci
				if self.panelTypeLabel.text() == "Hyperallelic":
					colNames = ["`{0}_a%s`" % i for i in range(1, self.panelPloidy + 1)]
					colNames = [",".join(colNames).format(x) for x in genoIter.loci]
					colNames = ",".join(colNames)
					alleleListDict = getAlleleDict_hyper(self.cnx, self.panelComboBox.currentText(), genoIter.loci, self.panelPloidy)
					missTuple = tuple([0] * self.panelPloidy)
				elif self.panelTypeLabel.text() == "Multiallelic":
					colNames = ",".join(["`" + x + "`" for x in genoIter.loci])
					genoListDict = getGenoDict_multi(self.cnx, self.panelComboBox.currentText(), genoIter.loci, self.panelPloidy)
				else:
					# biallelic
					colNames = ",".join(["`" + x + "` + 0" for x in genoIter.loci]) # + 0 converts binary to integer
					refAltLookup = getRefAlt(self.cnx, self.panelComboBox.currentText(), genoIter.loci)
					missInt = self.panelPloidy + 1 # value for missing genotype
				sqlState = "SELECT %s FROM intDB%s_gt WHERE ind_id = " % (colNames, self.panelComboBox.currentText())

			for g in genoIter:
				# if needed variables are not predefined, we need to define them
				if self.fileFormat.currentText() == "long":
					# list column names in order of loci
					if self.panelTypeLabel.text() == "Hyperallelic":
						colNames = ["`{0}_a%s`" % i for i in range(1, self.panelPloidy + 1)]
						colNames = [",".join(colNames).format(x) for x in g[2]]
						colNames = ",".join(colNames)
						alleleListDict = getAlleleDict_hyper(self.cnx, self.panelComboBox.currentText(), g[2], self.panelPloidy)
						missTuple = tuple([0] * self.panelPloidy)
					elif self.panelTypeLabel.text() == "Multiallelic":
						colNames = ",".join(["`" + x + "`" for x in g[2]])
						genoListDict = getGenoDict_multi(self.cnx, self.panelComboBox.currentText(), g[2], self.panelPloidy)
					else:
						# biallelic
						colNames = ",".join(["`" + x + "` + 0" for x in g[2]]) # + 0 converts binary to integer
						refAltLookup = getRefAlt(self.cnx, self.panelComboBox.currentText(), g[2])
						missInt = self.panelPloidy + 1 # value for missing genotype
					sqlState = "SELECT %s FROM intDB%s_gt WHERE ind_id = " % (colNames, self.panelComboBox.currentText())
				# initiate storage
				# counts in order of:
				# missing in both, missing in database only, missing in import only, genotyped concordant, genotyped non-concordant
				tempList = [0] * 5
				# get indID
				indID = getIndIDdict(self.cnx, [g[0]])
				if len(indID) < 1:
					# ind not in pedigree
					concorDict[g[0]] = [""] * 5
					continue
				# pull genotypes from database
				curs.execute(sqlState + str(indID[g[0]]))
				databaseGenos = next(curs, None)
				if databaseGenos is None:
					# ind not in genotype table
					concorDict[g[0]] = [""] * 5
					continue
				# convert genotypes/alleles to ints and compare
				if self.panelTypeLabel.text() == "Multiallelic":
					# note: we are leaving the genoIDs as integers here, not converting to string
					genoIDs = [genoListDict[i // self.panelPloidy][tuple(sorted(g[1][i:(i+self.panelPloidy)]))] for i in range(0, len(g[1]), self.panelPloidy)]
					for i in range(0, len(genoIDs)):
						if genoIDs[i] == 0 and databaseGenos[i] == 0:
							tempList[0] += 1
						elif databaseGenos[i] == 0:
							tempList[1] += 1
						elif genoIDs[i] == 0:
							tempList[2] += 1
						elif genoIDs[i] == databaseGenos[i]:
							tempList[3] += 1
						else:
							tempList[4] += 1
				elif self.panelTypeLabel.text() == "Hyperallelic":
					# note: we are leaving the alleleIDs as integers here, not converting to string
					alleleIDs = [alleleListDict[i // self.panelPloidy][g[1][i + j]] for i in range(0, len(g[1]), self.panelPloidy) for j in range(0, self.panelPloidy) ]
					for i in range(0, len(databaseGenos), self.panelPloidy):
						# we are comparing alleles and ignoring order
						tempDatabaseGeno = tuple(sorted(databaseGenos[i:(i+self.panelPloidy)]))
						tempFileGeno = tuple(sorted(alleleIDs[i:(i + self.panelPloidy)]))
						if tempFileGeno == missTuple and tempDatabaseGeno == missTuple:
							tempList[0] += 1
						elif tempDatabaseGeno == missTuple:
							tempList[1] += 1
						elif tempFileGeno == missTuple:
							tempList[2] += 1
						elif tempFileGeno == tempDatabaseGeno:
							tempList[3] += 1
						else:
							tempList[4] += 1
				else:
					# biallelic
					# convert to number of alt copies as integers
					genoAltCopies = [genoToAltCopies(g[1][i:(i+self.panelPloidy)], refAltLookup[i // self.panelPloidy]) for i in range(0, len(g[1]), self.panelPloidy)]
					for i in range(0, len(genoAltCopies)):
						if genoAltCopies[i] == missInt and databaseGenos[i] == missInt:
							tempList[0] += 1
						elif databaseGenos[i] == missInt:
							tempList[1] += 1
						elif genoAltCopies[i] == missInt:
							tempList[2] += 1
						elif genoAltCopies[i] == databaseGenos[i]:
							tempList[3] += 1
						else:
							tempList[4] += 1

				# save to output dict and running total
				if self.fileFormat.currentText() == "long" and g[0] in concorDict:
					# if already seen this individual, add to the totals
					for i in range(0, len(tempList)):
						concorDict[g[0]][i] += tempList[i]
				else:
					concorDict[g[0]] = [x for x in tempList] # using list comprehension b/c we want to make a copy, not a reference
			
		# give summary and optionally write report
		# calc summary stats
		minlist = ["NA"] * 5
		meanlist = ["NA"] * 5
		maxlist = ["NA"] * 5
		for i in range(0, 5):
			tempVal = [v[i] for v in concorDict.values() if v[i] != ""]
			if len(tempVal) < 1:
				break
			minlist[i] = min(tempVal)
			meanlist[i] = fmean(tempVal)
			maxlist[i] = max(tempVal)
		stringSubList = [len(tempVal)]
		for i in range(0, 5):
			stringSubList += [minlist[i]]
			stringSubList += [meanlist[i]]
			stringSubList += [maxlist[i]]

		writeReportBox = QMessageBox(parent=self)
		writeReportBox.setWindowTitle("Concordance check")
		msgTxt = "Min, Mean, and Max number of genotypes for %s total individuals in the file and genotype table\n"
		msgTxt += "Missing in both: %s, %s, %s\n"
		msgTxt += "Missing in database only: %s, %s, %s\n"
		msgTxt += "Missing in import file only: %s, %s, %s\n"
		msgTxt += "Genotypes concordant: %s, %s, %s\n"
		msgTxt += "Genotypes non-concordant: %s, %s, %s\n\n"
		msgTxt += "Write report to " + self.inputFile.text() + "_concordanceReport.txt?"
		writeReportBox.setText(msgTxt % tuple(stringSubList))
		writeReportBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
		writeReport = writeReportBox.exec()

		# write report
		if writeReport == QMessageBox.StandardButton.Yes:
			with open(self.inputFile.text() + "_concordanceReport.txt", "w") as fout:
				fout.write("\t".join(["ind", "missBoth", "missDatabase", "missImportFile", "concordant", "nonConcordant"]) + "\n") # write header line
				# in both
				for k, v in concorDict.items():
					fout.write(k + "\t" + "\t".join([str(x) for x in v]) + "\n")
		
		# TODO
		# figure out read/write of BLOB with python connector
		# convert system to working with BLOB of genotypes

		# move on to genotype export





	# import genotypes
	def importGenotypes(self):
		if not self.updateRadio.isChecked() and not self.addNewRadio.isChecked():
			dlgError(parent=self, message="You must indicate either add new genotypes or update existing genotypes")
			return
		
		# check if alleles have been validated
		if not hasattr(self, "newAlleles"):
			msgTxt = "You have not checked that the allele values match what is expected. "
			msgTxt += "If there is an unrecognized value, the import will only be partially executed and the interface will crash. "
			msgTxt += "Do you want to proceed?"
			askBox = QMessageBox(parent=self)
			askBox.setWindowTitle("Confirm proceed")
			askBox.setText(msgTxt)
			askBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
			proceed = askBox.exec()
			if proceed == QMessageBox.StandardButton.No:
				return
		elif len(self.newAlleles) > 0:
			dlgError(parent=self, message="Unrecognized alleles were found when you ran \"Check that alleles are recognized\" and have not been added to the panel.")
			return

		# make sure all loci (and no extras) are present
		tempCheck, allLociInFile = self.checkLociNames(interact = False)
		if  tempCheck > 1:
			dlgError(parent=self, message="Problem with locus names. Run \"Verify locus names\"")
			return
		elif tempCheck == 1:
			# file does not contain all loci
			askBox = QMessageBox(parent=self)
			askBox.setWindowTitle("Confirm proceed")
			if self.addNewRadio.isChecked():
				askBox.setText("One or more loci in the panel are missing from the input file. Genotypes for the missing loci will be saved as missing genotypes. Do you want to proceed with the import?")
			else:
				askBox.setText("One or more loci in the panel are missing from the input file. Genotypes for the missing loci will not be updated. Do you want to proceed with the import?")
			askBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
			proceed = askBox.exec()
			if proceed == QMessageBox.StandardButton.No:
				return
		
		# check for duplicate inds and add inds to pedigree if needed
		inds = getIndsFromFile(self.inputFile.text(), self.fileFormat.currentText())
		if inds[1]:
			dlgError(parent=self, message="Duplicate individual names in the input file")
			return
		inds = inds[0]
		indsInPed = indsInPedigree(self.cnx, inds)

		# make sure all are in the pedigree already if updating genotypes
		if self.updateRadio.isChecked() and len(indsInPed[1]) > 0:
			dlgError(parent=self, message="You are trying to update genotypes but one or more individuals is not in the pedigree")
			return
		
		retValue = addToPedigree(self.cnx, indsInPed[1], sire = None, dam = None)
		if retValue != 0:
			raise Exception("Internal error") 
		
		# check for presence of individuals in the genotype table
		tableCheck = indsInTable(self.cnx, inds, "intDB" + self.panelComboBox.currentText() + "_gt")
		if self.addNewRadio.isChecked() and len(tableCheck[0]) > 0:
			dlgError(parent=self, message="You are trying to add new genotypes but one or more individuals is already in the genotype table")
			return
		elif self.updateRadio.isChecked() and len(tableCheck[1]) > 0:
			dlgError(parent=self, message="You are trying to update genotypes but one or more individuals is not already in the genotype table")
			return
		
		# build dictionary of ind names and ind_id
		indIDlookup = getIndIDdict(self.cnx, inds)

		# build dictionary of key = locus name, 
		# value = dict with key = genotype/allele, value of genotype/allele id
		# OR
		# value = tuple(ref allele, alt allele)
		genoConvertDict = getGenoConvertDict(self.cnx, self.panelComboBox.currentText(), allLociInFile)
		
		# initiate iterator for selected file type
		genoIter = self.getGenoIter()

		if self.addNewRadio.isChecked():
			# add new genotypes
			if self.fileFormat.currentText() == "long":
				self.addNewGenos_long(indIDlookup, genoIter)
			else:
				self.addNewGenos(indIDlookup, genoIter, genoConvertDict)
		else:
			# update existing genotypes
			self.updateGenos(indIDlookup, genoIter)
		
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Genotype import")
		messageBox.setText("Genotype import complete")
		messageBox.exec()
		self.close()
	
	# add new genotypes
	def addNewGenos(self, indIDlookup, genoIter, genoConvertDict):
		# get order that loci need to be in - returns tuple of locus names in order
		locusOrder = getLocusOrderInBlob(self.cnx, self.panelComboBox.currentText())
		with self.cnx.cursor() as curs:
			sqlState = "INSERT INTO `intDB" + self.panelComboBox.currentText() + "_gt` (ind_id, genotypes) VALUES "
			# for each individual, convert input to database representation, and add to database
			for g in genoIter:
				if self.panelTypeLabel.text() == "Biallelic":
					# note that if memory becomes limiting, this can be done in a stream, converting to hex in chunks
					binaryFormatString = "0%sb" % numBits(2, self.panelPloidy)
					# convert to number of alt copies (missing is ploidy + 1) and binary (e.g. "01")
					altCopies = [format(genoToAltCopies(g.genoDict[lname], genoConvertDict[lname]), binaryFormatString) for lname in locusOrder]
					# join together into one long string
					altCopies = "".join(altCopies)
					# pad with zeros on the end to make an even number of bytes
					altCopies += "0" * (8 - (len(altCopies) % 8))
					# convert to hex string 4 digits at a time to make sure we keep all 0s
					hexString = "".join([format(int(altCopies[x:(x+4)], 2), "01x") for x in range(0, len(altCopies), 4)])
					del altCopies # save some memory
				else:
					if self.panelTypeLabel.text() == "Multiallelic":
						# convert the sorted genotype tuple into an integer < 256
						blobInts = [genoConvertDict[lname][g.genoDict[lname]] for lname in locusOrder]
					else:
						# Hyperallelic
						# convert the alleles into integers < 256
						blobInts = [genoConvertDict[lname][g.genoDict[lname][x]] for lname in locusOrder for x in range(0, self.panelPloidy)]
					# convert ints into hex
					hexString = "".join([format(x, "02x") for x in blobInts])
					del blobInts # save a bit of memory for large panels
				# add to database
				curs.execute(sqlState + "(%s,X'%s')" % (indIDlookup[g.indName], hexString))
		
		# commit transaction after all individuals successfully added
		self.cnx.commit()
	# TODO left off here after testing import
	def addNewGenos_long(self, indIDlookup, genoIter):

		## if long and ind has been seen before, pull existing and update
		## if long, add to seen before list
		## if long and seen before, update instead of insert



		# add new genotypes
		with self.cnx.cursor() as curs:
			sqlState = "INSERT INTO `intDB" + self.panelComboBox.currentText() + "_gt` (%s) VALUES "
			# the big list comprehensions here are a bit of a pain to read, but they are expected to run much faster than when split into for loops 
			if self.panelTypeLabel.text() == "Multiallelic":
				for g in genoIter:
					# define variables b/c loci change between iterations
					genoListDict = getGenoDict_multi(self.cnx, self.panelComboBox.currentText(), g[2], self.panelPloidy)
					colNames = "ind_id," + ",".join(["`%s`" % x for x in g[2]])
					sqlState_long = sqlState % colNames
					# change alleles to genotype codes
					# have to sort alleles and then convert to tuple (b/c lists aren't hashable) for lookup
					# then convert to str for the next line
					genoIDs = [str(genoListDict[i // self.panelPloidy][tuple(sorted(g[1][i:(i+self.panelPloidy)]))]) for i in range(0, len(g[1]), self.panelPloidy)]
					# add ind_id, genotype_id(s) to table
					sqlState_long += "(%s,%s)" % (indIDlookup[g[0]], ",".join(genoIDs))
					sqlState_long += " ON DUPLICATE KEY UPDATE"
					for i in range(0, len(genoIDs)):
						sqlState_long += " " + g[2][i] + "=" + genoIDs[i] + ","
					curs.execute(sqlState_long.rstrip(","))
			elif self.panelTypeLabel.text() == "Hyperallelic":
				alleleNameStrings = ["`{0}_a%s`" % i for i in range(1, self.panelPloidy + 1)]
				for g in genoIter:
					# define variables b/c loci change between iterations
					alleleListDict = getAlleleDict_hyper(self.cnx, self.panelComboBox.currentText(), g[2], self.panelPloidy)
					alleleColumns = [x.format(y) for y in g[2] for x in alleleNameStrings]
					sqlState_long = sqlState % ("ind_id," + ",".join(alleleColumns))
					# change alleles to allele codes
					# convert to str for the next line
					# list comprehension equivalent to nested for loop for i in: for j in: list += [allele[i][g[1][i+j]]]
					alleleIDs = [str(alleleListDict[i // self.panelPloidy][g[1][i + j]]) for i in range(0, len(g[1]), self.panelPloidy) for j in range(0, self.panelPloidy) ]
					sqlState_long += "(%s,%s)" % (indIDlookup[g[0]], ",".join(alleleIDs))
					sqlState_long += " ON DUPLICATE KEY UPDATE"
					for i in range(0, len(alleleColumns)):
						sqlState_long += " " + alleleColumns[i] + "=" + alleleIDs[i] + ","
					curs.execute(sqlState_long.rstrip(","))
			else:
				# biallelic
				# generate format string with matching number of binary digits
				binaryFormatString = "0%sb" % numBits(2, self.panelPloidy)
				for g in genoIter:
					# list in order of g[2], values are tuple (refAllele, altAllele)
					refAltLookup = getRefAlt(self.cnx, self.panelComboBox.currentText(), g[2])
					colNames = "ind_id," + ",".join(["`" + x + "`" for x in g[2]])
					sqlState_long = sqlState % colNames
					# change alleles to bit code
					genoBitCodes = ["b'" + format(genoToAltCopies(g[1][i:(i+self.panelPloidy)], refAltLookup[i // self.panelPloidy]), binaryFormatString) + "'" for i in range(0, len(g[1]), self.panelPloidy)]
					sqlState_long += "(%s,%s)" % (indIDlookup[g[0]], ",".join(genoBitCodes))
					sqlState_long += " ON DUPLICATE KEY UPDATE"
					for i in range(0, len(genoBitCodes)):
						sqlState_long += " " + g[2][i] + "=" + genoBitCodes[i] + ","
					curs.execute(sqlState_long.rstrip(","))
	# left off adding long format here
	def updateGenos(self, indIDlookup, genoIter):
		# overwrite existing genotypes
		with self.cnx.cursor() as curs:
			sqlState = "UPDATE `intDB%s_gt` SET " % self.panelComboBox.currentText()
			# the big list comprehensions here are a bit of a pain to read, but they are expected to run much faster than when split into for loops 
			if self.panelTypeLabel.text() == "Multiallelic":
				# list in order of genoIter.loci, values are dict[(allele_1,allele_2,...)] = genotype_id
				genoListDict = getGenoDict_multi(self.cnx, self.panelComboBox.currentText(), genoIter.loci, self.panelPloidy)
				for g in genoIter:
					# change alleles to genotype codes
					# have to sort alleles and then convert to tuple (b/c lists aren't hashable) for lookup
					# then convert to str for the next line
					genoIDs = [str(genoListDict[i // self.panelPloidy][tuple(sorted(g[1][i:(i+self.panelPloidy)]))]) for i in range(0, len(g[1]), self.panelPloidy)]
					# build long SET section of the statement
					# add WHERE statement (VERY important, otherwise all rows are overwritten)
					# update table
					curs.execute(sqlState + ",".join(["`" + genoIter.loci[i] + "`" + "=" + genoIDs[i] for i in range(0, len(genoIDs))]) + (" WHERE ind_id = %s" % indIDlookup[g[0]]))
			elif self.panelTypeLabel.text() == "Hyperallelic":
				# list in order of genoIter.loci
				alleleListDict = getAlleleDict_hyper(self.cnx, self.panelComboBox.currentText(), genoIter.loci, self.panelPloidy)
				setState = ["`{0}_a%s`=" % i for i in range(1, self.panelPloidy + 1)]
				setState = [x.format(locus) for locus in genoIter.loci for x in setState]
				for g in genoIter:
					# change alleles to allele codes
					# convert to str for the next line
					# list comprehension equivalent to nested for loop for i in: for j in: list += [allele[i//ploidy][g[1][i+j]]]
					alleleIDs = [str(alleleListDict[i // self.panelPloidy][g[1][i + j]]) for i in range(0, len(g[1]), self.panelPloidy) for j in range(0, self.panelPloidy) ]
					curs.execute(sqlState + ",".join([setState[i] + alleleIDs[i] for i in range(0, len(alleleIDs))]) + (" WHERE ind_id = %s" % indIDlookup[g[0]]))
			else:
				# biallelic
				# list in order of genoIter.loci, values are tuple (refAllele, altAllele)
				refAltLookup = getRefAlt(self.cnx, self.panelComboBox.currentText(), genoIter.loci)
				# generate format string with matching number of binary digits
				binaryFormatString = "0%sb" % numBits(2, self.panelPloidy)
				for g in genoIter:
					# change genotypes to bit code
					genoBitCodes = ["b'" + format(genoToAltCopies(g[1][i:(i+self.panelPloidy)], refAltLookup[i // self.panelPloidy]), binaryFormatString) + "'" for i in range(0, len(g[1]), self.panelPloidy)]
					curs.execute(sqlState + ",".join(["`" + genoIter.loci[i] + "`" + "=" + genoBitCodes[i] for i in range(0, len(genoBitCodes))]) + (" WHERE ind_id = %s" % indIDlookup[g[0]]))
