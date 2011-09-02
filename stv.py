# Copyright 2011 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#   1. Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#
#  2. Redistributions in binary form must reproduce the above
#     copyright notice, this list of conditions and the following
#     disclaimer in the documentation and/or other materials provided
#     with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS''
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE REGENTS OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
# OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be interpreted
# as representing official policies, either expressed or implied, of
# GRNET S.A.

from operator import mul, itemgetter
from fractions import Fraction
from random import random, seed
import logging
import sys

SVT_LOGGER = 'SVT'
LOGGER_FORMAT = '%(message)s'

logging.basicConfig(format=LOGGER_FORMAT)
logging.getLogger(SVT_LOGGER).setLevel(logging.INFO)

class Ballot:
    """A ballot class for Single Transferable Voting.

    The ballot class contains an ordered list of candidates (in
    decreasing order of preference) and an ordered list of weights
    (new weights are added to the front of the list). The index of the
    current preference (for the first count and subsequent rounds)
    is kept in an index.

    """

    candidates = []
    weights = [1]
    index = 0
    _value = 1

    def __init__(self, candidates=[]):
        self.candidates = candidates

    def add_weight(self, weight):
        self.weights.insert(0, weight)
        self._value *= weight

    def get_value(self):
        return self._value

def randomly_select_first(sequence, key):
    """Selects the first item of equals in a sorted sequence of items.

    For the given sorted sequence, returns the first item if it
    is different than the second; if there are ties so that there
    are items with equal values, it randomly selects among those items.
    The value of each item in the sequence is provided by applying the
    function key to the item. 

    """
    
    first_value = key(sequence[0])
    collected = []
    for item in sequence:
        if key(item) == first_value:
            collected.append(item)
        else:
            break
    random_index = int(random()*(len(collected)))
    return collected[random_index]
        
    
def redistribute_ballots(selected, hopefuls, allocated, weight):
    """Redistributes the ballots from selected to the hopefuls.

    Redistributes the ballots currently allocated to the selected
    candidate. The ballots are redistributed with the given weight.
    The total ballot allocation is given by the allocated dict.
    
    """

    logger = logging.getLogger(SVT_LOGGER)
    transferred = []

    for ballot in allocated[selected]:
        reallocated = False
        i = ballot.index + 1
        while not reallocated and i < len(ballot.candidates):
            recipient = ballot.candidates[i]
            if recipient in hopefuls:
                ballot.index = i
                ballot.add_weight(weight)
                if recipient in allocated:
                    allocated[recipient].append(ballot)
                else:
                    allocated[recipient] = [ballot]
                reallocated = True
                logger.info('T' + ' ' + selected + '->' + recipient
                            + ' (' + str(weight) + ')')
                transferred.append(ballot)
            else:
                i += 1
    allocated[selected][:] = [x for x in allocated[selected]
                              if x not in transferred ]
    
def count_stv(ballots, seats):
    """Performs a SVT vote for the given ballots and number of seats.
    """
    
    allocated = {}
    vote_count = {}
    candidates = []
    elected = []
    hopefuls = []

    seed()

    round = 1
    threshold = int(len(ballots) / (seats + 1)) + 1

    logger = logging.getLogger(SVT_LOGGER)
    
    # First round
    logger.info('R ' + str(round))
    for ballot in ballots:
        selected = ballot.candidates[0]
        for candidate in ballot.candidates:
            if candidate not in candidates:
                candidates.append(candidate)
        if selected in allocated:
            allocated[selected].append(ballot)
        else:
            allocated[selected] = [ballot]
        if selected in vote_count:
            vote_count[selected] += 1
        else:
            vote_count[selected] = 1

    hopefuls = [x for x in candidates]

    # Log initial count
    for candidate in candidates:
        logger.info('C ' + candidate + '=' + str(vote_count[candidate]))
        
    for (candidate, ballots) in allocated.iteritems():
        if len(ballots) >= threshold:
            hopefuls.remove(candidate)
            elected.append(candidate)
            logger.info('E ' + candidate)

    # Subsequent rounds
    # Check if the number of seats left is bigger than the number of
    # hopefuls; if so, all hopefuls will be elected
    elect_all = seats - len(elected) >= len(hopefuls)
    while len(elected) < seats and not elect_all:
        round += 1
        logger.info('R ' + str(round))
        vote_count_sorted = sorted(vote_count.iteritems(), key=itemgetter(1),
                                   reverse=True)
        best_candidate = randomly_select_first(vote_count_sorted,
                                               key=itemgetter(1))[0]
        surplus = vote_count[best_candidate] - threshold
        # If there is a surplus redistribute the best candidate's votes
        # according to their next preferences
        if surplus > 0:
            # Calculate the weight for this round
            weight = Fraction(surplus, vote_count[best_candidate])
            # Adjust the vote count for the best candidate to the threshold
            # (the vote count does not matter, as the candidate is already
            # elected).
            vote_count[best_candidate] = threshold
            # Find the next eligible preference for each one of the ballots
            # cast for the candidate, and transfer the vote to that
            # candidate with its value adjusted by the correct weight.
            redistribute_ballots(best_candidate, hopefuls, allocated, weight)
        # If there is no surplus, take the least hopeful candidate
        # (i.e., the hopeful candidate with the less votes) and
        # redistribute that candidate's votes.
        else:
            hopefuls_sorted = sorted(hopefuls, key=vote_count.get)
            worst_candidate = randomly_select_first(hopefuls_sorted,
                                                    key=vote_count.get)
            logger.info('D ' + worst_candidate)
            redistribute_ballots(worst_candidate, hopefuls, allocated, 1)
            hopefuls.remove(worst_candidate)
        # Calculate new votes and move from hopefuls to elected as necessary
        transferred = []
        for hopeful in hopefuls:
            vote_count[hopeful] = sum([x.get_value()
                                       for x in allocated[hopeful]])
            if vote_count[hopeful] >= threshold:
                elected.append(hopeful)
                transferred.append(hopeful)
                logger.info('E ' + hopeful)
        hopefuls[:] = [x for x in hopefuls if x not in transferred ]
        elect_all = seats - len(elected) >= len(hopefuls)

    # At the end of each round, check if all hopefuls are to be elected.    
    if elect_all:
        for hopeful in hopefuls:
            elected.append(hopeful)
            logger.info('E ' + hopeful)
        hopefuls = []

    return elected

if __name__ == "__main__":
    ballots = []
    for i in range(4):
        ballots.append(Ballot(("Orange",)))
    for i in range(2):
        ballots.append(Ballot(("Pear", "Orange")))
    for i in range(8):
        ballots.append(Ballot(("Chocolate", "Strawberry")))
    for i in range(4):
        ballots.append(Ballot(("Chocolate", "Sweets")))
    ballots.append(Ballot(("Strawberry",)))
    ballots.append(Ballot(("Sweets",)))

    elected = count_stv(ballots, 3)

    print "Results:"
    for candidate in elected:
        print candidate
