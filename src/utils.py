# utility functions and classes
import os
import re
import mysql.connector as connector
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

def saveInfo(userInfo):
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
		with open(os.path.join(PACKAGEDIR, "sql/gui_initialize.sql"), mode="r") as f:
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

# check that does not begin with $ or end with space, len <= 64, no newlines
# this is a partial check for valid syntax for quoted identifiers
# returns True for good syntax, False for bad
def identifier_syntax_check(ident):
	if not re.fullmatch("^.{1,64}$", ident) or re.search("^\\$| $", ident):
		return False
	return True

# create a new database
# cnx: an open connection to a mysql server
# newDB: name of the new database
def create_new_db(cnx, newDB):
	if not identifier_syntax_check(newDB):
		raise Exception("Database name has invalid syntax")
	
	with cnx.cursor() as curs:
		curs.execute("SHOW DATABASES")
		db_exists = False
		for x in curs:
			if x[0] == newDB:
				db_exists = True
				cnx.consume_results()
				break
		if db_exists:
			return 1
		curs.execute("CREATE DATABASE `%s`" % newDB)
	return 0
