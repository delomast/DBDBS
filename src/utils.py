# utility functions and classes
import os
import re
import mysql.connector as connector
from math import log, comb, ceil
import sqlite3
from PyQt6.QtWidgets import (
	QMessageBox
)
from . import PACKAGEDIR

class dlgError(QMessageBox):
	def __init__(self, parent = None, message = ""):
		super().__init__(parent)
		self.setWindowTitle("Error")
		self.setText(message)
		self.exec()

def saveInfo(userInfo : dict):
	# check if directory exists and make if not
	if not os.path.isdir(os.path.join(PACKAGEDIR, "interface_db")):
		os.mkdir(os.path.join(PACKAGEDIR, "interface_db"))

	# check if database exists and initialize if not
	db_exists = os.path.exists(os.path.join(PACKAGEDIR, "interface_db/dbdbs.sqlite"))
	# connect/create
	gui_db = sqlite3.connect(os.path.join(PACKAGEDIR, "interface_db/dbdbs.sqlite"),
					detect_types=sqlite3.PARSE_DECLTYPES)
	if not db_exists:
		# create empty tables
		with open(os.path.join(PACKAGEDIR, "sql/gui_initialize.sql"), mode="r", encoding = "utf-8") as f:
			gui_db.executescript(f.read())
	
	# add info to gui database
	curs_host = gui_db.execute("SELECT host_id FROM server_info WHERE host = ? LIMIT 1", (userInfo["host"],))
	input_host_id = next(curs_host, [None])[0]
	curs_host.close()
	if input_host_id is None:
		# add host
		gui_db.execute("INSERT INTO server_info (host) VALUES (?)", (userInfo["host"],))
		gui_db.commit()
		# get auto assigned host_id and add user and database names
		curs_host = gui_db.execute("SELECT host_id FROM server_info WHERE host = ?", (userInfo["host"],))
		input_host_id = curs_host.fetchone()[0]
		curs_host.close()
		gui_db.execute("INSERT INTO user_info (host_id, user_name) VALUES (?, ?)", (input_host_id, userInfo["un"]))
		if userInfo["db"] != "":
			gui_db.execute("INSERT INTO db_info (host_id, db_name) VALUES (?, ?)", (input_host_id, userInfo["db"]))
		gui_db.commit()
	else:
		# host is already saved
		# check user
		curs_user = gui_db.execute("SELECT EXISTS(SELECT 1 FROM user_info WHERE user_name = ? AND host_id = ? LIMIT 1)", 
				(userInfo["un"], input_host_id))
		if curs_user.fetchone()[0] == 0:
			# need to add user
			gui_db.execute("INSERT INTO user_info (host_id, user_name) VALUES (?, ?)", (input_host_id, userInfo["un"]))
			gui_db.commit()
		curs_user.close()
		# check database
		if userInfo["db"] != "":
			curs_db = gui_db.execute("SELECT EXISTS(SELECT 1 FROM db_info WHERE db_name = ? AND host_id = ? LIMIT 1)", 
				(userInfo["db"], input_host_id))
			if curs_db.fetchone()[0] == 0:
				# need to add db
				gui_db.execute("INSERT INTO db_info (host_id, db_name) VALUES (?, ?)", (input_host_id, userInfo["db"]))
				gui_db.commit()
				curs_db.close()
	gui_db.close()

# check that does not begin with $ or end with space, len <= 54, no newlines
# does not start with "IntDB" (case insensitive)
# this is a partial check for valid syntax for quoted identifiers
# using one length for simplicity even though some (e.g., db name) could be longer
# returns True for good syntax, False for bad
def identifier_syntax_check(ident :  str) -> bool:
	if not re.fullmatch("^.{1,54}$", ident) or re.search("^\\$| $|^IntDB", ident, flags=re.IGNORECASE):
		return False
	return True

# calculate number of possible genotypes given the number
#  of alleles and the ploidy
def numGenotypes(numAlleles : int, ploidy : int) -> int:
	return comb(numAlleles + ploidy - 1, ploidy)

# calculate number of bits needed to represent a SNP including
#  a value for a missing genotype
def numBits(numAlleles : int, ploidy : int) -> int:
	return ceil(log(numGenotypes(numAlleles, ploidy) + 1, 2))

# get number of loci in a panel
def getNumLoci(cnx : connector, panelName : str) -> int:
	with cnx.cursor() as curs:
		curs.execute("SELECT number_of_loci FROM intDBgeno_overview where panel_name = %s", (panelName,))
		return curs.fetchone()[0]

