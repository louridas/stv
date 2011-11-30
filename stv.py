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
import math
import csv
import argparse

SVT_LOGGER = 'SVT'
LOGGER_FORMAT = '%(levelname)s %(message)s'
LOG_MESSAGE = "{action} {desc}"

class Action:
    COUNT_ROUND = "@ROUND"
    TRANSFER = ">TRANSFER"
    ELIMINATE = "-ELIMINATE"
    ELECT = "+ELECT"
    COUNT = ".COUNT"
    RANDOM = "*RANDOM"
    THRESHOLD = "^THRESHOLD"

class Ballot:
    """A ballot class for Single Transferable Voting.

    The ballot class contains an ordered list of candidates (in
    decreasing order of preference) and an ordered list of weights
    (new weights are added to the front of the list). The index of the
    current preference (for the first count and subsequent rounds)
    is also kept.

    """

    candidates = []
    weights = [1.0]
    current_preference = 0
    _value = 1.0

    def __init__(self, candidates=[]):
        self.candidates = filter(None, candidates)

    def add_weight(self, weight):
        self.weights.insert(0, weight)
        self._value *= weight

    def get_value(self):
        return self._value
    
def randomly_select_first(sequence, key, action, random_generator=None):
    """Selects the first item of equals in a sorted sequence of items.

    For the given sorted sequence, returns the first item if it
    is different than the second; if there are ties so that there
    are items with equal values, it randomly selects among those items.
    The value of each item in the sequence is provided by applying the
    function key to the item. The action parameter indicates the context
    in which the random selection takes place (election or elimination).
    random_generator, if given, is the function that produces the random
    selection.

    """

    first_value = key(sequence[0])
    collected = []
    for item in sequence:
        if key(item) == first_value:
            collected.append(item)
        else:
            break
    index = 0
    selected = collected[index]
    num_eligibles = len(collected)
    if (num_eligibles > 1):
        if random_generator is None:
            index = int(random() * num_eligibles)
            selected = collected[index]
        else:
            if not random_generator:
                print "Missing value for random selection"
                sys.exit(1)
            selected = random_generator.pop(0)
        logger = logging.getLogger(SVT_LOGGER)
        description = "{0} from {1} to {2}".format(selected, collected, action)
        logger.info(LOG_MESSAGE.format(action=Action.RANDOM, desc=description))
    return selected
        
    
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
    # Keep a hash of ballot moves for logging purposes.
    # Keys are a tuple of the form (from_recipient, to_recipient, value)
    # where value is the current value of the ballot. Each tuple points
    # to the ballot being moved.
    moves = {}

    for ballot in allocated[selected]:
        reallocated = False
        i = ballot.current_preference + 1
        while not reallocated and i < len(ballot.candidates):
            recipient = ballot.candidates[i]
            if recipient in hopefuls:
                ballot.current_preference = i
                ballot.add_weight(weight)
                current_value = ballot.get_value()
                if recipient in allocated:
                    allocated[recipient].append(ballot)
                else:
                    allocated[recipient] = [ballot]
                if recipient in vote_count:
                    vote_count[recipient] += current_value
                else:
                    vote_count[recipient] = current_value
                vote_count[selected] -= current_value
                reallocated = True
                if (selected, recipient, current_value) in moves:
                    moves[(selected, recipient, current_value)].append(ballot)
                else:
                    moves[(selected, recipient, current_value)] = [ballot]
                transferred.append(ballot)
            else:
                i += 1
    for move, ballots in moves.iteritems():
        times = len(ballots)
        description =  "from {0} to {1} {2}*{3}={4}".format(move[0],
                                                            move[1],
                                                            times,
                                                            move[2],
                                                            times * move[2])
        logger.debug(LOG_MESSAGE.format(action=Action.TRANSFER,
                                        desc=description))
    allocated[selected][:] = [x for x in allocated[selected]
                              if x not in transferred ]
    
