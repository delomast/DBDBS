-- create genotype panel information table
CREATE TABLE intDBgeno_overview(
	panel_name VARCHAR(64) UNIQUE NOT NULL, 
	number_of_loci INTEGER UNSIGNED NOT NULL,
	ploidy INTEGER UNSIGNED NOT NULL,
	panel_description TEXT,
	panel_type VARCHAR(255)
);

-- create phenotype table information table
CREATE TABLE intDBpheno_overview (
	table_name VARCHAR(64) UNIQUE NOT NULL,
	number_of_phenos INTEGER UNSIGNED NOT NULL,
	table_description TEXT
);

-- create genetic group information table
CREATE TABLE intDBgen_group_overview (
	grouping_name VARCHAR(64) UNIQUE NOT NULL,
	number_of_groups INTEGER UNSIGNED NOT NULL,
	group_description TEXT
);

-- create pedigree table
-- for sire and dam: 0 means founder, NULL means not entered
CREATE TABLE intDBpedigree (
	ind_id INTEGER UNSIGNED PRIMARY KEY AUTO_INCREMENT,
	ind VARCHAR (255) UNIQUE NOT NULL,
	sire INTEGER UNSIGNED,
	dam INTEGER UNSIGNED,
	INDEX (sire), -- indexing all columns for fast joins and searches
	INDEX (dam)
);
