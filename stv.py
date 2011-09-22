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
from random import random, seed
import logging
import sys

SVT_LOGGER = 'SVT'
LOGGER_FORMAT = '%(levelname)s %(message)s'
LOG_MESSAGE = "{action} {desc}"

class Action:
    COUNT_ROUND = "ROUND"
    TRANSFER = "TRANSFER"
    ELIMINATE = "ELIMINATE"
    ELECT = "ELECT"
    COUNT = "COUNT"
    RANDOM = "RANDOM"
    
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
    weights = [1.0]
    index = 0
    _value = 1.0

    def __init__(self, candidates=[]):
        self.candidates = candidates

    def add_weight(self, weight):
        self.weights.insert(0, weight)
        self._value *= weight

    def get_value(self):
        return self._value

def randomly_select_first(sequence, key, action):
    """Selects the first item of equals in a sorted sequence of items.

    For the given sorted sequence, returns the first item if it
    is different than the second; if there are ties so that there
    are items with equal values, it randomly selects among those items.
    The value of each item in the sequence is provided by applying the
    function key to the item. The action parameter indicates the context
    in which the random selection takes place (election or elimination).

    """
    
    first_value = key(sequence[0])
    collected = []
    for item in sequence:
        if key(item) == first_value:
            collected.append(item)
        else:
            break
    index = 0
    if (len(collected) > 1):
        index = int(random()*(len(collected)))
        selected = collected[random_index]
        logger = logging.getLogger(SVT_LOGGER)
        description = "{0} from {1} to {2}".format(selected, collected, action)
        logger.info(LOG_MESSAGE.format(action=Action.RANDOM, desc=description))
    return collected[index]
        
    
def redistribute_ballots(selected, hopefuls, allocated, weight, vote_count):
    """Redistributes the ballots from selected to the hopefuls.

    Redistributes the ballots currently allocated to the selected
    candidate. The ballots are redistributed with the given weight.
    The total ballot allocation is given by the allocated dict. The current
    vote count is given by vote_count and is adjusted according to the
    redistribution.
    
    """

    logger = logging.getLogger(SVT_LOGGER)
    transferred = []
    moves = {}

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
                if recipient in vote_count:
                    vote_count[recipient] += (1 * weight)
                else:
                    vote_count[recipient] = 1 * weight
                reallocated = True
                if (selected, recipient) in moves:
                    moves[(selected, recipient)] += 1
                else:
                    moves[(selected, recipient)] = 1
                transferred.append(ballot)
            else:
                i += 1
    for move, times in moves.iteritems():
        description =  "{0} -> {1} {2}*{3}={4}".format(move[0], move[1], times,
                                                       weight, times*weight)
        logger.info(LOG_MESSAGE.format(action=Action.TRANSFER,
                                       desc=description))
    allocated[selected][:] = [x for x in allocated[selected]
                              if x not in transferred ]
    vote_count[selected] -= (len(transferred) * weight)
    
def count_stv(ballots, seats):
    """Performs a SVT vote for the given ballots and number of seats.
    """
    
    allocated = {}
    vote_count = {}
    candidates = []
    elected = []
    hopefuls = []

    seed()

    current_round = 1
    threshold = int(len(ballots) / (seats + 1)) + 1

    logger = logging.getLogger(SVT_LOGGER)
    
    # First round
    logger.info(LOG_MESSAGE.format(action=Action.COUNT_ROUND,
                                   desc=current_round))
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
    description  = ';'.join(map(lambda x: "{0} = {1}".format(x, vote_count[x]),
                                candidates))
    logger.info(LOG_MESSAGE.format(action=Action.COUNT,
                                   desc=description))
    for (candidate, ballots) in allocated.iteritems():
        if len(ballots) >= threshold:
            hopefuls.remove(candidate)
            elected.append(candidate)
            logger.info(LOG_MESSAGE.format(action=Action.ELECT,
                                           desc=candidate))

    # Subsequent rounds
    # Check if the number of seats left is bigger than the number of
    # hopefuls; if so, all hopefuls will be elected
    elect_all = seats - len(elected) >= len(hopefuls)
    while len(elected) < seats and not elect_all:
        current_round += 1
        logger.info(LOG_MESSAGE.format(action=Action.COUNT_ROUND,
                                       desc=current_round))
        # Filter candidates with surplus votes. These do not contain
        # candidates whose votes have been transferred in previous
        # rounds, since these candidates do not have surplus votes
        # any more.
        surplus_voted = filter(lambda x: vote_count[x] > threshold, vote_count)
        surplus_sorted = sorted(surplus_voted, vote_count.get, reverse=True)
        # If there is a surplus redistribute the best candidate's votes
        # according to their next preferences
        if len(surplus_voted) > 0:
            best_candidate = randomly_select_first(surplus_sorted,
                                                   key=vote_count.get,
                                                   action=Action.ELECT)
            surplus = vote_count[best_candidate] - threshold
            # Calculate the weight for this round
            weight = float(surplus) / vote_count[best_candidate]
            # Find the next eligible preference for each one of the ballots
            # cast for the candidate, and transfer the vote to that
            # candidate with its value adjusted by the correct weight.
            redistribute_ballots(best_candidate, hopefuls, allocated, weight,
                                 vote_count)
        # If there is no surplus, take the least hopeful candidate
        # (i.e., the hopeful candidate with the less votes) and
        # redistribute that candidate's votes.
        else:
            hopefuls_sorted = sorted(hopefuls, key=vote_count.get)
            worst_candidate = randomly_select_first(hopefuls_sorted,
                                                    key=vote_count.get,
                                                    action=Action.ELIMINATE)
            logger.info(LOG_MESSAGE.format(action=Action.ELIMINATE,
                                           desc=worst_candidate))
            redistribute_ballots(worst_candidate, hopefuls, allocated, 1.0,
                                 vote_count)
            hopefuls.remove(worst_candidate)
        # Move from hopefuls to elected as necessary
        transferred = []
        for hopeful in hopefuls:
            if vote_count[hopeful] >= threshold:
                elected.append(hopeful)
                transferred.append(hopeful)
                logger.info(LOG_MESSAGE.format(action=Action.ELECT,
                                               desc=hopeful))
        hopefuls[:] = [x for x in hopefuls if x not in transferred ]

        # At the end of each round, check if all hopefuls are to be elected.
        elect_all = seats - len(elected) >= len(hopefuls)
        if elect_all:
            for hopeful in hopefuls:
                elected.append(hopeful)
                logger.info(LOG_MESSAGE.format(action=Action.ELECT,
                                               desc=hopeful))
            hopefuls = []

        # Log count at the end of the round
        description  = ';'.join(map(lambda x: "{0} = {1}".format(x,
                                                                 vote_count[x]),
                                    candidates))
        logger.info(LOG_MESSAGE.format(action=Action.COUNT,
                                       desc=description))


    return elected, vote_count

if __name__ == "__main__":
    # Test data from http://en.wikipedia.org/wiki/Single_transferable_vote
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

    (elected, vote_count) = count_stv(ballots, 3)

    print "Results:"
    for candidate in elected:
        print candidate, vote_count[candidate]
