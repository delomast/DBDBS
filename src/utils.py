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

# count number of items in an iterable that are equal to a single value
def countEqual(items, matchValue) -> int:
	count = 0
	for i in items:
		if i == matchValue:
			count += 1
	return count

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
