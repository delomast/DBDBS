# make a new panel window
import mysql.connector as connector
import re
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QLineEdit, QComboBox, 
	 QGridLayout, 
	 QFileDialog, QVBoxLayout, QSpinBox, QTextEdit, QDialog
)
from .utils import (dlgError, countEqual, identifier_syntax_check, getCursLoci, 
	getCursLociAlleles, getConnection, numBits, numGenotypes, removePartialPanel
)
from collections import deque
from itertools import combinations_with_replacement

# using QDialog class and exec to block other windows - only one active window at a time
class newPanelWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Make new panel")
		self.cnx = cnx
		self.userInfo = userInfo

		# panel type, name, etc (info from user)
		self.panelTypeBox = QComboBox()
		self.panelTypeBox.addItems(["Biallelic", "Multiallelic", "Hyperallelic"])
		self.panelTypeBox.currentTextChanged.connect(self.onTypeChange)
		self.panelNameBox = QLineEdit()
		self.selectDefFile = QPushButton("Select definition file")
		self.selectDefFile.clicked.connect(self.onClickDefFile)
		self.curFileSelected = QLabel("")
		self.ploidySpinnerBox = QSpinBox()
		self.ploidySpinnerBox.setRange(1, 255) # limited by TINYINT UNSIGNED in lookup table for alt allele copies
		self.ploidySpinnerBox.setValue(2) # default is diploid
		self.batchSizeSpinnerBox = QSpinBox() # number of loci to process at once (higher = faster and more memory)
		self.batchSizeSpinnerBox.setRange(1, 100000000)
		self.batchSizeSpinnerBox.setValue(100000) # default is 100000
		self.panelDescBox = QTextEdit()
		self.panelDescBox.setAcceptRichText(False)

		self.gridLayout = QGridLayout()
		self.inputLabels = ["Panel type", "Panel name", "Ploidy", "Panel description", "Batch size"]
		for i in range(0, len(self.inputLabels)):
			self.gridLayout.addWidget(QLabel(self.inputLabels[i]), i, 0)
		self.gridLayout.addWidget(self.panelTypeBox, 0, 1)
		self.gridLayout.addWidget(self.panelNameBox, 1, 1)
		self.gridLayout.addWidget(self.ploidySpinnerBox, 2, 1)
		self.gridLayout.addWidget(self.panelDescBox, 3, 1)
		self.gridLayout.addWidget(self.batchSizeSpinnerBox, 4, 1)
		self.gridLayout.addWidget(self.selectDefFile, 5, 0)
		self.gridLayout.addWidget(self.curFileSelected, 5, 1)
		
		# add main selection items as top layout in main layout
		self.mainLayout = QVBoxLayout()
		self.mainLayout.addLayout(self.gridLayout)
		self.setLayout(self.mainLayout)

	def onClickDefFile(self):
		tempFile = QFileDialog.getOpenFileName(self, "Select panel definition file", "/home/")[0]
		if tempFile == "":
			return
		self.panelDefFile = tempFile
		self.curFileSelected.setText(self.panelDefFile)
		# read in header line
		with open(self.panelDefFile, "r") as f:
			h = f.readline()
		if h:
			h = h.rstrip("\n").split("\t")
		else:
			dlgError(self, "Error: Could not read specified file")
			return
		# delete old widgets if present
		if hasattr(self, "columnType_comboboxes"):
			for i in range(0, len(self.columnType_comboboxes)):
				self.columnType_comboboxes[i].setParent(None)
				self.columnType_labels[i].setParent(None)
		# make combobox selection and label for each column
		self.columnType_comboboxes = []
		self.columnType_labels = []
		self.columnType_subLayout = QGridLayout()
		for i in range(0, len(h)):
			self.columnType_comboboxes += [QComboBox()]
			self.columnType_comboboxes[i].addItems(self.getValidColumnTypes())
			self.columnType_labels += [QLabel(h[i])]
			# add to layout
			self.columnType_subLayout.addWidget(self.columnType_labels[i], i, 0)
			self.columnType_subLayout.addWidget(self.columnType_comboboxes[i], i, 1)
		# add sublayout to main layout
		self.mainLayout.addLayout(self.columnType_subLayout)

		# create submit button
		# only create after a file is selected, don't create more than once
		if not hasattr(self, "submitPanel_button"):
			self.submitPanel_button = QPushButton("Add new panel")
			self.submitPanel_button.clicked.connect(self.onSubmit)
			self.gridLayout.addWidget(self.submitPanel_button, len(self.inputLabels) + 1, 1)

	def onTypeChange(self):
		if hasattr(self, "columnType_comboboxes"):
			for i in range(0, len(self.columnType_comboboxes)):
				self.columnType_comboboxes[i].clear()
				self.columnType_comboboxes[i].addItems(self.getValidColumnTypes())
	
	def getValidColumnTypes(self):
		if self.panelTypeBox.currentText() == "Biallelic":
			validTypes = ["Locus name", "Ref allele", "Alt allele"]
		else:
			validTypes = ["Locus name", "Alleles"]
		validTypes += ["VARCHAR", "INTEGER", "DOUBLE", "DATE", "TEXT"]
		return(validTypes)
	
	def onSubmit(self):
		# input error checks
		if not identifier_syntax_check(self.panelNameBox.text()):
			dlgError(parent=self, message="Invalid panel name")
			return
		colItems = [self.columnType_comboboxes[i].currentText() for i in range(0, len(self.columnType_comboboxes))]
		if countEqual(colItems, "Locus name") != 1:
			dlgError(self, "(Only) One column must be \"Locus name\"")
			return
		if self.panelTypeBox.currentText() == "Biallelic":
			if countEqual(colItems, "Ref allele") != 1:
				dlgError(self, "(Only) One column must be \"Ref allele\"")
				return
			if countEqual(colItems, "Alt allele") != 1:
				dlgError(self, "(Only) One column must be \"Alt allele\"")
				return
		else:
			if countEqual(colItems, "Alleles") > 1:
				dlgError(self, "You cannot have more than one column of \"Alleles\"")
				return
		with self.cnx.cursor() as curs:
			curs.execute("SHOW TABLES")
			for x in curs:
				if x[0] == self.panelNameBox.text():
					self.cnx.consume_results()
					dlgError(parent=self, message="A table with that name already exists, please pick a different panel name")
					return
		
		# set maxBatchSize for easy referencing
		self.maxBatchSize = self.batchSizeSpinnerBox.value()

		# detect varchar sizes and more input checks
		# this does NOT check whether locus names are unique
		# this is not done b/c it would require storing all names in memory
		colNames = [x.text() for x in self.columnType_labels]
		colTypes = [x.currentText() for x in self.columnType_comboboxes]
		vChar = [i for i in range(0,len(colTypes)) if colTypes[i] in ("Locus name", "VARCHAR", "Alt allele", "Ref allele", "Alleles")]
		locName_pos = [i for i in range(0,len(colTypes)) if colTypes[i] == "Locus name"][0]
		toCheck_pos = [i for i in range(0,len(colTypes)) if colTypes[i] in ("Alt allele", "Ref allele", "Alleles")]
		maxLen = [0] * len(vChar)
		locusCount = 0 # number of loci in panel
		with open(self.panelDefFile, "r") as f:
			line = f.readline() # skip header
			line = f.readline()
			while line:
				line = line.rstrip("\n").split("\t")
				locusCount += 1
				for i in range(0, len(vChar)):
					if len(line[vChar[i]]) > maxLen[i]:
						maxLen[i] = len(line[vChar[i]])
				# make sure locus names are valid identifiers
				if not identifier_syntax_check(line[locName_pos]):
					dlgError(parent=self, message="Locus \"%s\" has an invalid name" % line[locName_pos])
					return
				# Make sure alt allele, ref allele, and alleles are valid values, if present (no whitespace, unique)
				for j in toCheck_pos:
					if re.search(r"\s", line[j]):
						dlgError(parent=self, message="Locus \"%s\" has an invalid value (contains whitespace) for %s" % (line[locName_pos], colTypes[j]))
						return
				if len(toCheck_pos) == 2:
					# ref and alt
					if line[toCheck_pos[0]] == line[toCheck_pos[1]]:
						dlgError(parent=self, message="Locus \"%s\" has the same ref and alt allele" % line[locName_pos])
						return
					elif line[toCheck_pos[0]] == "" or line[toCheck_pos[1]] == "":
						dlgError(parent=self, message="Locus \"%s\" is missing either a ref or an alt allele" % line[locName_pos])
						return
				elif len(toCheck_pos) == 1:
					# alleles
					alleles = line[toCheck_pos[0]].split(",")
					if len(alleles) > len(set(alleles)):
						dlgError(parent=self, message="Locus \"%s\" has the same allele listed more than once" % line[locName_pos])
						return
				line = f.readline()
		# make sure user defined columns have valid names
		for i in range(0, len(colNames)):
			if colTypes[i] not in ("Locus name", "Alt allele", "Ref allele", "Alleles"):
				if not identifier_syntax_check(colNames[i]):
					dlgError(parent=self, message="\"%s\" is an invalid column name" % colNames[i])
					return
				
		# add panel to database
		maxLen = deque(maxLen) # for efficient pop from left
		# build sql statement and value insert string
		sqlState = "CREATE TABLE `%s` (intDBlocus_id INTEGER UNSIGNED PRIMARY KEY AUTO_INCREMENT," % self.panelNameBox.text()
		insertString = "("
		for i in range(0, len(colTypes)):
			if i > 0:
				sqlState += ", "
				insertString += ","

			if colTypes[i] == "Locus name":
				sqlState += "intDBlocus_name VARCHAR(%s) UNIQUE NOT NULL" % maxLen.popleft()
				colNames[i] = "intDBlocus_name" # recode column names
			elif colTypes[i] == "Ref allele":
				if maxLen[0] == 1: # save a bit of memory if all are one character long
					tempVarType = "CHAR"
				else:
					tempVarType = "VARCHAR"
				sqlState += "intDBref_allele %s(%s) NOT NULL" % (tempVarType, maxLen.popleft())
				colNames[i] = "intDBref_allele"
			elif colTypes[i] == "Alt allele":
				if maxLen[0] == 1: # save a bit of memory if all are one character long
					tempVarType = "CHAR"
				else:
					tempVarType = "VARCHAR"
				sqlState += "intDBalt_allele %s(%s) NOT NULL" % (tempVarType, maxLen.popleft())
				colNames[i] = "intDBalt_allele"
			elif colTypes[i] == "Alleles":
				sqlState += "intDBalleles VARCHAR(%s) NOT NULL" % maxLen.popleft()
				colNames[i] = "intDBalleles"
			elif colTypes[i] == "VARCHAR":
				sqlState += "`%s` VARCHAR(%s) NOT NULL" % (colNames[i], maxLen.popleft())
			else:
				sqlState += "`%s` %s NOT NULL" % (colNames[i], colTypes[i])

			if colTypes[i] in ("INTEGER", "DOUBLE"):
				insertString += "%s" # no quotes for numbers
			else:
				insertString += "'%s'" # single quotes for string literals
		sqlState += ")"
		insertString += "),"
		
		# execute on MySQL server
		with self.cnx.cursor() as curs:
			# create panel information table
			curs.execute(sqlState)
			# load data - to best deal with new lines and LOCAL issues, not using LOAD DATA
			with open(self.panelDefFile, "r") as f:
				line = f.readline() # skip header
				line = f.readline()
				colNameString = "(" + ",".join(["`" + x + "`" for x in colNames]) + ")"
				sqlState = "INSERT INTO `%s` %s VALUES " % (self.panelNameBox.text(), colNameString)
				rowCounter = 0
				while line:
					line = line.rstrip("\n").split("\t")
					sqlState += insertString % tuple(line)
					rowCounter += 1
					if rowCounter == self.maxBatchSize:
						# strip last comma and execute insert statement
						curs.execute(sqlState.rstrip(","))
						sqlState = "INSERT INTO `%s` %s VALUES " % (self.panelNameBox.text(), colNameString)
						rowCounter = 0
					line = f.readline()
				if rowCounter > 0:
					# strip last comma and execute insert statement
					curs.execute(sqlState.rstrip(","))
			del sqlState

			# add panel to overall genotype panel information table
			# panel name, number of loci, ploidy, panel description, panel type
			curs.execute("INSERT INTO intDBgeno_overview VALUES (%s, %s, %s, %s, %s)", 
				(self.panelNameBox.text(), locusCount, self.ploidySpinnerBox.value(), self.panelDescBox.toPlainText(), self.panelTypeBox.currentText()))

			# create genotype table
			sqlState = "CREATE TABLE `%s` (ind_id INTEGER UNSIGNED PRIMARY KEY," % ("intDB" + self.panelNameBox.text() + "_gt")
			rowCounter = 0
			if self.panelTypeBox.currentText() == "Biallelic":
				# determine number of bits needed
				nBits = numBits(2, self.ploidySpinnerBox.value())
				# statement for defining a column in CREATE TABLE
				baseState = " `{}` " + ("BIT(%s) NOT NULL," % nBits)
				# statement for adding a column in ALTER TABLE
				baseState2 = " ADD COLUMN" + baseState
			elif self.panelTypeBox.currentText() == "Multiallelic":
				baseState = " `{}` TINYINT UNSIGNED NOT NULL,"
				baseState2 = " ADD COLUMN" + baseState
			elif self.panelTypeBox.currentText() == "Hyperallelic":
				baseState = ""
				for i in range(1, self.ploidySpinnerBox.value() + 1):
					baseState += " `{0}" + (".a%s` TINYINT UNSIGNED NOT NULL," % i)
				baseState2 = ""
				for i in range(0, self.ploidySpinnerBox.value()):
					baseState2 += " ADD COLUMN `{0}" + (".a%s` TINYINT UNSIGNED NOT NULL," % i)

			# get second connection and cursor to loop through loci without storing all 
			# locus names in memory
			cnx2 = getConnection(self.userInfo)
			lociCursor = getCursLoci(cnx2, self.panelNameBox.text())
			# build genotype table with all loci
			# NOTE: this needs to work for all three panel types with different baseState(s) from above
			for loc in lociCursor:
				sqlState += baseState.format(loc[0])
				rowCounter += 1
				if rowCounter == self.maxBatchSize:
					# execute statement
					if sqlState[0:6] == "CREATE":
						# add foreign key constraint with initial table specification
						curs.execute(sqlState + " FOREIGN KEY (ind_id) REFERENCES intDBpedigree(ind_id))")
					else:
						curs.execute(sqlState.rstrip(","))
					# start new statement with ALTER TABLE
					sqlState = "ALTER TABLE `%s` " % ("intDB" + self.panelNameBox.text() + "_gt")
					baseState = baseState2
					rowCounter = 0
			# execute last statement if needed
			if rowCounter > 0:
				if sqlState[0:6] == "CREATE":
					# add foreign key constraint with initial table specification
					curs.execute(sqlState + " FOREIGN KEY (ind_id) REFERENCES intDBpedigree(ind_id))")
				else:
					curs.execute(sqlState.rstrip(","))
			lociCursor.close()
			del sqlState

			# create lookup table
			if self.panelTypeBox.currentText() == "Multiallelic":
				# define table
				sqlState = "CREATE TABLE `%s` (locus_id INTEGER UNSIGNED NOT NULL, genotype_id TINYINT UNSIGNED NOT NULL," % ("intDB" + self.panelNameBox.text() + "_lt")
				alleleCols = []
				for i in range(1, self.ploidySpinnerBox.value() + 1):
					sqlState += " allele_%s VARCHAR(255) NOT NULL," % i
					alleleCols += ["allele_%s" % i]
				sqlState += " FOREIGN KEY (locus_id) REFERENCES %s (intDBlocus_id), PRIMARY KEY (locus_id, genotype_id), INDEX (%s))" % (self.panelNameBox.text(), ",".join(alleleCols))
				del alleleCols # defensive
				curs.execute(sqlState)
				# populate with user supplied values, if any
				if "intDBalleles" in colNames:
					# get cursor for loci/alleles ordered by locus id
					laCursor = getCursLociAlleles(cnx2, self.panelNameBox.text())
					colNameString = "(" + ",".join(["locus_id", "genotype_id"] + ["allele_%s" % i for i in range(1, self.ploidySpinnerBox.value() + 1)]) + ")"
					for loc in laCursor: # (id, name, alleles)
						# split alleles
						alleles = loc[2].split(",")
						alleles = [x for x in alleles if len(x) > 0] # remove any empty strings (can happen when user uploads with no value)
						if len(alleles) < 1: # skip if no alleles given
							continue
						# check that number of genotypes can be stored
						if numGenotypes(len(alleles), self.ploidySpinnerBox.value()) > 255:
							dlgError(parent=self, message="%s alleles for locus %s is too many to be stored in a Multiallelic panel." % (len(alleles), loc[1]))
							removePartialPanel(self.userInfo, self.panelNameBox.text())
							return
						alleles.sort() # sort to make comparison to user input data easy (have to sort it on input as well)
						geno_id = 1 # start at 1 b/c 0 is missing genotype
						sqlState = "INSERT INTO `%s` %s VALUES " % ("intDB" + self.panelNameBox.text() + "_lt", colNameString)
						for geno in combinations_with_replacement(alleles, self.ploidySpinnerBox.value()):
							genoSort = list(geno) 
							genoSort.sort() # should already be sorted, but double checking here just to make sure, and in case combin function changes
							# add genotype to lookup table
							sqlState += "(%s,%s,%s)," % (loc[0], geno_id, ",".join(["'%s'" % x for x in genoSort]))
							geno_id += 1
						# execute each locus at a time
						curs.execute(sqlState.rstrip(","))
					laCursor.close()

			elif self.panelTypeBox.currentText() == "Hyperallelic":
				# define table
				sqlState = """
				CREATE TABLE `%s` (
				locus_id INTEGER UNSIGNED NOT NULL, 
				allele_id TINYINT UNSIGNED NOT NULL, 
				allele VARCHAR(255) NOT NULL,
				FOREIGN KEY (locus_id) REFERENCES %s (intDBlocus_id), 
				PRIMARY KEY (locus_id, allele_id),
				INDEX (allele))
				""" % ("intDB" + self.panelNameBox.text() + "_lt", self.panelNameBox.text())
				curs.execute(sqlState)
				# populate with user supplied values, if any
				if "intDBalleles" in colNames:
					# get cursor for loci/alleles ordered by locus id
					laCursor = getCursLociAlleles(cnx2, self.panelNameBox.text())
					colNameString = "(" + ",".join(["locus_id", "allele_id", "allele"]) + ")"
					for loc in laCursor: # (locus id, allele id, allele character string)
						# split alleles
						alleles = loc[2].split(",")
						alleles = [x for x in alleles if len(x) > 0] # remove any empty strings (can happen when user uploads with no value)
						if len(alleles) < 1: # skip if no alleles given
							continue
						if len(alleles) > 255:
							dlgError(parent=self, message="%s alleles for locus %s is too many to be stored in a Hyperallelic panel." % (len(alleles), loc[1]))
							removePartialPanel(self.userInfo, self.panelNameBox.text())
							return
						allele_id = 1 # start at 1 b/c 0 is missing genotype
						sqlState = "INSERT INTO `%s` %s VALUES " % ("intDB" + self.panelNameBox.text() + "_lt", colNameString)
						for a in alleles:
							# add allele to lookup table
							sqlState += "(%s,%s,'%s')," % (loc[0], allele_id, a)
							allele_id += 1
						# execute each locus at a time
						curs.execute(sqlState.rstrip(","))
					laCursor.close()
			
			cnx2.close() # close second connection

		# close window
		self.close()
	