# function to start a new connection
def getConnection(userInfo : dict):
	cnx = connector.connect(user=userInfo["un"], password=userInfo["pw"], 
						 host=userInfo["host"], database=userInfo["db"], autocommit=True)
	return cnx

# return a cursor with locus names in a panel ordered by auto_incrementing id number
def getCursLoci(cnx : connector, panelName : str):
	curs = cnx.cursor()
	curs.execute("SELECT intDBlocus_name FROM `%s` ORDER BY intDBlocus_id ASC" % panelName)
	return curs

# return a cursor with locus id, locus name, and alleles in a panel ordered by auto_incrementing id number
def getCursLociAlleles(cnx : connector, panelName : str):
	curs = cnx.cursor()
	curs.execute("SELECT intDBlocus_id, intDBlocus_name, intDBalleles FROM `%s` ORDER BY intDBlocus_id ASC" % panelName)
	return curs

# remove a partial or whole genotype panel if it is empty (no genotypes stored)
# in case an error is encountered after some commits have already been made
# this will remove any of the tables/rows made from this panel
# it will only remove panels that do not contain genotype data and so
# will not delete a panel with genotypes present
def removePartialPanel(userInfo : dict, panelName : str):
	cnxTemp = getConnection(userInfo)
	with cnxTemp.cursor() as curs:
		# make sure genotype table is empty, if it exists
		curs.execute("SHOW TABLES LIKE 'intdb%s_gt'" % panelName)
		if next(curs, [None])[0] is not None:
			curs.execute("SELECT 1 FROM `intdb%s_gt` LIMIT 1" % panelName)
			if next(curs, [None])[0] is not None:
				return 1
			# remove genotype table
			curs.execute("DROP TABLE `intdb%s_gt`" % panelName)
		# remove lookup table, if it exists
		curs.execute("SHOW TABLES LIKE 'intdb%s_lt'" % panelName)
		if next(curs, [None])[0] is not None:
			curs.execute("DROP TABLE `intdb%s_lt`" % panelName)
		# remove panel info table
		curs.execute("SHOW TABLES LIKE '%s'" % panelName)
		if next(curs, [None])[0] is not None:
			curs.execute("DROP TABLE `%s`" % panelName)
		# remove row from panel overview table
		curs.execute("DELETE FROM intDBgeno_overview WHERE panel_name = '%s'" % panelName)
	cnxTemp.close()
	return 0

# checking which inds are in the pedigree already
# returns a tuple of two tuples, first has inds in 
# the pedigree, second has inds not in the pedigree
def indsInPedigree(cnx : connector, inds : list):
	with cnx.cursor() as curs:
		curs.execute("SELECT ind FROM intDBpedigree WHERE ind IN (%s)" % ",".join(["'%s'" % x for x in inds]))
		inPed = [x[0] for x in curs]
	outPed = [x for x in inds if x not in inPed]
	return (tuple(inPed), tuple(outPed))

# checking which inds are in a table already
# returns a tuple of two tuples, first has inds in 
# the table, second has inds not in the table
# assumes table has ind_id column which
# should be linked as foreign key to pedigree table
def indsInTable(cnx : connector, inds : list, tableName : str):
	with cnx.cursor() as curs:
		sqlState = """
		SELECT intDBpedigree.ind
		FROM intDBpedigree
		INNER JOIN `%s` AS panel ON intDBpedigree.ind_id=panel.ind_id
		WHERE intDBpedigree.ind IN (%s)
		""" % (tableName, ",".join(["'%s'" % x for x in inds]))
		curs.execute(sqlState)
		inTable = [x[0] for x in curs]
	outTable = [x for x in inds if x not in inTable]
	return (tuple(inTable), tuple(outTable))

# return a list of individual names from a 2col format file
# and a boolean of whether there are duplicate ind names
def getIndsFromFile(fileName : str, fileType : str) -> list:
	if fileType == "2col":
		with open(fileName, "r") as f:
			header = f.readline() # skip header
			inds = [line.rstrip("\n").split("\t")[0] for line in f]
		# check for duplicates
		if len(inds) > len(set(inds)):
			dups = True
		else:
			dups = False
	else:
		raise Exception("Internal error: file type not supported by getIndsFromFile")
	return [tuple(inds), dups]

