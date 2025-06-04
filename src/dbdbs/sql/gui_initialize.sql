DROP TABLE IF EXISTS server_info;
DROP TABLE IF EXISTS user_info;
DROP TABLE IF EXISTS db_info;

/* Information on saved mySQL servers
host_id internal numeric identifier
host address of server
*/
CREATE TABLE server_info (
	host_id INTEGER PRIMARY KEY AUTOINCREMENT,
	host TEXT UNIQUE NOT NULL
);

/* Information on saved usernames to go with a server
host_id internal numeric identifier linking to server_info
user_name saved user name for that server
*/
CREATE TABLE user_info (
	host_id INTEGER NOT NULL,
	user_name TEXT NOT NULL,
	PRIMARY KEY (host_id, user_name),
	FOREIGN KEY (host_id) REFERENCES server_info (host_id)
);

/* Information on saved database names to go with a server
host_id internal numeric identifier linking to server_info
db_name saved database name for that server
*/
CREATE TABLE db_info (
	host_id INTEGER NOT NULL,
	db_name TEXT NOT NULL,
	PRIMARY KEY (host_id, db_name),
	FOREIGN KEY (host_id) REFERENCES server_info (host_id)
);
