# short functions, mostly utilities
import re
import mysql.connector as connector

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
			raise Exception("Database name already exists.")
		curs.execute("CREATE DATABASE `%s`" % newDB)
