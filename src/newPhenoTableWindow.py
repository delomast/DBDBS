# make a new phenotype table window
import mysql.connector as connector
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QLineEdit, QComboBox, QRadioButton,
	QCheckBox, QWidget, QSplitter,
	QGridLayout, QScrollArea, QMessageBox,
	QFileDialog, QVBoxLayout, QDoubleSpinBox, QTextEdit, QDialog
)
from PyQt6.QtCore import Qt
from .utils import (dlgError, identifier_syntax_check)

# using QDialog class and exec to block other windows - only one active window at a time
class newPhenoTableWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Make new phenotype table")
		self.cnx = cnx
		self.userInfo = userInfo
		
		self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)
		self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
		self.setMinimumSize(400, 200) # trying to avoid :"Unable to set geometry" warning

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

		# add to widget and splitter - splitter allows top and bottom split to be resized
		self.gridLayoutWidget = QWidget()
		self.gridLayoutWidget.setLayout(self.gridLayout)

		self.mainLayout = QVBoxLayout()
		self.mainSplitter = QSplitter()
		self.mainSplitter.setOrientation(Qt.Orientation.Vertical)
		self.mainSplitter.addWidget(self.gridLayoutWidget)
		self.mainLayout.addWidget(self.mainSplitter)
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
				self.columnType_comboboxes[i].deleteLater()
				self.columnType_labels[i].deleteLater()
				self.columnMin[i].deleteLater()
				self.columnMax[i].deleteLater()
				self.useMinMax[i].deleteLater()
				self.columnDescription[i].deleteLater()

		self.columnType_subLayout = QGridLayout()
		# make combobox selection, label, min/max value, and
		# description for each column
		self.columnType_comboboxes = []
		self.columnType_labels = []
		self.columnMin = []
		self.columnMax = []
		self.useMinMax = []
		self.columnDescription = []
		self.columnType_subLayout.addWidget(QLabel("Column", alignment=Qt.AlignmentFlag.AlignRight), 0, 0)
		self.columnType_subLayout.addWidget(QLabel("Type", alignment=Qt.AlignmentFlag.AlignRight), 0, 1)
		self.columnType_subLayout.addWidget(QLabel("Min", alignment=Qt.AlignmentFlag.AlignRight), 0, 2)
		self.columnType_subLayout.addWidget(QLabel("Max", alignment=Qt.AlignmentFlag.AlignRight), 0, 3)
		self.columnType_subLayout.addWidget(QLabel("Use min/max", alignment=Qt.AlignmentFlag.AlignRight), 0, 4)
		self.columnType_subLayout.addWidget(QLabel("Description", alignment=Qt.AlignmentFlag.AlignHCenter), 0, 5)
		for i in range(0, len(h)):
			self.columnType_comboboxes += [QComboBox()]
			self.columnType_comboboxes[i].addItems(self.getValidColumnTypes())
			self.columnType_labels += [QLabel(h[i])]
			self.columnMin += [QDoubleSpinBox()]
			self.columnMin[i].setDecimals(4)
			self.columnMin[i].setRange(-1000000, 1000000)
			self.columnMax += [QDoubleSpinBox()]
			self.columnMax[i].setDecimals(4)
			self.columnMax[i].setRange(-1000000, 1000000)
			self.useMinMax += [QCheckBox()]
			self.columnDescription += [QTextEdit()]
			self.columnDescription[i].setAcceptRichText(False)
			self.columnDescription[i].setMinimumWidth(200)
			
			# add to layout
			self.columnType_subLayout.addWidget(self.columnType_labels[i], i+1, 0)
			self.columnType_subLayout.addWidget(self.columnType_comboboxes[i], i+1, 1)
			self.columnType_subLayout.addWidget(self.columnMin[i], i+1, 2)
			self.columnType_subLayout.addWidget(self.columnMax[i], i+1, 3)
			self.columnType_subLayout.addWidget(self.useMinMax[i], i+1, 4)
			self.columnType_subLayout.addWidget(self.columnDescription[i], i+1, 5)
		
		# add scroll area
		self.scrollArea = QScrollArea()
		self.scrollArea.setWidgetResizable(True) # allow widget within the scroll area to resize automatically
		self.scrollWidget = QWidget()
		# add to layout
		self.scrollWidget.setLayout(self.columnType_subLayout)
		self.scrollArea.setWidget(self.scrollWidget)
		if self.mainSplitter.count() == 1:
			self.mainSplitter.addWidget(self.scrollArea)
		else:
			self.mainSplitter.replaceWidget(1, self.scrollArea)
		
		# create submit button
		# only create after a file is selected, don't create more than once
		if not hasattr(self, "submitPanel_button"):
			self.submitPanel_button = QPushButton("Add new table")
			self.submitPanel_button.clicked.connect(self.onSubmit)
			self.gridLayout.addWidget(self.submitPanel_button, 4, 1)
		
		# make window bigger if not mazimized
		if not self.isMaximized():
			self.setWindowState(Qt.WindowState.WindowMaximized)
			# self.resize(600, 600)

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
		validTypes += ["u_DATE", "u_DATETIME", "INTEGER", "DOUBLE", "VARCHAR(60)", "VARCHAR(1000)", "TEXT", "DATE", "DATETIME"]
		return(validTypes)
	
	def onSubmit(self):
		# input error checks
		if not identifier_syntax_check(self.tableNameBox.text()):
			dlgError(parent=self, message="Invalid panel name")
			return
		colNames = [x.text() for x in self.columnType_labels] # user provided column names
		colItems = [x.currentText() for x in self.columnType_comboboxes] # user selected data type
		if (colItems.count("u_DATE") + colItems.count("u_DATETIME")) != 1:
			dlgError(self, "(Only) One column must be either \"u_DATE\" or \"u_DATETIME\"")
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
				if x[0].lower() == self.tableNameBox.text().lower():
					self.cnx.consume_results()
					dlgError(parent=self, message="A table with that name already exists, please pick a different table name")
					return
		
		# make sure user defined columns have valid names
		for i in range(0, len(colNames)):
			if not identifier_syntax_check(colNames[i]):
				dlgError(parent=self, message="\"%s\" is an invalid column name" % colNames[i])
				return
				
		# add panel to database
		with self.cnx.cursor() as curs:
			## add details to intDBpheno_overview
			sqlState = "INSERT INTO intDBpheno_overview (table_name, time_obs_col, number_of_phenos, table_description,"
			if "u_DATE" in colItems:
				timeColName = colNames[colItems.index("u_DATE")]
			else:
				timeColName = colNames[colItems.index("u_DATETIME")]

			sqlValues = [self.tableNameBox.text(), timeColName, len(colNames) - 2, self.tableDescBox.toPlainText()]
			if self.indivRadio.isChecked():
				sqlState += "ind_name_col) VALUES ('%s','%s',%s,'%s','%s')"
				sqlValues += [colNames[colItems.index("ind_name")]]
			else:
				sqlState += "sire_name_col, dam_name_col) VALUES ('%s','%s',%s,'%s','%s','%s')"
				sqlValues += [colNames[colItems.index("sire_name")], colNames[colItems.index("dam_name")]]
				sqlValues[2] -= 1 # decrease number of phenotypes to account for 2 family ID (sire and dam) columns
			sqlValues = tuple(sqlValues)
			# add details on variables
			# allowable range, description
			sqlState2 = "INSERT INTO intDBpheno_variableInfo (table_name, pheno_name, pheno_description, min_value, max_value) VALUES"
			for i in range(0, len(colItems)):
				# saving info for all columns in case user wants to save a description of required columns
				# if colItems[i] in ("ind_name", "sire_name", "dam_name", "u_DATE", "u_DATETIME"):
				# 	continue
				# use min and max values for input checking
				if self.useMinMax[i].isChecked():
					if colItems[i] not in ("INTEGER", "DOUBLE"):
						dlgError("Cannot use min/max for %s because it is not either INTEGER or DOUBLE." % colNames[i])
						return
					if self.columnMin[i].value() > self.columnMax[i].value():
						dlgError("Min must be less than Max for %s." % colNames[i])
						return
					sqlState2 += "('%s', '%s', '%s', %s, %s)," % (self.tableNameBox.text(), colNames[i], self.columnDescription[i].toPlainText(), self.columnMin[i].value(), self.columnMax[i].value())
				else:
					sqlState2 += "('%s', '%s', '%s', NULL, NULL)," % (self.tableNameBox.text(), colNames[i], self.columnDescription[i].toPlainText())
			# execute statements
			curs.execute(sqlState % sqlValues) # executing later in case input error found during min/max
			if not sqlState2.endswith("VALUES"):
				curs.execute(sqlState2.rstrip(","))
			del sqlState2 # defensive

			# create table
			sqlState = "CREATE TABLE `%s` (" % self.tableNameBox.text()
			# add date(time) column
			if "u_DATE" in colItems:
				sqlState += "intDBu_DTobs DATE NOT NULL,"
			else:
				sqlState += "intDBu_DTobs DATETIME NOT NULL,"
			# add user defined phenotypes
			for i in range(0, len(colItems)):
				if colItems[i] in ("ind_name", "sire_name", "dam_name", "u_DATE", "u_DATETIME"):
					continue
				sqlState += " `%s` %s," % (colNames[i], colItems[i])
			# add either individual or dam and sire ids and contstraints
			if self.indivRadio.isChecked():
				sqlState += " intDBind_id INTEGER UNSIGNED,"
				sqlState += " PRIMARY KEY (intDBind_id, intDBu_DTobs),"
				sqlState += " FOREIGN KEY (intDBind_id) REFERENCES intDBpedigree(ind_id))"
			else:
				sqlState += " intDBsire INTEGER UNSIGNED, intDBdam INTEGER UNSIGNED,"
				sqlState += " PRIMARY KEY (intDBsire, intDBdam, intDBu_DTobs),"
				sqlState += " FOREIGN KEY (intDBsire) REFERENCES intDBpedigree(ind_id),"
				sqlState += " FOREIGN KEY (intDBdam) REFERENCES intDBpedigree(ind_id))"
			# execute
			curs.execute(sqlState)

		## commit
		self.cnx.commit()

		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Phenotype table")
		messageBox.setText("Phenotype table successfully added")
		messageBox.exec()

		# close window
		self.close()
	
