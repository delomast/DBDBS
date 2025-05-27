# import phenotype data window
import mysql.connector as connector
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QComboBox, 
	 QGridLayout,
	 QFileDialog, QVBoxLayout, QDialog,
	 QRadioButton, QHBoxLayout, QMessageBox
)
import re
from .utils import (dlgError, 
	indsInPedigree, addToPedigree, getIndIDdict
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
		# self.colNames = [] # column names NOT including sire, dam, ind, date(time)
		# self.minValue = []
		# self.maxValue = []

		# check for new individuals button
		self.checkIndsButton = QPushButton("Check if individuals are in the pedigree")
		self.checkIndsButton.clicked.connect(self.checkNewInds)
		# check for new observations button
		self.checkObsButton = QPushButton("Check if observations are in the table")
		self.checkObsButton.clicked.connect(self.checkNewObservations)


		# check that column names match the selected panel
		self.checkColsButton = QPushButton("Verify column names")
		self.checkColsButton.clicked.connect(self.checkColNames)

		# add new phenotypes or update existing individuals on import radio buttons
		self.addNewRadio = QRadioButton("Add new observations", self)
		self.addNewRadio.setChecked(True) # default is add new individuals
		self.updateRadio = QRadioButton("Update existing observations", self)

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
		self.gridLayout2.addWidget(self.checkObsButton, 2, 0)
		self.gridLayout2.addWidget(self.importButton, 3, 0)

		# add grid layout as top layout in main layout
		self.mainLayout = QVBoxLayout()
		self.mainLayout.addLayout(self.gridLayout)
		self.mainLayout.addLayout(self.fileSelectLayout)
		self.mainLayout.addLayout(self.gridLayout2)
		self.setLayout(self.mainLayout)

		# update labels with values for default selections
		self.tableSelectionChange()


	def tableSelectionChange(self):
		# clear and update information
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
			# self.colNames = [] # column names NOT including sire, dam, ind, date(time)
			# self.minValue = []
			# self.maxValue = []
			# curs.execute("SELECT pheno_name, min_value, max_value FROM intDBpheno_variableInfo WHERE table_name = '%s'" % self.tableComboBox.currentText())
			# for res in curs:
			# 	if res[0] in (self.ind_col, self.sire_col, self.dam_col, self.dt_col):
			# 		continue
			# 	self.colNames += [res[0]]
			# 	self.minValue += [res[1]]
			# 	self.maxValue += [res[2]]

	# open file dialog for user to select an input file
	def onClickInputFile(self):
		tempFile = QFileDialog.getOpenFileName(self, "Select input file", "/home/")[0]
		if tempFile == "":
			return
		self.inputFile.setText(tempFile)
	
	# check that file has been selected and has required columns
	# if an error is found, issues error message and returns False
	# if no error is found, returns True
	def checkFile(self):
		if self.inputFile.text() == "":
			dlgError(parent=self, message="No input file is selected")
			return False
		# read header to check for presence of column names
		with open(self.inputFile.text(), "r") as f:
			h = f.readline().rstrip("\n").split("\t")
			if self.ind_col is None:
				# family data, dam and sire columns should be present
				if self.sire_col not in h or self.dam_col not in h:
					dlgError(parent=self, message="Missing the dam and/or sire column(s)")
					return False
			else:
				if self.ind_col not in h:
					dlgError(parent=self, message="Missing the individual name column(s)")
					return False
			if self.dt_col not in h:
					dlgError(parent=self, message="Missing the data(time) of observation column")
					return False
		return True

	
	# check if individuals are in the pedigee
	def checkNewInds(self, s = None, interact = True):
		if not self.checkFile():
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

			if not interact:
				return pedStatus
		
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
	# s is to catch signal from button
	def checkNewObservations(self, s = None, interact = True):
		if not self.checkFile():
			return
		with open(self.inputFile.text(), "r") as f:
			# identify column(s) with individual names and date/time
			h = f.readline().rstrip("\n").split("\t")
			if self.ind_col is None:
				# position of columns to pull names from
				pos = [h.index(self.sire_col), h.index(self.dam_col), h.index(self.dt_col)]
			else:
				pos = [h.index(self.ind_col), h.index(self.dt_col)]
			# make set of all observations in the input file
			# with each observation a tuple of (indName, datetime) or (sire, dam, datetime)
			obs = set()
			obsCount = 0
			for line in f:
				sep = line.rstrip("\n").split("\t")
				obsCount += 1
				oneObs = tuple([sep[x] for x in pos])
				obs.add(oneObs)
			if len(obs) < obsCount:
				if interact:
					dlgError(parent=self, message="Not all observations are unique")
					return
				else:
					return 3 # duplicate observations in the input - error
			with self.cnx.cursor() as curs:
				# get set of observations that are already in the table
				if self.ind_col is None:
					sqlState = "SELECT intDBsire, intDBdam, intDBu_DTobs FROM `%s` WHERE (intDBsire, intDBdam, intDBu_DTobs) IN (" % self.tableComboBox.currentText()
				else:
					sqlState = "SELECT intDBind_id, intDBu_DTobs FROM `%s` WHERE (intDBind_id, intDBu_DTobs) IN (" % self.tableComboBox.currentText()
				
				# convert ind names to ids then assemble for sql lookup
				if self.ind_col is None:
					inds = set([x[0] for x in obs]).union(set([x[1] for x in obs]))
				else:
					inds = set([x[0] for x in obs])
				indIDdict = getIndIDdict(self.cnx, list(inds))
				# if len(indIDdict) < len(inds):
				# 	dlgError(parent=self, message="Some individuals are not in the pedigree")
				# 	return
				# using indIDdict.get() to return "NULL" if ind is not in the pedigree
				# which is sent as NULL to mysql and will show up as not in the table
				if self.ind_col is None:
					obsIDconverted = [(indIDdict.get(o[0], "NULL"), indIDdict.get(o[1], "NULL"), "'%s'" % o[2]) for o in obs]
				else:
					obsIDconverted = [(indIDdict.get(o[0], "NULL"), "'%s'" % o[1]) for o in obs]
				sqlState += ",".join(["(%s)" % ",".join([str(y) for y in x]) for x in obsIDconverted]) + ")"
				curs.execute(sqlState)
				inTable = set([x for x in curs])
			# observations that aren't in the table (with converted IDs and "NULL" for IDs not in pedigree)
			# outTable = set(obsIDconverted).difference(inTable)

			# return values for within function checking
			if not interact:
				if len(inTable) == 0:
					# none in the table - ready to import new values
					return 0
				elif len(inTable) == obsCount:
					# all in the table - ready to update values
					return 1
				# mix of in the table and out - error
				return 2
			
			# show summary message and ask whether to write a report
			writeReportBox = QMessageBox(parent=self)
			writeReportBox.setWindowTitle("Individual check")
			msgTxt = "Of %s total observations, %s are already in the table. " % (len(obsIDconverted), len(inTable))
			msgTxt += "Write report to " + self.inputFile.text() + "_obsReport.txt?"
			writeReportBox.setText(msgTxt)
			writeReportBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
			writeReport = writeReportBox.exec()

			# write report
			if writeReport == QMessageBox.StandardButton.Yes:
				# change IDs back to individual names
				indIDdict_reverse = {v : k for k,v in indIDdict.items()}
				if self.ind_col is None:
					inTableOrigNames = set([(indIDdict_reverse[o[0]], indIDdict_reverse[o[1]], o[2]) for o in inTable])
				else:
					inTableOrigNames = set([(indIDdict_reverse[o[0]], o[1]) for o in inTable])
				outTableOrigNames = obs.difference(inTableOrigNames)
					
				# write report
				with open(self.inputFile.text() + "_obsReport.txt", "w") as fout:
					# write header line
					if self.ind_col is None:
						fout.write("%s\t%s\t%s\tinTable\n" % (self.sire_col, self.dam_col, self.dt_col))
					else:
						fout.write("%s\t%s\tinTable\n" % (self.ind_col, self.dt_col))
					# in table
					for o in inTableOrigNames:
						fout.write("\t".join(o + ("TRUE",)) + "\n")
					# not in table
					for o in outTableOrigNames:
						fout.write("\t".join(o + ("FALSE",)) + "\n")


	# check column names in input file
	def checkColNames(self, s = None, interact = True):
		if not self.checkFile():
			return
		
		# get column names from import file
		with open(self.inputFile.text(), "r") as f:
			h = set(f.readline().rstrip("\n").split("\t"))
		
		# get locus names from panel
		with self.cnx.cursor() as curs:
			curs.execute("SELECT pheno_name FROM intDBpheno_variableInfo WHERE table_name = '%s'" % self.tableComboBox.currentText())
			inTable = set([x[0] for x in curs])

		# loci in panel but not in file
		onlyInTable = inTable.difference(h)
		# loci in file but not in panel
		onlyInFile = h.difference(inTable)

		if interact:
			messageBox = QMessageBox(parent=self)
			messageBox.setWindowTitle("Column name check")
			if len(onlyInFile) == 0 and len(onlyInTable) == 0:
				msgTxt = "Column names in the file match those in the table."
			else:
				if len(onlyInFile) > 10 or len(onlyInFile) == 0:
					onlyInFile = [str(len(onlyInFile)) + " loci"]
				if len(onlyInTable) > 10 or len(onlyInTable) == 0:
					onlyInPanel = [str(len(onlyInTable)) + " loci"]
				msgTxt = "%s named only in the file \n\n %s missing from the file" % (",".join(onlyInFile), ",".join(onlyInTable))
			messageBox.setText(msgTxt)
			messageBox.exec()
			return
		
		if len(onlyInFile) == 0 and len(onlyInTable) == 0:
			# all columns in both
			return 0
		elif len(onlyInFile) == 0:
			# file is missing some but all present are valid
			return 1
		else:
			# file has some that are not in the table - error
			return 4


	# import phenotypes
	# checks loop through the file many times
	# potential to speed up by combining into one function and/or looping through 
	# once and storing data 
	def importPhenotypes(self):
		if not self.checkFile():
			return

		if not self.updateRadio.isChecked() and not self.addNewRadio.isChecked():
			dlgError(parent=self, message="You must indicate either add new observations or update existing observations")
			return
		
		# check column names
		colNameCheck = self.checkColNames(interact = False)
		if colNameCheck == 1:
			# warn about some missing
			askBox = QMessageBox(parent=self)
			askBox.setWindowTitle("Confirm proceed")
			if self.addNewRadio.isChecked():
				askBox.setText("One or more columns in the table are missing from the input file. Values for the missing columns will be saved as missing data. Do you want to proceed with the import?")
			else:
				askBox.setText("One or more columns in the table are missing from the input file. Values for the missing columns will not be updated. Do you want to proceed with the import?")
			askBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
			proceed = askBox.exec()
			if proceed == QMessageBox.StandardButton.No:
				return
		elif colNameCheck > 1:
			# error, some unrecognized
			dlgError(parent=None, message="File contains unrecognized column names")
			return

		# check individuals in pedigree
		pedStatus = self.checkNewInds(interact = False)
		# make sure all are in the pedigree already if updating observations
		if self.updateRadio.isChecked() and len(pedStatus[1]) > 0:
			dlgError(parent=self, message="You are trying to update observations but one or more individuals is not in the pedigree")
			return
		# add individuals to the pedigree if needed
		retValue = addToPedigree(self.cnx, pedStatus[1], sire = None, dam = None)
		if retValue != 0:
			dlgError(parent=self, message="Error trying to add individuals to the pedigree")
			return

		# check observations in table
		obsCheck = self.checkNewObservations(interact=False)
		if not self.addNewRadio.isChecked() and obsCheck == 0:
			# none in table, should be importing new
			dlgError(parent=None, message="No observations are in the table but the add new observations option is not in use.")
			return	
		elif not self.updateRadio.isChecked() and obsCheck == 1:
			# all in table, should be updating
			dlgError(parent=None, message="All observations are already in the table but the update observations option is not in use.")
			return			
		elif obsCheck == 2:
			# mix of in table and not, error
			dlgError(parent=None, message="Some observations are already in the table and some are not.")
			return
		elif obsCheck == 3:
			# duplicate observations, error
			dlgError(parent=None, message="Some observations are duplicated in the input.")
			return

		# loop through data to check format of values
		# check min/max constraints
		with open(self.inputFile.text(), "r") as f:
			# read header
			h = f.readline().rstrip("\n").split("\t")
			# first get unique values
			# build dict with key = column name, value = set of unique values
			# individual name, sire, and dam columns not in the dict
			uniqueValueDict = {x : set() for x in h if x not in (self.ind_col, self.dam_col, self.sire_col)}
			# positions to pull values from
			pos = [x for x in range(0, len(h)) if h[x] not in (self.ind_col, self.dam_col, self.sire_col)]
			for line in f:
				sep = line.rstrip("\n").split("\t")
				for i in pos:
					# empty string is missing data
					if sep[i] != "":
						uniqueValueDict[h[i]].add(sep[i])
		# now check that all values are valid
		sqlVarTypeDict = {} # save for insert or update function
		for k,v in uniqueValueDict.items(): # k is column name, v is set of unique values
			# get variable type
			with self.cnx.cursor() as curs:
				if k == self.dt_col:
					repTuple = (self.cnx.database, self.tableComboBox.currentText(), "intDBu_DTobs")
				else:
					repTuple = (self.cnx.database, self.tableComboBox.currentText(), k)
				curs.execute("SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS " +
				"WHERE TABLE_SCHEMA = '%s' AND TABLE_NAME = '%s' AND COLUMN_NAME = '%s'" % repTuple)
				sqlVarType = curs.fetchone()[0].lower()
				sqlVarTypeDict[k] = sqlVarType

				# get min/max
				minVal, maxVal = (None, None)
				if sqlVarType.lower() in ("int", "double"):
					curs.execute("SELECT min_value, max_value FROM intDBpheno_variableInfo " +
					"WHERE table_name = '%s' AND pheno_name = '%s'" % 
					(self.tableComboBox.currentText(), k))
					minVal, maxVal = curs.fetchone()

			# check format of all unique values
			for val in v:
				# check format
				if sqlVarType == "int":
					try:
						temp = int(val)
					except:
						dlgError(parent=None, message="Error converting %s to an integer in column %s" % (val, k))
						return
				elif sqlVarType == "double":
					try:
						temp = float(val)
					except:
						dlgError(parent=None, message="Error converting %s to a number in column %s" % (val, k))
						return
				elif sqlVarType == "varchar" or sqlVarType == "text":
					pass # no validation needed, could validate character count, but not going to right now
				elif sqlVarType == "date":
					# check format
					if re.fullmatch("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", val) is None:
						dlgError(parent=None, message="%s in column %s does not conform to the MySQL date format of 'YYYY-MM-DD'" % (val, k))
						return
					# check year, month, and day values
					dateSep = [int(x) for x in val.split("-")]
					if dateSep[0] < 1000: #or dateSep[0] > 9999 # > 9999 is impossible with int of four characters
						dlgError(parent=None, message="%s in column %s has an invalid value for year" % (val, k))
						return
					if dateSep[1] < 1 or dateSep[1] > 12:
						dlgError(parent=None, message="%s in column %s has an invalid value for month" % (val, k))
						return
					if dateSep[2] < 1 or dateSep[2] > 31:
						dlgError(parent=None, message="%s in column %s has an invalid value for day" % (val, k))
						return
				elif sqlVarType == "datetime":
					# check format
					if re.fullmatch("^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$", val) is None:
						dlgError(parent=None, message="%s in column %s does not conform to the MySQL date format of 'YYYY-MM-DD hh:mm:ss'" % (val, k))
						return
					dateSep = val.split(" ")
					try:
						timeSep = [int(x) for x in dateSep[1].split(":")]
					except:
						dlgError(parent=None, message="Error converting time portion of %s to integers in column %s" % (val, k))
						return
					try:
						dateSep = [int(x) for x in dateSep[0].split("-")]
					except:
						dlgError(parent=None, message="Error converting date portion of %s to integers in column %s" % (val, k))
						return
					# check year, month, and day values
					if dateSep[0] < 1000: #or dateSep[0] > 9999 # > 9999 is impossible with int of four characters
						dlgError(parent=None, message="%s in column %s has an invalid value for year" % (val, k))
						return
					if dateSep[1] < 1 or dateSep[1] > 12:
						dlgError(parent=None, message="%s in column %s has an invalid value for month" % (val, k))
						return
					if dateSep[2] < 1 or dateSep[2] > 31:
						dlgError(parent=None, message="%s in column %s has an invalid value for day" % (val, k))
						return
					# check hour, minute, and second values
					if timeSep[0] < 0 or timeSep[0] > 23:
						dlgError(parent=None, message="%s in column %s has an invalid value for hour" % (val, k))
						return
					if timeSep[1] < 0 or timeSep[1] > 59:
						dlgError(parent=None, message="%s in column %s has an invalid value for minute" % (val, k))
						return
					if dateSep[2] < 0 or dateSep[2] > 59:
						dlgError(parent=None, message="%s in column %s has an invalid value for second" % (val, k))
						return
				else:
					dlgError(parent=None, message="Datatype of %s for %s is not recognized" % (sqlVarType, k))
					return

				# check min/max
				if minVal is not None and maxVal is not None and (sqlVarType == "double" or sqlVarType == "int"):
					if temp < minVal or temp > maxVal:
						dlgError(parent=None, message="Value of %s is outside the allowed range for column %s" % (val, k))
						return
		
		# all values have been checked and are valid
		# insert or update 

		# build dictionary key of ind name, value of ind_id
		indIDlookup = getIndIDdict(self.cnx, list(pedStatus[0] + pedStatus[1]))
		if self.addNewRadio.isChecked():
			# add new phenotypes
			self.addNewPhenos(indIDlookup, sqlVarTypeDict)
		else:
			# update existing phenotypes
			self.updatePhenos(indIDlookup, sqlVarTypeDict)
		
		# commit transaction after all individuals successfully added
		self.cnx.commit()
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Phenotype import")
		messageBox.setText("Phenotype import complete")
		messageBox.exec()
		self.close()
	
	# add new phenotypes
	def addNewPhenos(self, indIDlookup, sqlVarTypeDict):
		with open(self.inputFile.text(), "r") as f:
			# build SQL statement
			h = f.readline().rstrip("\n").split("\t") # read header
			sqlColNames = h.copy()
			sqlState = "INSERT INTO `%s` (" % self.tableComboBox.currentText()
			if self.ind_col is None:
				# position of columns with names
				IDpos = [h.index(self.sire_col), h.index(self.dam_col)]
				sqlColNames[IDpos[0]] = "intDBsire"
				sqlColNames[IDpos[1]] = "intDBdam"
			else:
				IDpos = [h.index(self.ind_col)]
				sqlColNames[IDpos[0]] = "intDBind_id"
			DTpos = h.index(self.dt_col) # position of date(time) column
			sqlColNames[DTpos] = "intDBu_DTobs"
			sqlState += ",".join(["`%s`" % x for x in sqlColNames])
			sqlState += ") VALUES "
			# build substitution string for adding quotes as needed
			sqlValueSubString = []
			for i in range(0, len(h)):
				if i in IDpos or sqlVarTypeDict[h[i]] == "double" or sqlVarTypeDict[h[i]] == "int":
					sqlValueSubString += ["%s"] # no quotes
				else:
					sqlValueSubString += ["'%s'"]
			sqlValueSubString = "(" + ",".join(sqlValueSubString) + "),"
			# makes something like "(%s,'%s','%s','%s',%s,'%s'),"
			# add all rows to the statement
			for line in f:
				sep = line.rstrip("\n").split("\t")
				# convert individual names to internal ID numbers
				for i in IDpos:
					sep[i] = indIDlookup[sep[i]]
				sqlState += sqlValueSubString % tuple(sep)
		with self.cnx.cursor() as curs:
			curs.execute(sqlState.rstrip(","))


	# update phenotypes in database by overwriting existing phenotypes
	def updatePhenos(self, indIDlookup, sqlVarTypeDict):
		with self.cnx.cursor() as curs:
			with open(self.inputFile.text(), "r") as f:
				# build SQL statement
				h = f.readline().rstrip("\n").split("\t") # read header
				sqlState = "UPDATE `%s` SET " % self.tableComboBox.currentText()
				if self.ind_col is None:
					# position of columns with names
					IDpos = [h.index(self.sire_col), h.index(self.dam_col)]
				else:
					IDpos = [h.index(self.ind_col)]
				DTpos = h.index(self.dt_col) # position of date(time) column

				# build substitution string for adding quotes as needed
				sqlColOrder = [] # order of columns for SQL
				for i in range(0, len(h)):
					if i in IDpos or i == DTpos:
						continue
					sqlColOrder += [i]
					sqlState += h[i] + "="
					if sqlVarTypeDict[h[i]] == "double" or sqlVarTypeDict[h[i]] == "int":
						sqlState += "{a[%s]}," % i # no quotes
					else:
						sqlState += "'{a[%s]}'," % i
				sqlState = sqlState.rstrip(",") # remove last comma
				sqlColOrder += IDpos
				sqlColOrder += [DTpos]
				sqlState += " WHERE "
				if self.ind_col is None:
					sqlState += "intDBsire={a[%s]} AND intDBdam={a[%s]} AND intDBu_DTobs='{a[%s]}'" % tuple(IDpos + [DTpos])
				else:
					sqlState += "intDBind_id={a[%s]} AND intDBu_DTobs='{a[%s]}'" % tuple(IDpos + [DTpos])
				# sqlState is now something like
				# UPDATE `%s` SET var1={a[2]},var2='{a[3]}',var3={a[4]} WHERE indDBind_id={a[0]} AND intDBu_DTobs='{a[1]}'

				# update each observation in input
				for line in f:
					sep = line.rstrip("\n").split("\t")
					# convert individual names to internal ID numbers
					for i in IDpos:
						sep[i] = indIDlookup[sep[i]]
					curs.execute(sqlState.format(a = sep))
