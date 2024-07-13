from utils import *
import mysql.connector as connector

createNewDB = False
dbName = "cvir_test"
# initialize connection
if createNewDB:
	cnx = connector.connect(user="root", password="DBSDB", 
						host="localhost")
	# create new and switch to it
	create_new_db(cnx, dbName)
	with cnx.cursor() as curs:
		curs.execute("USE `%s`" % dbName)
else:
	cnx = connector.connect(user="root", password="DBSDB", 
					host="localhost", database="dbName")


cnx.close()
