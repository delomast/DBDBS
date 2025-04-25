# make a new phenotype table window
import mysql.connector as connector
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QLineEdit, QComboBox, QRadioButton,
	 QGridLayout, 
	 QFileDialog, QVBoxLayout, QSpinBox, QTextEdit, QDialog
)
from .utils import (dlgError, identifier_syntax_check,
	getConnection
)

# using QDialog class and exec to block other windows - only one active window at a time
class newPhenoTableWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Make new phenotype table")
		self.cnx = cnx
		self.userInfo = userInfo

		self.setMinimumSize(200, 200) # trying to avoid :"Unable to set geometry" warning

		# panel type, name, etc (info from user)
		# individual or family level data
		# individual level requires individual name and date/time
		# family level requires sire, dam and date/time
		self.indivRadio = QRadioButton("Individual level data", self)
		self.indivRadio.setChecked(True) # default is individual data
		self.indivRadio.toggled.connect(self.onTypeChange)
		self.familyRadio = QRadioButton("Family level data", self)
		
		self.tableNameBox = QLineEdit() # name of phenotype table
		
		# file to define table
		# just contains header row of column names - other rows ignored so it
		# can be a file containing data
		self.selectDefFile = QPushButton("Select definition file")
		self.selectDefFile.clicked.connect(self.onClickDefFile)
		self.curFileSelected = QLabel("")
		self.curFileSelected.setWordWrap(True)
		
		# text description of phenotype table
		self.tableDescBox = QTextEdit()
		self.tableDescBox.setAcceptRichText(False)

		# set up grid layout
		self.gridLayout = QGridLayout()
		self.gridLayout.addWidget(self.indivRadio, 0, 0)
		self.gridLayout.addWidget(self.familyRadio, 0, 1)
		self.gridLayout.addWidget(QLabel("Table name"), 1, 0)
		self.gridLayout.addWidget(self.tableNameBox, 1, 1)
		self.gridLayout.addWidget(self.selectDefFile, 2, 0)
		self.gridLayout.addWidget(self.curFileSelected, 2, 1)
		self.gridLayout.addWidget(QLabel("Table description"), 3, 0)
		self.gridLayout.addWidget(self.tableDescBox, 3, 1)

		# add main selection items as top layout in main layout
		self.mainLayout = QVBoxLayout()
		self.mainLayout.addLayout(self.gridLayout)
		self.setLayout(self.mainLayout)

	def onClickDefFile(self):
		tempFile = QFileDialog.getOpenFileName(self, "Select table definition file", "/home/")[0]
		if tempFile == "":
			return
		self.tableDefFile = tempFile
		self.curFileSelected.setText(self.tableDefFile)
		# read in header line
		with open(self.tableDefFile, "r") as f:
			h = f.readline()
		if h:
			h = h.rstrip("\n").split("\t")
		else:
			dlgError(self, "Error: Could not read specified file")
			return
		
		# make sure column names are unique
		if len(h) > len(set(h)):
			dlgError(self, "Error: duplicated column names")
			return
		
		# make sure below maximum number of columns
		if len(h) > 1000:
			dlgError(self, "Error: too many columns, limit is 1000")
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
			self.gridLayout.addWidget(self.submitPanel_button, 4, 1)

	def onTypeChange(self):
		if hasattr(self, "columnType_comboboxes"):
			for i in range(0, len(self.columnType_comboboxes)):
				self.columnType_comboboxes[i].clear()
				self.columnType_comboboxes[i].addItems(self.getValidColumnTypes())
	
	def getValidColumnTypes(self):
		if self.indivRadio.isChecked():
			validTypes = ["ind_name"]
		else:
			validTypes = ["sire_name", "dam_name"]
		validTypes += ["DATE", "DATETIME", "INTEGER", "DOUBLE", "VARCHAR_255", "VARCHAR_65535", "TEXT"]
		return(validTypes)
	
	def onSubmit(self):
		# input error checks
		if not identifier_syntax_check(self.tableNameBox.text()):
			dlgError(parent=self, message="Invalid panel name")
			return
		colNames = [x.text() for x in self.columnType_labels] # user provided column names
		colItems = [x.currentText() for x in self.columnType_comboboxes] # user selected data type
		if (colItems.count("DATE") + colItems.count("DATETIME")) != 1:
			dlgError(self, "(Only) One column must be either \"DATE\" or \"DATETIME\"")
			return
		if self.indivRadio.isChecked():
			if colItems.count("ind_name") != 1:
				dlgError(self, "(Only) One column must be \"ind_name\"")
				return
		else:
			if colItems.count("sire_name") != 1:
				dlgError(self, "(Only) One column must be \"sire_name\"")
				return
			if colItems.count("dam_name") != 1:
				dlgError(self, "(Only) One column must be \"dam_name\"")
				return
		with self.cnx.cursor() as curs:
			curs.execute("SHOW TABLES")
			for x in curs:
				if x[0] == self.tableNameBox.text():
					self.cnx.consume_results()
					dlgError(parent=self, message="A table with that name already exists, please pick a different table name")
					return
		
		# make sure user defined columns have valid names
		for i in range(0, len(colNames)):
			if not identifier_syntax_check(colNames[i]):
				dlgError(parent=self, message="\"%s\" is an invalid column name" % colNames[i])
				return
				
		# add panel to database

		## add details to intDBpheno_overview

		## create table





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
					sqlState += " allele_%s VARCHAR(65535) NOT NULL," % i
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
				allele VARCHAR(65535) NOT NULL,
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

		# close window
		self.close()
	
