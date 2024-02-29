# STV Documentation

This is a pure Python implementation of Simple Transferable Vote (STV)
counting. It also implements the version of STV used in the
elections of the Greek university governing councils.

# Usage

Help is available with

    python stv.py --help

The parameters include:

* `-b BALLOTS_FILE, --ballots BALLOTS_FILE`

The ballots file is a CSV file containing a single ballot in each
line, for instance:

    Chocolate, Strawberry
    Banana, Sweets
    Banana, Sweets
    Banana, Strawberry

* `-s SEATS --seats SEATS`

The number of seats to be filled.

* `-c CONSTITUENCIES_FILE, --constituencies CONSTITUENCIES_FILE`

In the Greek university governing councils elections there are quotas
on the number of seats to be filled by members of a single school. The
constituencies file is a CSV file containing the allocation of
candidates among constituencies (i.e., schools). Each line contains
the name of the constituency, the size of the constituency, and the
candidates that are elected in the constituency, for instance:

    Deserts, 10, Chocolate, Sweets
    Fruits, 8, Banana, Strawberry

* `-q QUOTA, --quota QUOTA`

The constituency quota, that is, the number of seats that can be
filled by candidates in a single constituency, if constituencies are
used.

* `-r RANDOM_SEED --random RANDOM_SEED`

The random seed, as a Python code literal, so that the number can be
in base 2, 8, 10, 16, e.g., `0x123EF`. During the STV seat allocation
process a random selection among candidates may be required, either to
elect or to eliminate a candidate, or to sort constituencies according
to size breaking ties.

* `-l LOGLEVEL, --loglevel LOGLEVEL`

The logging level, which can be either DEBUG or INFO (the default).

* `-m QUOTA_MODULE, --quota_module QUOTA_MODULE`

A file containing custom quota logic. It must implement a class
inheriting from `DefaultQuotaCallback`.

For an invocation like:

    stv.py --ballots ballots.csv --constituencies constituencies.csv --seats 6 --quota 2 -l DEBUG

The output is a series of lines, each line prefixed with the action
taking place. Specifically:

    ^THRESHOLD threshold

The election threshold.

    @ROUND round

The current counting round.

    .COUNT candidate1 = count1; candidate2 = count2; ...

The count at the current counting round, as a semicolon separated list
of `candidate = count` pairs.

    +ELECT candidate candidate = votes

The `candidate` has been elected with `votes`.

    >TRANSFER from candidate1 to candidate2 n*w = t

A transfer of `n` votes from `candidate1` to `candidate2` using weight `w`.

    -ELIMINATE candidate = votes

The `candidate` having received `votes` has been eliminated because no
candidate could be elected at this round, and this candidate has the
smallest number of votes.

    !QUOTA candidate constituency >= quota

The `candidate` has been removed from the counting process because the
`quota` has been reached for the respective `constituency`.

    ~ZOMBIES candidates

The list of zombie candidates, that is, candidates that had been
eliminated, but are brought back into the counting process because
other candidates have been removed from it following quota
restrictions.

    *RANDOM candidate from [candidates] to +ELECT

The `candidate` has been randomly selected from the list of candidates
for election.

    *RANDOM candidate from [candidates] to -ELIMINATE

The `candidate` has been randomly selected from the list of candidates
for elimination.

    xSHUFFLE from [ items ] to [ shuffled items ]

Perform a random shuffle in the given items. This is done prior to
sorting the constituencies when performing round robin selection
rounds. As sorting is stable, that means that ties are broken
randomly. 

    /SORT from [ items ] to [ sorted items ]
    
Sort the given items.
    
    oROUND_ROBIN [ (constituency1, size1), (constituency2, size2), ... ]
    
Try to elect candidates from orphan constituencies, that is,
constituencies that have no candidate elected, taking the
constituencies in round robin fashion, order by their size with ties
broken randomly.
    
    #CONSTITUENCY_TURN constituency [ (candidate1, vote1), (candidate2, vote2), ... ]
    
The constituency currently selected in round robin fashion.

    ?COMMENT 

Log a comment on the process.