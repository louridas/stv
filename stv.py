# Copyright 2011, 2022 GRNET S.A. All rights reserved.
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

import random
import logging
import sys
import math
import csv
import argparse

SVT_LOGGER = 'SVT'
LOGGER_FORMAT = '%(message)s'
LOG_MESSAGE = "{action} {desc}"

class Action:
    COUNT_ROUND = "@ROUND"
    TRANSFER = ">TRANSFER"
    ELIMINATE = "-ELIMINATE"
    QUOTA = "!QUOTA"
    ELECT = "+ELECT"
    COUNT = ".COUNT"
    ZOMBIES = "~ZOMBIES"
    RANDOM = "*RANDOM"
    THRESHOLD = "^THRESHOLD"
    ROUND_ROBIN = "oROUND_ROBIN"
    CONSTITUENCY_TURN = "#CONSTITUENCY_TURN"
    SHUFFLE = "xSHUFFLE"
    SORT = "/SORT"
   
class Ballot:
    """A ballot class for Single Transferable Voting.

    The ballot class contains an ordered list of candidates (in
    decreasing order of preference). The index of the current
    holder of the ballot (for the first count and subsequent
    rounds) is also kept.
    """

    candidates = []
    current_holder = 0

    def __init__(self, candidates=[]):
        self.candidates = candidates
    
def select_first_rnd(sequence, key, action):
    """Selects the first item in a sorted sequence breaking ties randomly.

    For the given sorted sequence, returns the first item if it
    is different than the second; if there are ties so that there
    are items with equal values, it randomly selects among those items.
    The value of each item in the sequence is provided by applying the
    function key to the item. The action parameter indicates the context
    in which the random selection takes place (election or elimination).
    """

    first_value = key(sequence[0])
    collected = [ item for item in sequence if key(item) == first_value ]
    index = 0
    selected = collected[index]
    num_eligibles = len(collected)
    if (num_eligibles > 1):
        index = int(random.random() * num_eligibles)
        selected = collected[index]
        logger = logging.getLogger(SVT_LOGGER)
        description = f"{selected} from {collected} to {action}"
        logger.info(LOG_MESSAGE.format(action=Action.RANDOM, desc=description))
    return selected
        

def sort_rnd(sequence, key, reverse):
    """Sorts the sequence breaking ties randomnly.

    The sequence is sorted in place and returned, using the key
    callable as sorting key and reverse to determine whether the sort
    will be ascending or descending. The function first shuffles the
    sequence randomly, and the sorts the shuffled sequence. As the
    sort is stable, the resulting sorted sequence has ties broken
    randomly.
    """
    
    sequence_str = str(sequence)
    random.shuffle(sequence)
    shuffled_sequence_str = str(sequence)
    description = ('from ' + sequence_str +
                   ' to ' + shuffled_sequence_str)
    logger.info(LOG_MESSAGE.format(action=Action.SHUFFLE,
                                   desc=description))
    sorted_sequence = sorted(
        sequence,
        key=key,
        reverse=reverse)
    description = ('from' + shuffled_sequence_str +
                   ' to ' + str(sorted_sequence))
    logger.info(LOG_MESSAGE.format(action=Action.SORT, desc=description))
    return sorted_sequence

def redistribute_ballots(selected, transfer_volume, hopefuls, allocated,
                         vote_count):
    """Redistributes the ballots from selected to the hopefuls.

    Redistributes the ballots currently allocated to the selected
    candidate among the hopeful candidates. The number of ballots to
    be redistributed is given bu transfer_volume. The total ballot
    allocation is given by the allocated map, which is modified
    accordingly. The current vote count is given by vote_count and is
    adjusted according to the redistribution.
    """

    logger = logging.getLogger(SVT_LOGGER)
    transfers = {}
    transferred = []
    num_transfers = 0
    
    for ballot in allocated[selected]:
        reallocated = False
        i = ballot.current_holder + 1
        while not reallocated and i < len(ballot.candidates):
            target = ballot.candidates[i]
            if target in hopefuls:
                ballot.current_holder = i
                if target in allocated:
                    allocated[target].append(ballot)
                else:
                    allocated[target] = [ballot]
                if (selected, target) in transfers:
                    transfers[(selected, target)].append(ballot)
                else:
                    transfers[(selected, target)] = [ballot]
                transferred.append(ballot)
                num_transfers += 1
                reallocated = True                
            else:
                i += 1
    if num_transfers == 0:
        return
    transfer_unit = transfer_volume / num_transfers
    for (selected, target), ballots in transfers.items():
        times = len(ballots)
        transfer_value = transfer_unit * times
        if target in vote_count:
            vote_count[target] += transfer_value
        else:
            vote_count[target] = transfer_value
        vote_count[selected] -= transfer_value
        description =  "from {0} to {1} {2} * {3} = {4}".format(
            selected,
            target,
            times,
            transfer_unit,
            transfer_value)
        logger.debug(LOG_MESSAGE.format(action=Action.TRANSFER,
                                        desc=description))
    allocated[selected][:] = [
        x for x in allocated[selected]
        if x not in transferred
    ]

