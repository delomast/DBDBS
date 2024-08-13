# genotype file iterators
# iterators that read different genotype file formats 
# and return one ind name and genotypes for each call
# specifically returns tuple of (indName, (tuple of alleles from all loci in order))
# also make locus names (order of loci returned) available

import re

# iterator to read "2col" format genotype files
class genoIter_2col:
	# file path, whether to strip trailing .-aA1 from locus names, ploidy
	def __init__(self, file : str, strip_a1 : bool, ploidy : int):
		# open file
		self.f = open(file, "r")
        # get locus names from header
		self.line = self.f.readline()
		self.loci = self.line.rstrip("\n").split("\t")
		self.loci = [self.loci[i] for i in range(1, len(self.loci) - 1, ploidy)] # remove ind name column and allele 2+ names
		if strip_a1:
			self.loci = [re.sub(r"[\.-_][aA]1$", "", x) for x in self.loci]

	def __iter__(self):
		return self

	def __next__(self):
		self.line = self.f.readline()
		if self.line == "":
			raise StopIteration
		else:
			# process line to return genotypes
			sep = self.line.rstrip("\n").split("\t")
			return (sep[0], tuple(sep[1:]))
