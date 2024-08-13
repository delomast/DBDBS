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
from .utils import (dlgError, countEqual, identifier_syntax_check, getCursLoci, 
	getCursLociAlleles, getConnection, numBits, numGenotypes, indsInPedigree,
	indsInTable, getIndsFromFile, addToPedigree, getIndIDdict, getGenoDict_multi,
	getAlleleDict_hyper
)
from .genotypeFileIterators import *
from itertools import combinations_with_replacement

# using QDialog class and exec to block other windows - only one active window at a time
class importGenoWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Import genotypes")
		self.cnx = cnx
		self.userInfo = userInfo

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
		# 2col: tab-delimited, 2 column per call
		# first col is individual name
		# with header line
		# locus names pulled from header for first column, optionally stripping [\.-_][aA]1
		self.fileFormat.addItems(["2col", "PLINK ped and map", "formatotro"])
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
		self.gridLayout2.addWidget(self.alleleVerifyButton, 0, 0)
		self.gridLayout2.addWidget(self.addNewAllelesButton, 0, 1)
		self.gridLayout2.addWidget(self.checkIndsButton, 1, 0)
		self.gridLayout2.addWidget(self.checkLociButton, 2, 0)
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
						# this occurs when no alleles have been defined for this locus
						panelAlleles[res[0]] = set()
					else:
						panelAlleles[res[0]] = {res[1]}

		# get alleles for each locus in input file
		genoIter = self.getGenoIter()
		h = genoIter.loci
		# list of sets, one set for each locus, in same order as locus names in h
		inputAlleles = [set() for x in range(0, len(h))]
		for g in genoIter:
			for i in range(0, len(inputAlleles)):
				for j in range(0, self.panelPloidy):
					inputAlleles[i].add(g[1][j + (i*self.panelPloidy)])

		# remove alleles that are already defined in the panel
		# and save any new ones
		self.newAlleles = {}
		for i in range(0, len(inputAlleles)):
			inputAlleles[i].difference_update(panelAlleles[h[i]])
			# if new alleles, save them
			if len(inputAlleles[i]) > 0:
				self.newAlleles[h[i]] = inputAlleles[i]

		# display summary message and ask about writing a report
		writeReportBox = QMessageBox(parent=self)
		writeReportBox.setWindowTitle("Allele check")
		msgTxt = "Of %s total loci, %s have new alleles. " % (len(h), len(self.newAlleles))
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
		else:
			raise Exception("Interal error, not set up for this file format")
		return genoIter

	# check if individuals are 1) in pedigee an 2) in genotype panel
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
			genoStatus = indsInTable(self.cnx, pedStatus[0], self.panelComboBox.currentText())
		
		# show summary message and ask whether to write a report
		writeReportBox = QMessageBox(parent=self)
		writeReportBox.setWindowTitle("Individual check")
		msgTxt = "Of %s total individuals, %s are already in the pedigree and %s are already in the genotype panel. " % \
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
		genoIter = self.getGenoIter()
		h = genoIter.loci
		del genoIter
		if len(h) < 1:
			if interact:
				dlgError(parent=self, message="No loci in the file")
				return
			else:
				return 3
		oldLen = len(h)
		h = set(h)
		if len(h) < oldLen:
			if interact:
				dlgError(parent=self, message="One or more loci are repeated in the file")
				return
			else:
				return 2
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
			return 0
		else:
			return 1
	
	# check concordance of genotypes in file before updating genotypes of 
	# previously genotyped individuals
	def genoConcordance(self):
		if not self.updateRadio.isChecked():
			dlgError(parent=self, message="This function is only for when you intend to update previously genotyped individuals")
			return
		if self.fileFormat.currentText() == "2col":
			pass
			# TODO
			# get locus names

			# for each individual
			# pull genotypes from file

			# pull genotypes from database

			# compare
			# missing to non-missing

			# non-missing to missing

			# proportion of alleles in common 



	# import genotypes
	def importGenotypes(self):
		# make sure all loci (and no extras) are present
		if self.checkLociNames(interact = False) != 0:
			dlgError(parent=self, message="Problem with locus names. Run \"Verify locus names\"")
		
		# check for duplicate inds and add inds to pedigree if needed
		inds = getIndsFromFile(self.inputFile.text(), self.fileFormat.currentText())
		if inds[1]:
			dlgError(parent=self, message="Dupliate individual names in the input file")
			return
		inds = inds[0]
		indsInPed = indsInPedigree(self.cnx, inds)
		retValue = addToPedigree(self.cnx, indsInPed[1], sire = None, dam = None)
		if retValue != 0:
			raise Exception("Internal error")

		# build dictionary of ind names and ind_id
		indIDlookup = getIndIDdict(self.cnx, inds)
		
		# initiate iterator for selected file type
		genoIter = self.getGenoIter()
		
		# add new genotypes
		with self.cnx.cursor() as curs:
			if self.panelTypeLabel.text() == "Multiallelic":
				# list in order of genoIter.loci, values are dict[(allele_1,allele_2,...)] = genotype_id
				genoListDict = getGenoDict_multi(self.cnx, self.panelComboBox.currentText(), genoIter.loci, self.panelPloidy)
				colNames = "ind_id," + ",".join(["`%s`" % x for x in genoIter.loci])
				sqlState = "INSERT INTO `intDB%s_gt` (%s) VALUES " % (self.panelComboBox.currentText(), colNames)
				for g in genoIter:
					# change alleles to genotype codes
					# have to sort and then convert to tuple (b/c lists aren't hashable)
					# then convert to str for .join in the next line
					genoIDs = [str(genoListDict[i // self.panelPloidy][tuple(sorted(g[1][i:(i+self.panelPloidy)]))]) for i in range(0, len(g[1]), self.panelPloidy)]
					# add ind_id, genotype_id(s) to table
					curs.execute(sqlState + "(%s,%s)" % (indIDlookup[g[0]], ",".join(genoIDs)))
			elif self.panelTypeLabel.text() == "Hyperallelic":
				# list in order of genoIter.loci
				alleleListDict = getAlleleDict_hyper(self.cnx, self.panelComboBox.currentText(), genoIter.loci, self.panelPloidy)
				colNames = ["`{0}_a%s`" % i for i in range(1, self.panelPloidy + 1)]
				colNames = [",".join(colNames).format(x) for x in genoIter.loci]
				colNames = "ind_id," + ",".join(colNames)
				sqlState = "INSERT INTO intDB%s_gt (%s) VALUES " % (self.panelComboBox.currentText(), colNames)
				for g in genoIter:
					# change alleles to allele codes
					# convert to str for .join in next line
					# list comprehension equivalent to nested for loop for i in: for j in: list += [allele[i][g[1][i+j]]]
					alleleIDs = [str(alleleListDict[i // self.panelPloidy][g[1][i + j]]) for i in range(0, len(g[1]), self.panelPloidy) for j in range(0, self.panelPloidy) ]
					curs.execute(sqlState + "(%s,%s)" % (indIDlookup[g[0]], ",".join(alleleIDs)))
			else:
				# biallelic
				
				pass
		
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Genotype import")
		messageBox.setText("Genotype import complete")
		messageBox.exec()
		self.close()

		### updating genotypes
		###### different function - can skip pedigree check

	