def elect_reject(candidate, vote_count, constituencies_map, quota_limit,
                 current_round, elected, rejected, constituencies_elected):
    """Elects or rejects the candidate.

    Otherwise, if there are no quota limits, the candidate is elected.
    If there are quota limits, the candidate is either elected or
    rejected, if the quota limits are exceeded. The elected and
    rejected lists are modified accordingly, as well as the
    constituencies_elected map.

    Returns true if the candidate is elected, false otherwise.
    """
    
    
    logger = logging.getLogger(SVT_LOGGER)
    quota_exceeded = False
    # If there is a quota limit, check if it is exceeded
    if quota_limit > 0 and candidate in constituencies_map:
        current_constituency = constituencies_map[candidate]
        if constituencies_elected[current_constituency] >= quota_limit:
            quota_exceeded = True
    # If the quota limit has been exceeded, reject the candidate
    if quota_exceeded:
        rejected.append((candidate, current_round, vote_count[candidate]))
        d = (f'{candidate} {current_constituency} '
             f'{constituencies_elected[current_constituency]} '
             f'>= {quota_limit}')
        msg = LOG_MESSAGE.format(action=Action.QUOTA, desc=d)
        logger.info(msg)
        return False
    # Otherwise, elect the candidate
    else:
        elected.append((candidate, current_round, vote_count[candidate]))
        if constituencies_map:
            current_constituency = constituencies_map[candidate]
            constituencies_elected[current_constituency] += 1
        d = candidate + " = " + str(vote_count[candidate])
        msg = LOG_MESSAGE.format(action=Action.ELECT, desc=d)
        logger.info(msg)
        return True

def count_description(vote_count, candidates):
    """Returns a string with count results.

    The string is of the form of {0} = {1} separated by ; where each
    {0} is a candidate and each {1} is the corresponding vote count.
    The count is in decreasing number of votes, with tied candidates
    broken lexicographically.
    """

    count_results = ((c, vote_count[c]) for c in candidates)
    count_results = sorted(count_results,
                           key=lambda item: (-item[1], item[0]))
    return  ';'.join([ f"{candidate} = {votes}"
                       for candidate, votes in count_results ])


def elect_round_robin(vote_count, constituencies, constituencies_map,
                      quota_limit, current_round, elected, rejected,
                      constituencies_elected, seats, num_elected):
    """Elects candidates going round robin around the orphan constituencies.

    If there are orphan constituencies, i.e., constituencies with no
    elected candidates, try to elect them by going through each of
    these constituencies, in decreasing order by side, with ties
    broken randomly. In each constituency take each candidate in
    decreasing orded by number of votes.
    """

    logger = logging.getLogger(SVT_LOGGER)
    
    orphan_constituencies = [
        (constituency, sz) for constituency, sz in constituencies.items()
        if constituencies_elected[constituency] == 0
    ]
    
    if len(orphan_constituencies) > 0:
        sorted_orphan_constituencies = sort_rnd(orphan_constituencies,
                                                key=lambda item: item[1],
                                                reverse=True)
        # Put the candidate votes for each sorted orphan constituency (soc)
        # in a dictionary keyed by candidate with their votes as value.
        soc_candidates = {} 
        soc_candidates_num = 0
        for soc, _ in sorted_orphan_constituencies:
            # Get the vote count for the sorted orphan constituency.
            soc_vote_count = [
                (candidate, count) for candidate, count in vote_count.items()
                if constituencies_map[candidate] == soc
            ]
            # Sort them by vote count, descending, so that we will be
            # able to use select_first_rnd on them.
            soc_vote_count.sort(key=lambda item:item[1], reverse=True)
            soc_candidates[soc] = soc_vote_count
            soc_candidates_num += len(soc_vote_count)
        turn = 0
        desc = ('[' +
                ', '.join([ str(c) for c in sorted_orphan_constituencies ])
                +']')
        logger.info(LOG_MESSAGE.format(action=Action.ROUND_ROBIN,
                                       desc=desc))
        while (seats - num_elected) > 0 and soc_candidates_num > 0:
            best_candidate = None
            while best_candidate is None:
                constituency_turn = sorted_orphan_constituencies[turn][0]
                candidates_turn = soc_candidates[constituency_turn]
                desc = f'{constituency_turn} {candidates_turn}'
                logger.info(LOG_MESSAGE.format(action=Action.CONSTITUENCY_TURN,
                                               desc=desc))
                if len(candidates_turn) > 0:
                    best_candidate_vote = select_first_rnd(
                        candidates_turn,
                        key=lambda item: item[0],
                        action=Action.ELECT)
                    best_candidate = best_candidate_vote[0]
                    candidates_turn.remove(best_candidate_vote)
                    soc_candidates_num -= 1
                turn = (turn + 1) % len(orphan_constituencies)
            elect_reject(best_candidate, vote_count, 
                         constituencies_map, quota_limit, 
                         current_round,
                         elected, rejected,
                         constituencies_elected)
            num_elected = len(elected)
    return num_elected