def count_stv(ballots, droop, seats, rnd_gen=None):
    """Performs a SVT vote for the given ballots and number of seats.
    
    """
    
    allocated = {} # The allocation of ballots to candidates
    vote_count = {} # A hash of ballot counts, indexed by candidates
    candidates = [] # All candidates
    elected = [] # The candidates that have been elected
    hopefuls = [] # The candidates that may be elected

    seed()

    if droop:
            threshold = int(1 + (len(ballots) / (seats + 1.0)))
    else:
        threshold = int(math.ceil(1 + len(ballots) / (seats + 1.0)))

    logger = logging.getLogger(SVT_LOGGER)
    logger.info(LOG_MESSAGE.format(action=Action.THRESHOLD,
                                   desc=threshold))
    
    # Do initial count
    for ballot in ballots:
        selected = ballot.candidates[0]
        for candidate in ballot.candidates:
            if candidate not in candidates:
                candidates.append(candidate)
                vote_count[candidate] = 0
        if selected in allocated:
            allocated[selected].append(ballot)
        else:
            allocated[selected] = [ballot]
        vote_count[selected] += 1

    # In the beginning, all candidates are hopefuls
    hopefuls = [x for x in candidates]

    # Start rounds
    current_round = 1
    num_elected = len(elected)
    num_hopefuls = len(hopefuls)
    while num_elected < seats and num_hopefuls > 0:
        logger.info(LOG_MESSAGE.format(action=Action.COUNT_ROUND,
                                       desc=current_round))
        # Log count
        description  = ';'.join(map(lambda x: "{0} = {1}".format(x,
                                                                 vote_count[x]),
                                    hopefuls))
        logger.info(LOG_MESSAGE.format(action=Action.COUNT,
                                       desc=description))
        hopefuls_sorted = sorted(hopefuls, key=vote_count.get, reverse=True )
        # If there is a surplus try to redistribute the best candidate's votes
        # according to their next preferences
        surplus = vote_count[hopefuls_sorted[0]] - threshold
        remaining_seats = seats - num_elected
        if surplus >= 0 or num_hopefuls <= remaining_seats:
            best_candidate = randomly_select_first(hopefuls_sorted,
                                                   key=vote_count.get,
                                                   action=Action.ELECT,
                                                   random_generator=rnd_gen)
            hopefuls.remove(best_candidate)
            elected.append((best_candidate, current_round,
                            vote_count[best_candidate]))
            logger.info(LOG_MESSAGE.format(action=Action.ELECT,
                                           desc=best_candidate
                                           + " = " + str(vote_count[best_candidate])))
            if surplus > 0:
                # Calculate the weight for this round
                weight = float(surplus) / vote_count[best_candidate]
                # Find the next eligible preference for each one of the ballots
                # cast for the candidate, and transfer the vote to that
                # candidate with its value adjusted by the correct weight.
                redistribute_ballots(best_candidate, hopefuls, allocated,
                                     weight, vote_count)
        # If there is no surplus, take the least hopeful candidate
        # (i.e., the hopeful candidate with the less votes) and
        # redistribute that candidate's votes.
        else:
            hopefuls_sorted.reverse()
            worst_candidate = randomly_select_first(hopefuls_sorted,
                                                    key=vote_count.get,
                                                    action=Action.ELIMINATE,
                                                    random_generator=rnd_gen)
            hopefuls.remove(worst_candidate)
            logger.info(LOG_MESSAGE.format(action=Action.ELIMINATE,
                                           desc=worst_candidate
                                           + " = " + str(vote_count[worst_candidate])))
            redistribute_ballots(worst_candidate, hopefuls, allocated, 1.0,
                                 vote_count)
            
        current_round += 1
        num_hopefuls = len(hopefuls)
        num_elected = len(elected)

    return elected, vote_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Perform STV')
    parser.add_argument('-b', '--ballots', default='sys.stdin',
                        dest='ballots_file', help='input ballots file')
    parser.add_argument('-n', '--not_droop', action="store_false",
                        dest='droop', help="don't use droop quota")
    parser.add_argument('-s', '--seats', type=int, default=0,
                        dest='seats', help='number of seats')
    parser.add_argument('-r', '--random', nargs='*',
                        dest='random', help='random selection results')
    parser.add_argument('-l', '--loglevel', default=logging.INFO,
                        dest='loglevel', help='logging level')
    args = parser.parse_args()
    logging.basicConfig(format=LOGGER_FORMAT)
    logging.getLogger(SVT_LOGGER).setLevel(args.loglevel)
    ballots = []
    ballots_file = sys.stdin
    if args.ballots_file != 'sys.stdin':
        ballots_file = open(args.ballots_file, 'U')
    ballots_reader = csv.reader(ballots_file, delimiter=',',
                                quotechar='"',
                                skipinitialspace = True)
    for ballot in ballots_reader:
        ballots.append(Ballot(ballot))

    if args.seats == 0:
        args.seats = len(ballots) / 2
    (elected, vote_count) = count_stv(ballots, args.droop, args.seats,
                                      args.random)

    print "Results:"
    for result in elected:
        print result
