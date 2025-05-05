# import phenotype data window
import mysql.connector as connector
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QComboBox, 
	 QGridLayout, QCheckBox,
	 QFileDialog, QVBoxLayout, QSpinBox, QDialog,
	 QRadioButton, QHBoxLayout, QMessageBox
)
from .utils import (dlgError, 
	indsInPedigree,
	indsInTable, getIndsFromFile, addToPedigree, getIndIDdict,
)

# using QDialog class and exec to block other windows - only one active window at a time
class importPhenoWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Import phenotypes")
		self.cnx = cnx
		self.userInfo = userInfo

		self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
		self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
		self.setMinimumSize(500, 400) # trying to avoid :"Unable to set geometry" warning

		# panel selection dropbox
		self.tableComboBox = QComboBox()
		with cnx.cursor() as curs:
			curs.execute("SELECT table_name FROM intDBpheno_overview")
			tables = [x for x in curs]
		if len(tables) == 0:
			dlgError(parent=self, message="No phenotype tables are defined in the database")
			return
		tables = [x[0] for x in tables]
		self.tableComboBox.addItems(tables)
		self.tableComboBox.currentTextChanged.connect(self.tableSelectionChange)

		# display information in the window about the selected panel
		self.famOrIndLabel = QLabel("") # label of whether table is ind or family
		# storing table information internally for quick reference
		self.ind_col = None
		self.sire_col = None
		self.dam_col = None
		self.dt_col = None
		self.table_description = None
		self.colNames = [] # column names NOT including sire, dam, ind, date(time)
		self.minValue = []
		self.maxValue = []

		# check for new individuals button
		self.checkIndsButton = QPushButton("Check if individuals are in the database")
		self.checkIndsButton.clicked.connect(self.checkNewInds)
		# check for new observations button
		self.checkObsButton = QPushButton("Check if observations are in the database")
		self.checkObsButton.clicked.connect(self.checkNewObservations)


		# check that column names match the selected panel
		self.checkColsButton = QPushButton("Verify column names")
		self.checkColsButton.clicked.connect(self.checkColNames)

		# add new phenotypes or update existing individuals on import radio buttons
		self.addNewRadio = QRadioButton("Add new phenotypes", self)
		self.addNewRadio.setChecked(True) # default is add new individuals
		self.updateRadio = QRadioButton("Update existing phenotypes", self)

		# start import button
		self.importButton = QPushButton("Import phenotypes")
		self.importButton.clicked.connect(self.importPhenotypes)

		# set up layout
		self.gridLayout = QGridLayout()
		self.gridLayout.addWidget(QLabel("Table name"), 0, 0)
		self.gridLayout.addWidget(self.tableComboBox, 0, 1)
		self.gridLayout.addWidget(QLabel("Data type: "), 0, 2)
		self.gridLayout.addWidget(self.famOrIndLabel, 0, 3)


		self.gridLayout.addWidget(self.addNewRadio, 1, 0)
		self.gridLayout.addWidget(self.updateRadio, 1, 1)
		
   		# file selection button and label
		self.selectInputFile = QPushButton("Select input file")
		self.selectInputFile.clicked.connect(self.onClickInputFile)
		self.inputFile = QLabel("")
		self.inputFile.setWordWrap(True)

		# layout for input file button and display of selected file name
		self.fileSelectLayout = QHBoxLayout()
		self.fileSelectLayout.addWidget(self.selectInputFile)
		self.fileSelectLayout.addWidget(self.inputFile)

		# set up action button layout
		self.gridLayout2 = QGridLayout()
		self.gridLayout2.addWidget(self.checkColsButton, 0, 0)
		self.gridLayout2.addWidget(self.checkIndsButton, 1, 0)
		self.gridLayout2.addWidget(self.importButton, 2, 0)

		# add grid layout as top layout in main layout
		self.mainLayout = QVBoxLayout()
		self.mainLayout.addLayout(self.gridLayout)
		self.mainLayout.addLayout(self.fileSelectLayout)
		self.mainLayout.addLayout(self.gridLayout2)
		self.setLayout(self.mainLayout)

		# update labels with values for default selections
		self.tableSelectionChange()


	def tableSelectionChange(self):
		# clear new allele information
		with self.cnx.cursor() as curs:
			curs.execute("SELECT ind_name_col, sire_name_col, dam_name_col, time_obs_col, table_description FROM intDBpheno_overview WHERE table_name = %s", (self.tableComboBox.currentText(),))
			info =[x for x in curs.fetchone()]
			# update variables           
			self.ind_col = info[0]
			self.sire_col = info[1]
			self.dam_col = info[2]
			self.dt_col = info[3]
			self.table_description = info[4]
			if self.ind_col is None:
				self.famOrIndLabel.setText("Family")
			else:
				self.famOrIndLabel.setText("Individual")
			
			# get phenotype column names
			## add column names and descriptions in a scroll area with a splitter?
			## or just have a button to open a window with phenotype descriptions?
			## I think there is no need to display the descriptions here, just get the column names and maybe have a button to show them?
			## descriptions can be viewed in a different function?
			self.colNames = [] # column names NOT including sire, dam, ind, date(time)
			self.minValue = []
			self.maxValue = []
			curs.execute("SELECT pheno_name, min_value, max_value FROM intDBpheno_variableInfo WHERE table_name = '%s'" % self.tableComboBox.currentText())
			for res in curs:
				if res[0] in (self.ind_col, self.sire_col, self.dam_col, self.dt_col):
					continue
				self.colNames += [res[0]]
				self.minValue += [res[1]]
				self.maxValue += [res[2]]

	# open file dialog for user to select an input file
	def onClickInputFile(self):
		tempFile = QFileDialog.getOpenFileName(self, "Select input file", "/home/")[0]
		if tempFile == "":
			return
		self.inputFile.setText(tempFile)
	
	# check if individuals are in the pedigee
	# TODO check this function
	def checkNewInds(self):
		if self.inputFile.text() == "":
			dlgError(parent=self, message="No input file is selected")
			return
		# read header to find out which column(s) have individual names
		with open(self.inputFile.text(), "r") as f:
			h = f.readline().rstrip("\n").split("\t")
			if self.ind_col is None:
				# position of columns to pull names from
				pos = [h.index(self.sire_col), h.index(self.dam_col)]
			else:
				pos = [h.index(self.ind_col)]
			inds = []
			for line in f:
				sep = line.rstrip("\n").split("\t")
				for p in pos:
					inds += [sep[p]]
			# remove any duplicates
			inds = list(set(inds))

			# check if inds are in pedigree
			pedStatus = indsInPedigree(self.cnx, inds)
		
			# show summary message and ask whether to write a report
			writeReportBox = QMessageBox(parent=self)
			writeReportBox.setWindowTitle("Individual check")
			msgTxt = "Of %s total individuals, %s are already in the pedigree. " % (len(inds), len(pedStatus[0]))
			msgTxt += "Write report to " + self.inputFile.text() + "_indReport.txt?"
			writeReportBox.setText(msgTxt)
			writeReportBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
			writeReport = writeReportBox.exec()

			# write report
			if writeReport == QMessageBox.StandardButton.Yes:
				with open(self.inputFile.text() + "_indReport.txt", "w") as fout:
					fout.write("ind\tinPedigree\n") # write header line
					# in pedigree
					for name in pedStatus[0]:
						fout.write("\t".join([name, "TRUE"]) + "\n")
					# not in pedigree
					for name in pedStatus[1]:
						fout.write("\t".join([name, "FALSE"]) + "\n")

	# check if observations (individual and data/time combinations) are in the phenotype table
	# and check for duplicate observations
	def checkNewObservations(self):
		# TODO

	# check column names
	def checkColNames(self, s = None, interact = True):
		if self.inputFile.text() == "":
			dlgError(parent=self, message="No input file is selected")
			return
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


	# import phenotypes
	def importPhenotypes(self):
		if self.inputFile.text() == "":
			dlgError(parent=self, message="No input file is selected")
			return

		if not self.updateRadio.isChecked() and not self.addNewRadio.isChecked():
			dlgError(parent=self, message="You must indicate either add new genotypes or update existing genotypes")
			return
		
		# check if alleles have been validated
		if not hasattr(self, "newAlleles"):
			msgTxt = "You have not checked that the allele values match what is expected. "
			msgTxt += "If there is an unrecognized value, the import will be cancelled and the interface will crash. "
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
		if inds[1] and self.fileFormat.currentText() != "long":
			dlgError(parent=self, message="Duplicate individual names in the input file")
			return
		inds = list(set(inds[0])) # remove duplicates - may be present if long format
		indsInPed = indsInPedigree(self.cnx, inds)

		# make sure all are in the pedigree already if updating genotypes
		if self.updateRadio.isChecked() and len(indsInPed[1]) > 0:
			dlgError(parent=self, message="You are trying to update genotypes but one or more individuals is not in the pedigree")
			return
		
		retValue = addToPedigree(self.cnx, indsInPed[1], sire = None, dam = None)
		if retValue != 0:
			dlgError(parent=self, message="Error trying to add individuals to the pedigree")
			return
		
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
				self.addNewGenos_long(indIDlookup, genoIter, genoConvertDict)
			else:
				self.addNewGenos(indIDlookup, genoIter, genoConvertDict)
		else:
			# update existing genotypes
			self.updateGenos(indIDlookup, genoIter, genoConvertDict)
		
		# commit transaction after all individuals successfully added
		self.cnx.commit()
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Genotype import")
		messageBox.setText("Genotype import complete")
		messageBox.exec()
		self.close()
	
	# add new phenotypes
	def addNewPhenos(self, indIDlookup, genoIter, genoConvertDict):
		# get order that loci need to be in - returns tuple of locus names in order
		locusOrder = getLocusOrderInBlob(self.cnx, self.panelComboBox.currentText())
		# convert tuple to dictionary with key of locus name, value of position (0-based)
		locusOrderDict = {}
		for i in range(0, len(locusOrder)):
			locusOrderDict[locusOrder[i]] = i
		del locusOrder
		with self.cnx.cursor() as curs:
			sqlState = "INSERT INTO `intDB" + self.panelComboBox.currentText() + "_gt` (ind_id, genotypes) VALUES "
			# for each individual, convert input to database representation, and add to database
			for g in genoIter:
				if self.panelTypeLabel.text() == "Biallelic":
					# note that if memory becomes limiting, this can be done in a stream, converting to hex in chunks
					binaryFormatString = "0%sb" % numBits(2, self.panelPloidy)
					# convert to number of alt copies (missing is ploidy + 1) and binary (e.g. "01")
					# initiate with all missing
					altCopies = [self.panelPloidy + 1] * len(locusOrderDict)
					# add genotypes for loci present in the file
					for k, v in g.genoDict.items():
						altCopies[locusOrderDict[k]] = genoToAltCopies(v, genoConvertDict[k])
					# convert to binary
					altCopies = [format(x, binaryFormatString) for x in altCopies]
					# join together into one long string
					altCopies = "".join(altCopies)
					# pad with zeros on the end to make complete bytes
					altCopies += "0" * (8 - (len(altCopies) % 8))
					# convert to hex string 4 digits at a time to make sure we keep all 0s
					# and prevent any issues with large numbers
					hexString = "".join([format(int(altCopies[x:(x+4)], 2), "01x") for x in range(0, len(altCopies), 4)])
					del altCopies # save some memory
				else:
					if self.panelTypeLabel.text() == "Multiallelic":
						# convert the sorted genotype tuple into an integer < 256
						# initiate with all missing
						blobInts = [0] * len(locusOrderDict)
						# add genotypes for loci present in the file
						for k, v in g.genoDict.items():
							blobInts[locusOrderDict[k]] = genoConvertDict[k][v]
					else:
						# Hyperallelic
						# convert the alleles into integers < 256
						# initiate with all missing
						blobInts = [0] * (len(locusOrderDict) * self.panelPloidy)
						# add genotypes for loci present in the file
						for k, v in g.genoDict.items():
							for i in range(0, self.panelPloidy):
								blobInts[(locusOrderDict[k] * self.panelPloidy) + i] = genoConvertDict[k][v[i]]
					# convert ints into hex
					hexString = "".join([format(x, "02x") for x in blobInts])
					del blobInts # save a bit of memory for large panels
				# add to database
				curs.execute(sqlState + "(%s,X'%s')" % (indIDlookup[g.indName], hexString))


	# update phenotypes in database by overwriting existing phenotypes
	def updatePhenos(self, indIDlookup, genoIter, genoConvertDict):
		# get a tuple of locus names in order
		locusOrder = getLocusOrderInBlob(self.cnx, self.panelComboBox.currentText())
		# convert tuple to dictionary with key of locus name, value of position (0-based)
		locusOrderDict = {}
		for i in range(0, len(locusOrder)):
			locusOrderDict[locusOrder[i]] = i
		del locusOrder

		with self.cnx.cursor() as curs:
			sqlState_update = "UPDATE `intDB%s_gt` SET " % self.panelComboBox.currentText()
			if self.panelTypeLabel.text() == "Biallelic":
				# calculate once if needed
				nb = numBits(2, self.panelPloidy)
				binaryFormatString = "0%sb" % nb
			# for each individual, convert input to database representation, and add to database
			for g in genoIter:
				# get existing genotypes as a list of ints
				curs.execute("SELECT genotypes FROM `intDB%s_gt` WHERE ind_id = %s" % (self.panelComboBox.currentText(), indIDlookup[g.indName]))
				if self.panelTypeLabel.text() == "Biallelic":
					# convert to binary 
					blobInts = "".join([format(x, "08b") for x in curs.fetchone()[0]])
					# unpack bitwise into loci and convert to ints
					# note we are ignoring padding on the right, will need to tack on 0s on insert
					blobInts = [int(blobInts[x:(x + nb)], 2) for x in range(0, len(locusOrderDict) * nb, nb)] 
				else:
					# convert bytes to ints
					blobInts = [x for x in curs.fetchone()[0]]
				
				# update with genotypes for loci in g
				if self.panelTypeLabel.text() == "Biallelic":
					for k, v in g.genoDict.items(): # key is locus name, value is tuple of alleles
						blobInts[locusOrderDict[k]] = genoToAltCopies(v, genoConvertDict[k])
					# convert ints to binary
					blobInts = [format(x, binaryFormatString) for x in blobInts]
					# join together into one long string
					blobInts = "".join(blobInts)
					# pad with zeros on the end to make complete bytes
					blobInts += "0" * (8 - (len(blobInts) % 8))
					# convert to hex string 4 digits at a time to make sure we keep all 0s
					# and prevent any issues with large numbers
					hexString = "".join([format(int(blobInts[x:(x+4)], 2), "01x") for x in range(0, len(blobInts), 4)])
					del blobInts # save some memory
				else:
					if self.panelTypeLabel.text() == "Multiallelic":
						for k, v in g.genoDict.items(): # key is locus name, value is tuple of alleles
							blobInts[locusOrderDict[k]] = genoConvertDict[k][v]
					else:
						# Hyperallelic
						for k, v in g.genoDict.items(): # key is locus name, value is tuple of alleles
							for i in range(0, self.panelPloidy):
								blobInts[(locusOrderDict[k] * self.panelPloidy) + i] = genoConvertDict[k][v[i]]
					# convert ints into hex
					hexString = "".join([format(x, "02x") for x in blobInts])
					del blobInts # save a bit of memory for large panels

				# update statement
				curs.execute(sqlState_update + "genotypes=X'%s' WHERE ind_id = %s" % (hexString, indIDlookup[g.indName]))
