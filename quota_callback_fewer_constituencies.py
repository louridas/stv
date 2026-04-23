from stv import DefaultQuotaCallback, Action, LOG_MESSAGE

class QuotaCallback(DefaultQuotaCallback):
    """
    Quota callback for constituencies fewer than seats.
    
    Quota callback that overrules the quota when the number of constituencies
    is fewer than the number of seats. 
    """

    def __init__(self, seats, quota_limit, kw_args):
        
        super().__init__(seats, quota_limit, kw_args)
        self.higher_quota = kw_args['higher_quota']
        self.overruled = 0

    def __call__(self,
                 candidate,
                 constituency_map,
                 elected_per_constituency):
        
        quota_exceeded = super().__call__(
            candidate, 
            constituency_map,
            elected_per_constituency
        )
        if not quota_exceeded:
            return False
        diff = self.seats - len(set(constituency_map.values()))
        constituency = constituency_map[candidate]
        num_elected = elected_per_constituency[constituency]
        if (diff > 0
            and self.overruled < diff
            and num_elected < self.higher_quota):
            self.overruled += 1
            d = ("Quota overruled. Constituencies fewer than seats.")
            msg = LOG_MESSAGE.format(action=Action.COMMENT.value, desc=d)
            self.logger.info(msg)
            return False
        return True
