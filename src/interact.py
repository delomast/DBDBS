# Main interaction window

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
	QApplication, QMainWindow, QPushButton, QLabel, QLineEdit, QComboBox, 
	 QGridLayout, QWidget, QCheckBox
)
import os
import sys
import mysql.connector as connector
import sqlite3
from .login import loginDialog
from .utils import dlgError
from . import PACKAGEDIR


class interactWindow(QMainWindow):
	def __init__(self):
		super().__init__()
		self.setWindowTitle("DBDBS")
		# repeatedly get login information until connected
		self.cnx = None
		while True:
			login = loginDialog()
			login.accepted.connect(self.dbConnect)
			login.rejected.connect(sys.exit)
			login.exec()
			if self.cnx is not None:
				break

		# define widgets


		# position widgets in a layout
		layout = QGridLayout()

		# adding labels
		labelText = ["Host address", "Username", "Password", "Database name", "Save info", "you are connected"]
		for i in range(0, len(labelText)):
			layout.addWidget(QLabel(labelText[i]), i, 0)

		# set the central widget of the Window
		widget = QWidget()
		widget.setLayout(layout)
		self.setCentralWidget(widget)

	def dbConnect(self, userInfo):
		# try to connect to database
		try:
			self.cnx = connector.connect(user=userInfo["un"], password=userInfo["pw"], 
								host=userInfo["host"], database=userInfo["db"])
		except Exception as e:
			dlgError(parent=self, message="Failed to connect to MySQL database")
			# raise e
		# if login was successful, save information if requested
		if self.cnx is not None and userInfo["save"]:
			self.saveInfo(userInfo=userInfo)
	
	def saveInfo(self, userInfo):
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
