# File for functions to test regularity of filter inputs

irregularFilterGroupNames = [None, "pasmater"]
irregularFilterNames = [None, "pasmater"]

testIfRegular = lambda g, n: not (g in irregularFilterGroupNames) and not (n in irregularFilterNames)