# add individuals to the pedigree (optionally sire and dam information as well)
# inds, sire, dam are either tuples or lists
def addToPedigree(cnx: connector, inds, sire = None, dam = None):
	if len(inds) == 0:
		return 0
	with cnx.cursor() as curs:
		if sire is None and dam is None:
			# just add inds
			sqlState = "INSERT INTO intDBpedigree (ind) VALUES"
			for name in inds:
				if name == "":
					dlgError(parent=self, message="Invalid individual name (empty string) found.")
					raise ValueError("Empty string cannot be an individual name.")
				sqlState += " ('%s')," % name
			curs.execute(sqlState.rstrip(","))
		elif sire is None:
			if len(inds) != len(dam):
				return 1
			pass
		elif dam is None:
			if len(inds) != len(sire):
				return 1
			pass
		else:
			if len(inds) != len(sire) or len(inds) != len(dam):
				return 1
			pass
	return 0

# get ind_id from database and return dict
# key of ind name, value of ind_id
def getIndIDdict(cnx : connector, inds : list):
	with cnx.cursor() as curs:
		curs.execute("SELECT ind, ind_id FROM intDBpedigree WHERE ind IN (%s)" % ",".join(["'%s'" % x for x in inds]))
		indID = {}
		for x in curs:
			indID[x[0]] = x[1]
	return indID

# for a multiallelic panel
# make a list, in order of loci,
# with each entry being a dict of
# key = (allele1, allele2, ...) and value of genotype_id 
def getGenoDict_multi(cnx : connector, panelName : str, loci : list, ploidy : int):
	# build blank list of dictionaries
	outListDict = [{} for x in loci]
	sqlState = "SELECT lt.genotype_id," + ",".join(["lt.allele_%s" % x for x in range(1, ploidy + 1)])
	sqlState += " FROM {0} AS p INNER JOIN intDB{0}_lt AS lt ON p.intDBlocus_id = lt.locus_id WHERE p.intDBlocus_name = '%s'".format(panelName)
	missTuple = tuple(["" for x in range(0, ploidy)]) # empty string tuple representing missing genotype
	with cnx.cursor() as curs:
		for i in range(0, len(loci)):
			# get locus specific lookup table
			curs.execute(sqlState % loci[i])
			# add to dictionary
			for x in curs:
				# key is ordered alleles in a tuple, value is genotype code
				outListDict[i][tuple(x[1:])] = x[0]
			# add missing genotype value
			outListDict[i][missTuple] = 0 # 0 in table is missing genotype
	return outListDict

# for a hyperallelic panel
# make a list, in order of loci,
# with each entry being a dict of
# key = (allele) and value of allele_id 
def getAlleleDict_hyper(cnx : connector, panelName : str, loci : list, ploidy : int):
	outListDict = [{} for x in loci]
	sqlState = "SELECT lt.allele_id,lt.allele FROM {0} AS p INNER JOIN intDB{0}_lt AS lt ON p.intDBlocus_id = lt.locus_id WHERE p.intDBlocus_name = '%s'".format(panelName)
	with cnx.cursor() as curs:
		for i in range(0, len(loci)):
			# get locus specific allele lookup table
			curs.execute(sqlState % loci[i])
			# add all alleles to dictionary
			for x in curs:
				outListDict[i][x[1]] = x[0]
			# add missing allele value
			outListDict[i][""] = 0
	return outListDict

# for a biallelic panel
# make a list in order of loci, values are tuple (refAllele, altAllele)
def getRefAlt(cnx : connector, panelName : str, loci : list):
	outList = [None for x in loci]
	lookupPos = {} # position in list that locus should have
	for i in range(0, len(loci)):
		lookupPos[loci[i]] = i
	with cnx.cursor() as curs:
		curs.execute("SELECT intDBlocus_name, intDBref_allele, intDBalt_allele FROM `%s` WHERE intDBlocus_name IN (%s)" % (panelName, ",".join(["'" + x + "'" for x in loci])))
		# add alleles as tuple (ref, alt) to list
		for res in curs:
			outList[lookupPos[res[0]]] = (res[1], res[2])
	return outList

# geno : iterable with each element being an allele, e.g. ("A", "C") represents a heterozygous diploid genotype
# refAlt : tuple of (refAllele, altAllele), e.g., element of list returned by getRefAlt
# missing allele is empty string "" (only checks first allele - assumes either all missing or none missing)
# returned genotype is number of copies of alt allele with missing genotype being (ploidy + 1)
def genoToAltCopies(geno, refAlt):
	if geno[0] == "":
		return len(geno) + 1 # ploidy + 1
	countAlt = 0
	for x in geno:
		if x == refAlt[0]:
			pass
		elif x == refAlt[1]:
			countAlt += 1
		else:
			raise ValueError("unrecognized allele") # throw an error
	return countAlt
