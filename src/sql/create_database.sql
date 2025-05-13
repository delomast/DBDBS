-- create genotype panel information table
CREATE TABLE intDBgeno_overview (
	panel_name VARCHAR(60) PRIMARY KEY, 
	number_of_loci INTEGER UNSIGNED NOT NULL,
	ploidy INTEGER UNSIGNED NOT NULL,
	panel_description TEXT,
	panel_type VARCHAR(60)
);

-- create phenotype table information table
CREATE TABLE intDBpheno_overview (
	table_name VARCHAR(60) PRIMARY KEY,
	ind_name_col VARCHAR(60),
	sire_name_col VARCHAR(60),
	dam_name_col VARCHAR(60),
	time_obs_col VARCHAR(60) NOT NULL,
	number_of_phenos INTEGER UNSIGNED NOT NULL,
	table_description TEXT
);

-- create a phenotype variable information table
CREATE TABLE intDBpheno_variableInfo (
	table_name VARCHAR(60) NOT NULL,
	pheno_name VARCHAR (60) NOT NULL,
	pheno_description TEXT,
	min_value DOUBLE,
	max_value DOUBLE,
	FOREIGN KEY (table_name) REFERENCES intDBpheno_overview(table_name),
	PRIMARY KEY (table_name, pheno_name)
);

-- create genetic group information table
CREATE TABLE intDBgen_group_overview (
	grouping_name VARCHAR(60) UNIQUE NOT NULL,
	number_of_groups INTEGER UNSIGNED NOT NULL,
	group_description TEXT
);

-- create pedigree table
-- for sire and dam: 0 means founder, NULL means not entered
CREATE TABLE intDBpedigree (
	ind_id INTEGER UNSIGNED PRIMARY KEY AUTO_INCREMENT,
	ind VARCHAR (50) UNIQUE NOT NULL,
	sire INTEGER UNSIGNED,
	dam INTEGER UNSIGNED,
	FOREIGN KEY (dam) REFERENCES intDBpedigree(ind_id), -- dam and sire must be present
	FOREIGN KEY (sire) REFERENCES intDBpedigree(ind_id)
);
