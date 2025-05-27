# import phenotype data window
import mysql.connector as connector
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
	QPushButton, QLabel, QComboBox, 
	 QGridLayout, QWidget, QSplitter,
	 QFileDialog, QVBoxLayout, QDialog, QDateEdit,
	 QDateTimeEdit, QSpinBox, QLineEdit,
	 QHBoxLayout, QMessageBox, QDoubleSpinBox,
	 QListWidget, QListWidgetItem, QAbstractItemView
)
from .utils import (dlgError, getIndIDdict)

# using QDialog class and exec to block other windows - only one active window at a time
class exportPhenoWindow(QDialog):
	def __init__(self, cnx : connector, userInfo : dict):
		super().__init__()
		self.setWindowTitle("Export phenotypes")
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
		self.colNames = [] # column names of selected phenotype table NOT including ind, sire, dam, dt_col

		
		# lists of columns to export and filter
		self.colsToExportListW = QListWidget() # cols to export
		self.colsToExportListW.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
		self.colsToExportListW.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove) # allow reordering
		self.colsToFilterListW = QListWidget() # cols to filter on
		self.colsToFilterListW.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
		self.colsToFilterListW.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
		self.colsToFilterListW.itemSelectionChanged.connect(self.updateFilterList)
		
		# user provides filter constraints
		## double and int, min and max values
		## character variables, value in set of user provided values
		##   user can either provide values in box or provide a file with one value per line and no header
		## date(time) variables, start and end values

		# start export button
		self.exportButton = QPushButton("Export phenotypes")
		self.exportButton.clicked.connect(self.exportPhenotypes)

		# choose output file button and label
		self.outputFileButton = QPushButton("Choose output file")
		self.outputFileButton.clicked.connect(self.chooseOutputFileDialog)
		self.outputFile = QLabel("")

		# set up layout
		self.gridLayout = QGridLayout()
		self.gridLayout.addWidget(QLabel("Table name"), 0, 0)
		self.gridLayout.addWidget(self.tableComboBox, 0, 1)
		self.gridLayout.addWidget(QLabel("Data type: "), 0, 2)
		self.gridLayout.addWidget(self.famOrIndLabel, 0, 3)
		
		self.gridLayout.addWidget(self.outputFileButton, 1, 0)
		self.gridLayout.addWidget(QLabel("Output file:"), 1, 1)
		self.gridLayout.addWidget(self.outputFile, 1, 2)
		
		# layout for input file button and display of selected file name
		self.colSelectLayout = QHBoxLayout()
		self.colSelectLayout.addWidget(self.colsToExportListW)
		self.colSelectLayout.addWidget(self.colsToFilterListW)
		self.colLayoutWidget = QWidget()
		self.colLayoutWidget.setLayout(self.colSelectLayout)


		# set up filter layout
		self.vertLayoutFilter = QVBoxLayout()
		self.filterLayoutWidget = QWidget()
		self.filterLayoutWidget.setLayout(self.vertLayoutFilter)
		self.vertLayoutFilter.addWidget(self.exportButton) # export button at the top


		# add grid layout as top layout in main layout
		self.mainLayout = QVBoxLayout()
		self.mainLayout.addLayout(self.gridLayout)

		self.mainSplitter = QSplitter() # using a splitter to allow resizing of filter input
		self.mainSplitter.setOrientation(Qt.Orientation.Vertical)
		self.mainLayout.addWidget(self.mainSplitter)
		self.mainSplitter.addWidget(self.colLayoutWidget)
		self.mainSplitter.addWidget(self.filterLayoutWidget)
		
		
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
			self.colNames = [] # column names of selected phenotype table
			curs.execute("SELECT pheno_name FROM intDBpheno_variableInfo WHERE table_name = '%s'" % self.tableComboBox.currentText())
			for res in curs:
				if res[0] in (self.ind_col, self.sire_col, self.dam_col, self.dt_col):
					continue
				self.colNames += [res[0]]
			
			# remove any items in the lists for selection
			self.colsToExportListW.clear()
			self.colsToFilterListW.clear()
			
			# add columns to lists for selection with ind names and date(time) of observation first
			for c in (self.ind_col, self.sire_col, self.dam_col, self.dt_col):
				if c is None:
					continue
				QListWidgetItem(c, self.colsToFilterListW)
				QListWidgetItem(c, self.colsToExportListW)
			for c in self.colNames:
				QListWidgetItem(c, self.colsToFilterListW)
				QListWidgetItem(c, self.colsToExportListW)
			
			# remove any filters
			# don't need to do this here b/c updateFilterList will be called automatically

	# update section where user inputs filtering criteria
	def updateFilterList(self):
		# get list of selected columns
		selCols = self.colsToFilterListW.selectedItems()
		selColNames = set([x.text() for x in selCols])
		# remove any filters that were unselected
		# iterate backwards to prevent index changing from removal
		for i in range(self.vertLayoutFilter.count() - 1, 0, -1):
			if self.vertLayoutFilter.itemAt(i).widget().name() not in selColNames:
				self.vertLayoutFilter.itemAt(i).widget().deleteLater() # schedule deletion of widget
				self.vertLayoutFilter.removeItem(self.vertLayoutFilter.itemAt(i)) # remove widget from layout
				# note that in the above line we are doing this by passing a reference (pointer) as the argument 
		# add any filters that were newly selected
		filterNames = set([self.vertLayoutFilter.itemAt(i).widget().name() for i in range(1, self.vertLayoutFilter.count())]) # names of current filters
		for col in selCols:
			if col.text() not in filterNames:
				# get variable type from MySQL
				# indID, sire, dam as "indID"
				if col.text() in (self.ind_col, self.sire_col, self.dam_col):
					sqlVarType = "indID"
				else:
					if col.text() == self.dt_col:
						repTuple = (self.cnx.database, self.tableComboBox.currentText(), "intDBu_DTobs")
					else:
						repTuple = (self.cnx.database, self.tableComboBox.currentText(), col.text())
					with self.cnx.cursor() as curs:
						curs.execute("SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS " +
						"WHERE TABLE_SCHEMA = '%s' AND TABLE_NAME = '%s' AND COLUMN_NAME = '%s'" % repTuple)
						sqlVarType = curs.fetchone()[0].lower()
				# add row to filter layout
				self.vertLayoutFilter.addWidget(filterPhenoRow(name = col.text(), varType = sqlVarType))
	
	# ask user for output file name
	def chooseOutputFileDialog(self):
		tempFile = QFileDialog.getSaveFileName(self, "Save output as", "/home/")[0]
		if tempFile == "":
			return
		self.outputFile.setText(tempFile)
	
	# export phenotypes to a file
	def exportPhenotypes(self):
		# make sure an output file is selected
		if self.outputFile.text() == "":
			dlgError(parent=None, message="No output file specified.")
			return
		# make sure columns to export are selected
		if len(self.colsToExportListW.selectedItems()) < 1:
			dlgError(parent=None, message="No columns selected to export.")
			return
		# get desired columns in desired order and
		# change from user-visible names to internal names where needed
		colsToExport = [x.text() for x in self.colsToExportListW.selectedItems()]
		for i in range(0, len(colsToExport)):
			if colsToExport[i] == self.dt_col:
				colsToExport[i] = "intDBu_DTobs"
		
		# build sql statement
		sqlState = "SELECT %s FROM `%s`"
		# add quotes for column names as needed
		for i in range(0, len(colsToExport)):
			if colsToExport[i] not in (self.ind_col, self.sire_col, self.dam_col):
				colsToExport[i] = "`%s`" % colsToExport[i]
		# add left join statements to translate ID numbers into names
		for i in range(0,3):
			col = (self.ind_col, self.sire_col, self.dam_col)[i]
			if col in colsToExport:
				pos = colsToExport.index(col)
				colsToExport[pos] = "a%s.ind AS `%s`" % (i, colsToExport[pos])
				sqlState += " LEFT JOIN intDBpedigree AS a{a[0]} ON {a[1]} = a{a[0]}.ind_id".format(
					a = (i, ("intDBind_id", "intDBsire", "intDBdam")[i]))
				# need to make something like 
				# SELECT site,survivors,a1.ind AS dam, a2.ind AS sire 
				# FROM phenotestfam LEFT JOIN intdbpedigree AS a1 ON intdbdam = a1.ind_id 
				# LEFT JOIN intdbpedigree AS a2 ON intdbsire = a2.ind_id;
		# make substitutions of column names and table name
		sqlState = sqlState % (",".join(colsToExport), self.tableComboBox.currentText())
		
		# add filters if needed
		if len(self.colsToFilterListW.selectedItems()) > 0:
			sqlState += " WHERE "
			# +1 to range b/c button is first widget in the layout
			for i in range(1, len(self.colsToFilterListW.selectedItems())+1):
				# get filter criteria and add to sql statement
				filVals = [self.vertLayoutFilter.itemAt(i).widget().name()]
				if self.vertLayoutFilter.itemAt(i).widget().varType in ("int", "double"):
					filVals += [self.vertLayoutFilter.itemAt(i).widget().min.value(),
								self.vertLayoutFilter.itemAt(i).widget().max.value()]
					sqlState += "`{a[0]}` >= {a[1]} AND `{a[0]}` <= {a[2]}".format(a = filVals)
				elif self.vertLayoutFilter.itemAt(i).widget().varType in ("date", "datetime"):
					if self.vertLayoutFilter.itemAt(i).widget().varType == "date":
						filVals += [self.vertLayoutFilter.itemAt(i).widget().start.date().toString("yyyy-MM-dd"),
									self.vertLayoutFilter.itemAt(i).widget().end.date().toString("yyyy-MM-dd")]
					else:
						filVals += [self.vertLayoutFilter.itemAt(i).widget().start.dateTime().toString("yyyy-MM-dd hh:mm:ss"),
									self.vertLayoutFilter.itemAt(i).widget().end.dateTime().toString("yyyy-MM-dd hh:mm:ss")]
					if self.vertLayoutFilter.itemAt(i).widget().name() == self.dt_col:
						# change colname to internal name
						filVals[0] = "intDBu_DTobs"
					sqlState += "`{a[0]}` >= '{a[1]}' AND `{a[0]}` <= '{a[2]}'".format(a = filVals)
				elif self.vertLayoutFilter.itemAt(i).widget().varType in ("varchar", "text", "indID"):
					if self.vertLayoutFilter.itemAt(i).widget().fileLabel.text() == "":
						# get values from lineEdit
						validValues = self.vertLayoutFilter.itemAt(i).widget().validBox.text().split(",")
					else:
						# get values from file - one per line, no header
						with open(self.vertLayoutFilter.itemAt(i).widget().fileLabel.text(), "r") as f:
							validValues = [line.rstrip("\n") for line in f]
					if self.vertLayoutFilter.itemAt(i).widget().varType == "indID":
						# filter on internal column
						if self.vertLayoutFilter.itemAt(i).widget().name() == self.ind_col:
							filVals[0] = "intDBind_id"
						elif self.vertLayoutFilter.itemAt(i).widget().name() == self.dam_col:
							filVals[0] = "intDBdam"
						elif self.vertLayoutFilter.itemAt(i).widget().name() == self.sire_col:
							filVals[0] = "intDBsire"
						# if indID variable, translate to int
						indIDdict = getIndIDdict(self.cnx, validValues)
						validValues = [indIDdict.get(x, None) for x in validValues]
						# remove any None (originate from ind names given but not in pedigree)
						# and change to string for ",".join()
						validValues = [str(x) for x in validValues if x is not None]
					else:
						# if not indID add quotes
						validValues = ["'%s'" % x for x in validValues]
					filVals += [",".join(validValues)]
					sqlState += "`{a[0]}` IN ({a[1]})".format(a = filVals)

				# add AND if needed
				if i < len(self.colsToFilterListW.selectedItems()):
					sqlState += " AND "

		# get data and write out
		with self.cnx.cursor() as curs:
			curs.execute(sqlState)
			with open(self.outputFile.text(), "w") as fout:
				# write out to tab-separated file
				# write out header
				fout.write("\t".join([x.text() for x in self.colsToExportListW.selectedItems()]) + "\n")
				# write out each line
				for x in curs:
					fout.write("\t".join([str(y) for y in x]) + "\n")

		# generate message box stating the export is done
		messageBox = QMessageBox(parent=self)
		messageBox.setWindowTitle("Genotype export")
		messageBox.setText("Genotype export complete")
		messageBox.exec()
		self.close()

