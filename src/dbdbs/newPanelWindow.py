# make a new panel window
import mysql.connector as connector
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QLineEdit, QComboBox, 
	 QGridLayout, QMessageBox,
	 QFileDialog, QVBoxLayout, QSpinBox, QTextEdit, QDialog
)
from .utils import (dlgError, identifier_syntax_check, alleleSyntaxCheck,
	getCursLociAlleles, getConnection, numBits, numGenotypes, removePartialPanel,
	locNameSyntaxCheck, escapeStringChar
)
from collections import deque
from itertools import combinations_with_replacement
import re

# using QDialog class and exec to block other windows - only one active window at a time
class newPanelWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Make new panel")
		self.cnx = cnx
		self.userInfo = userInfo

		self.setMinimumSize(200, 200) # trying to avoid :"Unable to set geometry" warning

		# panel type, name, etc (info from user)
		self.panelTypeBox = QComboBox()
		self.panelTypeBox.addItems(["Biallelic", "Multiallelic", "Hyperallelic"])
		self.panelTypeBox.currentTextChanged.connect(self.onTypeChange)
		self.panelNameBox = QLineEdit()
		self.selectDefFile = QPushButton("Select definition file")
		self.selectDefFile.clicked.connect(self.onClickDefFile)
		self.curFileSelected = QLabel("")
		self.curFileSelected.setWordWrap(True)
		self.ploidySpinnerBox = QSpinBox()
		self.ploidySpinnerBox.setRange(1, 255) # limited by TINYINT UNSIGNED in lookup table for alt allele copies
		self.ploidySpinnerBox.setValue(2) # default is diploid
		self.batchSizeSpinnerBox = QSpinBox() # number of loci to process at once (higher = faster and more memory)
		self.batchSizeSpinnerBox.setRange(1, 100000000)
		self.batchSizeSpinnerBox.setValue(10000) # default is 10000
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
		if colItems.count("Locus name") != 1:
			dlgError(self, "(Only) One column must be \"Locus name\"")
			return
		if self.panelTypeBox.currentText() == "Biallelic":
			if colItems.count("Ref allele") != 1:
				dlgError(self, "(Only) One column must be \"Ref allele\"")
				return
			if colItems.count("Alt allele") != 1:
				dlgError(self, "(Only) One column must be \"Alt allele\"")
				return
		else:
			if colItems.count("Alleles") > 1:
				dlgError(self, "You cannot have more than one column of \"Alleles\"")
				return
		with self.cnx.cursor() as curs:
			curs.execute("SHOW TABLES")
			for x in curs:
				if x[0].lower() == self.panelNameBox.text().lower():
					self.cnx.consume_results()
					dlgError(parent=self, message="A table with that name already exists, please pick a different panel name")
					return
		
		# detect varchar sizes and more input checks
		colNames = [x.text() for x in self.columnType_labels]
		colTypes = [x.currentText() for x in self.columnType_comboboxes]
		vChar = [i for i in range(0,len(colTypes)) if colTypes[i] in ("Locus name", "VARCHAR", "Alt allele", "Ref allele", "Alleles")]
		locName_pos = [i for i in range(0,len(colTypes)) if colTypes[i] == "Locus name"][0]
		toCheck_pos = [i for i in range(0,len(colTypes)) if colTypes[i] in ("Alt allele", "Ref allele", "Alleles")]
		dateCheck_pos = [i for i in range(0,len(colTypes)) if colTypes[i] == "DATE"]
		intCheck_pos = [i for i in range(0,len(colTypes)) if colTypes[i] == "INTEGER"]
		doubleCheck_pos = [i for i in range(0,len(colTypes)) if colTypes[i] == "DOUBLE"]
		maxLen = [0] * len(vChar)
		locusNames = set()
		locusCount = 0 # number of loci in panel definition file
		with open(self.panelDefFile, "r") as f:
			line = f.readline() # skip header
			for l in f:
				line = l.rstrip("\n").split("\t")
				locusCount += 1
				locusNames.add(line[locName_pos])
				for i in range(0, len(vChar)):
					if len(line[vChar[i]]) > maxLen[i]:
						maxLen[i] = len(line[vChar[i]])
				# make sure locus names are valid
				if not locNameSyntaxCheck(line[locName_pos]):
					dlgError(parent=self, message="Locus \"%s\" has an invalid name" % line[locName_pos])
					return
				# check date, integer, and double format
				for i in dateCheck_pos:
					if re.fullmatch("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", line[i]) is None:
						dlgError(parent=None, message="%s for locus %s does not conform to the MySQL date format of 'YYYY-MM-DD'" % (line[i], line[locName_pos]))
						return
					# check year, month, and day values
					dateSep = [int(x) for x in line[i].split("-")]
					if dateSep[0] < 1000: #or dateSep[0] > 9999 # > 9999 is impossible with int of four characters
						dlgError(parent=None, message="%s for locus %s has an invalid value for year" % (line[i], line[locName_pos]))
						return
					if dateSep[1] < 1 or dateSep[1] > 12:
						dlgError(parent=None, message="%s for locus %s has an invalid value for month" % (line[i], line[locName_pos]))
						return
					if dateSep[2] < 1 or dateSep[2] > 31:
						dlgError(parent=None, message="%s for locus %s has an invalid value for day" % (line[i], line[locName_pos]))
						return
				for i in intCheck_pos:
					try:
						temp = int(line[i])
					except:
						dlgError(parent=None, message="Error converting %s to an integer for locus %s" % (line[i], line[locName_pos]))
						return
				for i in doubleCheck_pos:
					try:
						temp = float(line[i])
					except:
						dlgError(parent=None, message="Error converting %s to a number for locus %s" % (line[i], line[locName_pos]))
						return
				# Make sure alt allele, ref allele, and alleles are valid values, if present (no whitespace, no single quotes, unique)
				if len(toCheck_pos) == 2:
					# ref and alt
					if line[toCheck_pos[0]] == line[toCheck_pos[1]]:
						dlgError(parent=self, message="Locus \"%s\" has the same ref and alt allele" % line[locName_pos])
						return
					elif line[toCheck_pos[0]] == "" or line[toCheck_pos[1]] == "":
						dlgError(parent=self, message="Locus \"%s\" is missing either a ref or an alt allele" % line[locName_pos])
						return
					for j in toCheck_pos:
						if not alleleSyntaxCheck(line[j]):
							dlgError(parent=self, message="Locus \"%s\" has an invalid allele value" % line[locName_pos])
							return
				elif len(toCheck_pos) == 1:
					# alleles
					alleles = line[toCheck_pos[0]].split(",")
					if len(alleles) > len(set(alleles)):
						dlgError(parent=self, message="Locus \"%s\" has the same allele listed more than once" % line[locName_pos])
						return
					if len(alleles) > 1 or alleles[0] != "":
						for a in alleles:
							if not alleleSyntaxCheck(a):
								dlgError(parent=self, message="Locus \"%s\" has an invalid allele value" % line[locName_pos])
								return
		if len(locusNames) < locusCount:
			dlgError(parent=self, message="Duplicate locus names found")
			return
		
		# make sure number of loci is below maximum
		# maximum allowed is a little below the hard maximum for MEDIUMBLOB
		maxLoci = 16700000 # for Multi, max loci is same as max bytes
		if self.panelTypeBox.currentText() == "Hyperallelic":
			maxLoci = maxLoci // self.ploidySpinnerBox.value()
		elif self.panelTypeBox.currentText() == "Biallelic":
			maxLoci = (maxLoci * 8) // numBits(2, self.ploidySpinnerBox.value())
		if locusCount > maxLoci:
			dlgError(parent=self, message="Too many loci to store in one panel. The maximum number of loci for this type and ploidy is %s." % maxLoci)
			return

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
				insertString += "'%s'" # single quotes for string literals and dates
		sqlState += ")"
		insertString += "),"
		
		# positions to escape special characters
		charEscape = [i for i in range(0, len(colTypes)) if colTypes[i] in ("VARCHAR", "TEXT")]

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
					for i in charEscape:
						line[i] = escapeStringChar(line[i])
					sqlState += insertString % tuple(line)
					rowCounter += 1
					if rowCounter == self.batchSizeSpinnerBox.value():
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
			sqlState = "CREATE TABLE `%s` (ind_id INTEGER UNSIGNED PRIMARY KEY, genotypes MEDIUMBLOB NOT NULL, FOREIGN KEY (ind_id) REFERENCES intDBpedigree(ind_id))" % ("intDB" + self.panelNameBox.text() + "_gt")
			curs.execute(sqlState)
			
			cnx2 = getConnection(self.userInfo)
			# create lookup table
			if self.panelTypeBox.currentText() == "Multiallelic":
				# define table
				sqlState = "CREATE TABLE `%s` (locus_id INTEGER UNSIGNED NOT NULL, genotype_id TINYINT UNSIGNED NOT NULL," % ("intDB" + self.panelNameBox.text() + "_lt")
				alleleCols = []
				for i in range(1, self.ploidySpinnerBox.value() + 1):
					sqlState += " allele_%s VARCHAR(1000) NOT NULL," % i
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
				allele VARCHAR(1000) NOT NULL,
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
		
		# commit changes
		self.cnx.commit()

		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Genotype panel")
		messageBox.setText("Genotype panel successfully added")
		messageBox.exec()

		# close window
		self.close()
	
