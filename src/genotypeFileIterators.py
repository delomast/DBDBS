# genotype file iterators
# iterators that read different genotype file formats 
# and return one ind name and genotypes for each call
# specifically returns tuple of (indName, {dict of genotypes, key locus name, value sorted tuple of alleles})
# also make locus names (order of loci returned) available
# note that for some formats locus names can change from one call to the next, for others it does not

import re
from itertools import chain
from .utils import dlgError

# basic multi-locus genotype structure to help readability
# holds genotypes for one or more loci for one individual
class multLocGeno:
	def __init__(self, indName : str, genoDict : dict):
		self.indName = indName
		self.genoDict = genoDict # key is locus name, value is tuple of alleles e.g. ("AA", "AC", "CC") for a triploid microhap genotype

# iterator to read "2col" format genotype files
class genoIter_2col:
	# file path, whether to strip trailing .-aA1 from locus names, ploidy
	def __init__(self, file : str, strip_a1 : bool, ploidy : int):
		# open file
		self.f = open(file, "r")
        # get locus names from header and store in order of loci in file
		self.line = self.f.readline()
		self.loci = self.line.rstrip("\n").split("\t")
		self.loci = [self.loci[i] for i in range(1, len(self.loci) - 1, ploidy)] # remove ind name column and allele 2+ names
		if strip_a1:
			self.loci = [re.sub(r"[\.-_][aA]1$", "", x) for x in self.loci]
		# dictionary: key is locus name, value is (allele1, allele2, ..., allelen) for ploidy n
		# saving as attribute so don't have to reallocate a dictionary each iteration
		self.genos = {}
		for l in self.loci:
			self.genos[l] = None
		self.ploidy = ploidy
		self.alleleCount = self.ploidy * len(self.loci) # number of alleles each line should have
		self.indName = None

	def __iter__(self):
		return self

	def __next__(self):
		self.readNextLine()
		if self.line == "":
			raise StopIteration
		else:
			# process line to return genotypes
			sep = self.line.rstrip("\n").split("\t")
			self.indName = sep[0]
			if len(sep) != self.alleleCount + 1:
				dlgError(parent=None, message="Incorrect number of alleles in input file at individual %s" % self.indName)
				raise RuntimeError("Incorrect number of alleles in input file at individual %s" % self.indName)
			for i_locus, i_geno in zip(range(0, len(self.loci)), range(1, len(sep), self.ploidy)):
				self.genos[self.loci[i_locus]] = tuple(sorted(sep[i_geno:(i_geno + self.ploidy)]))
			return multLocGeno(self.indName, self.genos)

	# read next line but skip blank lines
	def readNextLine(self):
		self.line = self.f.readline()
		if self.line == "\n":
			self.readNextLine()

# iterator to read plink text (ped + map) format genotype files
# assumes map file has same base name as ped file
# handles tabs and/or spaces as the field separator
class genoIter_plinkPEDMAP:
	# file path to .ped file
	def __init__(self, file : str):
		# compile splitting expression
		self.splitPattern = re.compile("\t| ")
		# get loci names
		self.loci = []
		for mapLine in open(re.sub(r"\.ped$", ".map", file), "r"):
			self.loci += [re.split(self.splitPattern, mapLine.rstrip("\n"))[1]]
		self.alleleCount = len(self.loci) * 2
		# detect number of loci and compound format or not based on first line of ped file
		with open(file, "r") as pedIn:
			firstLine = pedIn.readline()
			firstLine = re.split(self.splitPattern, firstLine.rstrip("\n"))
			if len(self.loci) + 6 == len(firstLine):
				self.cmpGenos = True # compound genotype calls
			elif (len(self.loci) * 2) + 6 == len(firstLine):
				self.cmpGenos = False
			else:
				dlgError(parent=None, message="Incorrectly formatted PLINK files. Number of columns does not match expectations.")
				raise RuntimeError("Incorrectly formatted PLINK files input")

		# open ped file
		self.ped = open(file, "r")

		# dictionary: key is locus name, value is (allele1, allele2) for ploidy n
		# saving as attribute so don't have to reallocate a dictionary each iteration
		self.genos = {}
		for l in self.loci:
			self.genos[l] = None
		self.indName = None

	def __iter__(self):
		return self

	def __next__(self):
		self.line = self.ped.readline()
		if self.line == "":
			raise StopIteration
		else:
			# process line to return genotypes
			sep = self.line.rstrip("\n")
			sep = re.split(self.splitPattern, sep)
			# pull indId as within-family ID
			self.indName = sep[1]
			sep = sep[6:] # genotypes only
			# split genos if needed
			if self.cmpGenos:
				sep = [x for x in chain.from_iterable(sep)]
			# translate missing into empty string
			sep = ["" if x == "0" else x for x in sep]
			# check that number of alleles is as expected
			if len(sep) != self.alleleCount:
				raise RuntimeError("Wrong number of alleles in PLINK file at individual %s" % self.indName)
			# make dictionary
			for i_locus, i_geno in zip(range(0, len(self.loci)), range(0, len(sep), 2)):
				self.genos[self.loci[i_locus]] = tuple(sorted(sep[i_geno:(i_geno + 2)]))
			return multLocGeno(self.indName, self.genos)

# TODO left off here changing from returning tuple to returning dict
#    to use for insert and update, run through loci in panel in order needed
#       with a .get() statemtne and have a default return of missing genotype value

# iterator to read "long" format genotype files
# tab delimited with columns of ind name, locus name, allele 1, ..., allele n
# one line per ind/locus genotype
# file has header line - required
# missing genotype is empty string for all alleles
# note that loci names are NOT saved to object b/c they change between iterations
# loci names are instead returned as part of iterator
# iterator returns (individual name, (allele1, allelel2, ...), (locusname1, locusname2, ...))
class genoIter_long:
	# file path, maximum number of lines to read at once 
	def __init__(self, file : str, nline : int):
		# open file
		self.f = open(file, "r")
        # get ploidy from header
		self.readNextLine()
		self.ploidy = len(self.sep) - 2
		if self.ploidy < 1:
			dlgError(parent=None, message="Input genotype file did not have enough columns")
			raise RuntimeError("Input genotype file did not have enough columns")
		# define number of lines
		self.nline = nline
		# load first genotype line in look-ahead variable
		self.readNextLine()

	def __iter__(self):
		return self

	def __next__(self):
		# read until individual changes, max lines reached, or end of file
		if self.line == "":
			raise StopIteration
		else:
			# define values with next line
			indID = self.sep[0]
			loci = [self.sep[1]]
			nloci = 1
			genos = self.sep[2:]
			self.readNextLine()
			# add more if possible
			while nloci < self.nline:
				# break if EOF or individual changes with the next line
				if self.line == "" or self.sep[0] != indID:
					break
				# add to locus and genotype lists
				loci += [self.sep[1]]
				nloci += 1
				genos += self.sep[2:]
				self.readNextLine()
			if len(genos) != (nloci * self.ploidy):
				dlgError(parent=None, message="Wrong number of columns on one or more lines with individual %s" % indID)
				raise RuntimeError("Wrong number of columns on one or more lines with individual %s" % indID)
			return (indID, tuple(genos), tuple(loci))
	
	def readNextLine(self):
		self.line = self.f.readline()
		self.sep = self.line.rstrip("\n").split("\t")