def count_stv(ballots, seats,
              constituencies,
              constituencies_map,
              quota_limit = 0,
              seed=None):
    """Performs a STV vote for the given ballots and number of seats.

    The constituencies argument is a map of constituencies to the
    number of voters. The constituencies_map argument is a map of
    candidates to constituencies, if any. The quota_limit, if
    different than zero, is the limit of candidates that can be
    elected by a constituency.
    """

    random.seed(a=seed)
    logger = logging.getLogger(SVT_LOGGER)
    
    allocated = {} # The allocation of ballots to candidates.
    vote_count = {} # A hash of ballot counts, indexed by candidates.
    candidates = [] # All candidates.
    elected = [] # The candidates that have been elected.
    hopefuls = [] # The candidates that may be elected.
    # The candidates that have been eliminated because of low counts.
    eliminated = []
    # The candidates that have been eliminated because of quota restrictions.
    rejected = []
    # The number of candidates elected per constituency.
    constituencies_elected = {}
    for (candidate, constituency) in constituencies_map.items():
        constituencies_elected[constituency] = 0
        if candidate not in allocated:
            allocated[candidate] = []
        if candidate not in candidates: # check not really needed
            candidates.append(candidate)
            vote_count[candidate] = 0

    threshold = int(len(ballots) / (seats + 1.0)) + 1

    logger.info(LOG_MESSAGE.format(action=Action.THRESHOLD,
                                   desc=threshold))
    
    # Do initial count
    for ballot in ballots:
        selected = ballot.candidates[0]
        for candidate in ballot.candidates:
            if candidate not in candidates:
                candidates.append(candidate)
                vote_count[candidate] = 0
            if candidate not in allocated:
                allocated[candidate] = []
        allocated[selected].append(ballot)
        vote_count[selected] += 1

    # In the beginning, all candidates are hopefuls.
    hopefuls = [x for x in candidates]

    # Start rounds.
    current_round = 1
    num_elected = len(elected)
    num_hopefuls = len(hopefuls)    
    while num_elected < seats and num_hopefuls > 0:
        # Log round.
        logger.info(LOG_MESSAGE.format(action=Action.COUNT_ROUND,
                                       desc=current_round))
        # Log count.
        description  = count_description(vote_count, hopefuls)
       
        logger.info(LOG_MESSAGE.format(action=Action.COUNT,
                                       desc=description))
        hopefuls_sorted = sorted(hopefuls, key=vote_count.get, reverse=True )
        # If there is a surplus record it, so that we can try to
        # redistribute the best candidate's votes according to their
        # next preferences.
        received = vote_count[hopefuls_sorted[0]]
        surplus = received - threshold
        # If there is a candidate that reaches the threshold,
        # try to elect them, respecting quota limits.
        if surplus >= 0:
            best_candidate = select_first_rnd(hopefuls_sorted,
                                              key=vote_count.get,
                                              action=Action.ELECT)
            hopefuls.remove(best_candidate)
            was_elected = elect_reject(best_candidate, vote_count,
                                       constituencies_map, quota_limit,
                                       current_round, 
                                       elected, rejected,
                                       constituencies_elected)
            if not was_elected and received > 0:
                redistribute_ballots(best_candidate, received, hopefuls,
                                     allocated, vote_count)
            elif surplus > 0:
                # Find the next eligible preference for each one of the ballots
                # cast for the candidate, and transfer the surplus votes
                # to that candidate.
                redistribute_ballots(best_candidate, surplus, hopefuls,
                                     allocated, vote_count)
        # If nobody can get elected, take the least hopeful candidate
        # (i.e., the hopeful candidate with the fewer votes) and
        # redistribute that candidate's votes.
        else:
            hopefuls_sorted.reverse()
            worst_candidate = select_first_rnd(hopefuls_sorted,
                                               key=vote_count.get,
                                               action=Action.ELIMINATE)
            hopefuls.remove(worst_candidate)
            eliminated.append(worst_candidate)
            desc = f'{worst_candidate} = {vote_count[worst_candidate]}'
            msg = LOG_MESSAGE.format(action=Action.ELIMINATE, desc=desc)
            logger.info(msg)
            received = vote_count[worst_candidate]
            if received > 0:
                redistribute_ballots(worst_candidate, received, hopefuls,
                                     allocated, vote_count)
            
        current_round += 1
        num_hopefuls = len(hopefuls)
        num_elected = len(elected)

    # If there are still seats to be filled, they will be filled in a
    # round-robin fashion by those constituencies that are not
    # represented, in decreasing order of voters.
    if (seats - num_elected) > 0:
        num_elected = elect_round_robin(vote_count,
                                        constituencies,
                                        constituencies_map,
                                        quota_limit, 
                                        current_round,
                                        elected, rejected,
                                        constituencies_elected,
                                        seats,
                                        num_elected)
 
    # If there is either a candidate with surplus votes, or
    # there are hopeful candidates beneath the threshold.
    while (seats - num_elected) > 0 and len(eliminated) > 0:
        logger.info(LOG_MESSAGE.format(action=Action.COUNT_ROUND,
                                       desc=current_round))
        description  = count_description(vote_count, eliminated)        
        logger.info(LOG_MESSAGE.format(action=Action.ZOMBIES,
                                       desc=description))

        best_candidate = eliminated.pop()
        elect_reject(best_candidate, vote_count, 
                     constituencies_map, quota_limit, 
                     current_round,
                     elected, rejected, constituencies_elected)
        current_round += 1
        num_elected = len(elected)

    return elected, vote_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Perform STV')
    parser.add_argument('-b', '--ballots', default='sys.stdin',
                        dest='ballots_file', help='input ballots file')
    parser.add_argument('-s', '--seats', type=int, default=0,
                        dest='seats', help='number of seats')
    parser.add_argument('-c', '--constituencies',
                        dest='constituencies_file',
                        help='input constituencies file')    
    parser.add_argument('-q', '--quota', type=int, default=0,
                        dest='quota', help='constituency quota')
    parser.add_argument('-r', '--random', dest='random_seed',
                        type=lambda x: int(x, 0),
                        help='random seed')
    parser.add_argument('-l', '--loglevel', default=logging.INFO,
                        dest='loglevel', help='logging level')
    args = parser.parse_args()

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    logger = logging.getLogger(SVT_LOGGER)
    logger.setLevel(args.loglevel)
    logger.addHandler(stream_handler)

    ballots = []
    ballots_file = sys.stdin
    if args.ballots_file != 'sys.stdin':
        ballots_file = open(args.ballots_file)
    ballots_reader = csv.reader(ballots_file, delimiter=',',
                                quotechar='"',
                                skipinitialspace=True)
    for ballot in ballots_reader:
        ballots.append(Ballot(ballot))

    if args.seats == 0:
        args.seats = len(ballots) / 2

    constituencies_map = {}
    constituencies = {}
    if args.constituencies_file:
        with open(args.constituencies_file) as constituencies_file:
             constituencies_reader = csv.reader(constituencies_file,
                                                    delimiter=',',
                                                    quotechar='"',
                                                    skipinitialspace=True)
             for constituency in constituencies_reader:
                 constituency_name = constituency[0]
                 constituency_size = int(constituency[1])
                 constituencies[constituency_name] = constituency_size
                 for candidate in constituency[2:]:
                     constituencies_map[candidate] = constituency_name

    (elected, vote_count) = count_stv(ballots,
                                      args.seats,
                                      constituencies,
                                      constituencies_map,
                                      args.quota,
                                      args.random_seed)

    print("Results:")
    for result in elected:
        print(result)
