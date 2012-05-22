# STV Documentation

This is a pure Python implementation of Simple Transferable Vote (STV)
counting. It also implements the version of STV that is used in the
elections of the Greek university governing councils.

# Usage

Help is available with

    python stv.py --help

The parameters include:

    -b BALLOTS_FILE, --ballots BALLOTS_FILE

The ballots file is a CSV file containing a single ballot in each
line, for instance:

    Chocolate, Strawberry
    Banana, Sweets
    Banana, Sweets
    Banana, Strawberry

    -n, --not_droop   

Do not use the [Droop
quota](http://en.wikipedia.org/wiki/Droop_quota). Usually, the Droop
quota is used. In the Greek university governing councils elections a
slightly different formula is used, specifically:

    int(math.ceil(1 + len(ballots) / (seats + 1.0)))

    -s SEATS --seats SEATS

The number of seats to be elected.

    -c CONSTITUENCIES_FILE, --constituencies CONSTITUENCIES_FILE

In the Greek university governing councils elections there are quotas
on the number of seats to be filled by members of a single school. The
constituencies file is a CSV file containing the allocation of
candidates among constituencies (i.e., schools). Each line contains
the candidates that are elected in the same constituency, for
instance:

    Chocolate, Sweets
    Banana, Strawberry

    -q QUOTA, --quota QUOTA

The constituency quota, that is, the number of seats that can be
filled by candidates in a single constituency, if constituencies are
used.

    -r [RANDOM [RANDOM ...]], --random [RANDOM [RANDOM ...]]

During the STV seat allocation process a random selection among
candidates may be required, either to elect or to eliminate a
candidate. The random selection can be carried out automatically, or
manually. If a manual random selection is necessary, then the user
specifies the -r switch. During the execution of the program, when the
random selection occurs, the program will stop and will output a
message informing the user that there is a missing value for a random
selection among candidates. The user will re-run the program giving
the index of the manually randomly selected candidate after the -r
switch. If a second random selection is required, the program will
again stop, and the user will re-run the program giving the indices of
the manually selected candidates one after the other after the -r
switch. And so on and so forth.

    -l LOGLEVEL, --loglevel LOGLEVEL

The logging level, which can be either DEBUG or INFO (the default).

For an invocation like:

    stv.py --ballots ballots.csv --constituencies constituencies.csv --seats 6 --quota 2 -n -l DEBUG

The output is a series of line, prefixed with the action taking place.
Specifically:

    ^THRESHOLD

The election threshold.

    @ROUND

The current counting round.

    .COUNT

The count at the current counting round, as a semicolon separated list
of candidate = count pairs.

    +ELECT candidate

The candidate has been elected.

    >TRANSFER from candidate1 to candidate2 n*w

A transfer of n votes from candidate1 to candidate2 using weight w.

    -ELIMINATE 

The candidate has been eliminated because no candidate could be
elected at this round, and this candidate has the smallest number of
votes.

    !QUOTA candidate

The candidate has been removed from the counting process because the
quota has been reached.

    ~ZOMBIES candidates

The list of zombie candidates, that is, candidates that had been
eliminated, but are brought back into the counting process because
other candidates have been removed from it following quota
restrictions.

    *RANDOM candidate from [candidates] to +ELECT

The candidate has been randomly selected from the list of candidates
for election.

    *RANDOM candidate from [candidates] to -ELIMINATE

The candidate has been randomly selected from the list of candidates
for elimination.