# class to make filter rows and some information easily selectable and editable
# each filter should be one row with column name and either
# min and max
# text box for value entry, file selection button, selected file path, and use file checkbox
# start and end date
class filterPhenoRow(QWidget):
	# name is name of column
	# varType is MySQL column type
	def __init__(self, name, varType):
		super().__init__()
		self.varType = varType
		# set up main layout as horizontal box
		self.mainLayout = QHBoxLayout()
		self.setLayout(self.mainLayout)
		# add label with column name
		self.colNameLabel = QLabel(name)
		self.mainLayout.addWidget(self.colNameLabel, 1) # stretch of 1

		# add widgets for variable type
		if self.varType == "int":
			# min and max values
			self.min = QSpinBox()
			self.min.setRange(-1000000, 1000000)
			self.max = QSpinBox()
			self.max.setRange(-1000000, 1000000)
			self.mainLayout.addWidget(QLabel("Min:"), 0) # stretch of 0 for close spacing of label
			self.mainLayout.addWidget(self.min, 2)
			self.mainLayout.addSpacing(50)
			self.mainLayout.addWidget(QLabel("Max:"), 0)
			self.mainLayout.addWidget(self.max, 2)
		elif self.varType == "double":
			# min and max values
			self.min = QDoubleSpinBox()
			self.min.setDecimals(4)
			self.min.setRange(-1000000, 1000000)
			self.max = QDoubleSpinBox()
			self.max.setDecimals(4)
			self.max.setRange(-1000000, 1000000)
			self.mainLayout.addWidget(QLabel("Min:"), 0)
			self.mainLayout.addWidget(self.min, 2)
			self.mainLayout.addSpacing(50)
			self.mainLayout.addWidget(QLabel("Max:"), 0)
			self.mainLayout.addWidget(self.max, 2)
		elif self.varType == "date":
			# start and end values
			self.start = QDateEdit()
			self.start.setDisplayFormat("yyyy-MM-dd")
			self.mainLayout.addWidget(QLabel("Start (yyyy-mm-dd):"), 0)
			self.mainLayout.addWidget(self.start, 2)
			self.mainLayout.addSpacing(50)
			self.end = QDateEdit()
			self.end.setDisplayFormat("yyyy-MM-dd")
			self.mainLayout.addWidget(QLabel("End (yyyy-mm-dd):"), 0)
			self.mainLayout.addWidget(self.end, 2)
		elif self.varType == "datetime":
			# start and end values
			self.start = QDateTimeEdit()
			self.start.setDisplayFormat("yyyy-MM-dd hh:mm:ss")
			self.mainLayout.addWidget(QLabel("Start (yyyy-mm-dd hh:mm:ss):"), 0)
			self.mainLayout.addWidget(self.start, 2)
			self.mainLayout.addSpacing(50)
			self.end = QDateTimeEdit()
			self.end.setDisplayFormat("yyyy-MM-dd hh:mm:ss")
			self.mainLayout.addWidget(QLabel("End (yyyy-mm-dd hh:mm:ss):"), 0)
			self.mainLayout.addWidget(self.end, 2)
		elif self.varType in ("varchar", "text", "indID"):
			# indID treated as text
			# text box for value entry, file selection button, selected file path, and use file checkbox
			self.validBox = QLineEdit()
			self.mainLayout.addWidget(QLabel("Values, comma separated:"), 0)
			self.mainLayout.addWidget(self.validBox, 2)
			self.fileEntryButton = QPushButton("Select file")
			self.fileEntryButton.clicked.connect(self.fileSelect)
			self.mainLayout.addWidget(self.fileEntryButton, 1)
			self.fileLabel = QLabel("")
			self.fileLabel.setWordWrap(True)
			self.mainLayout.addWidget(QLabel("File with values:"), 0)
			self.mainLayout.addWidget(self.fileLabel, 0)
	
	# return name of column this filter is for
	def name(self):
		return self.colNameLabel.text()
	
	def fileSelect(self):
		tempFile = QFileDialog.getOpenFileName(self, "Select input file", "/home/")[0]
		# adjusting stretch
		# allowing user to clear the file by not selecting a file
		if tempFile == "":
			self.mainLayout.setStretch(2, 2) # stretch for lineEdit widget for values
			self.mainLayout.setStretch(5, 0) # stretch for selected file label
			# make lineEdit widget editable
			self.validBox.setReadOnly(False)
		else:
			self.mainLayout.setStretch(2, 0) # stretch for lineEdit widget for values
			self.mainLayout.setStretch(5, 2) # stretch for selected file label
			# clear lineEdit widget and make non-editable
			self.validBox.clear()
			self.validBox.setReadOnly(True)
		self.fileLabel.setText(tempFile)
