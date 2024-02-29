from stv import DefaultQuotaCallback, Action, LOG_MESSAGE

class QuotaCallback(DefaultQuotaCallback):

    def __init__(self, seats, quota_limit, logger):
        super().__init__(seats, quota_limit)
        self.overruled = 0

    def __call__(self, candidate, constituency_map, elected_per_constituency):
        quota_exceeded = super().__call__(candidate, 
                                          constituency_map, elected_per_constituency)
        if not quota_exceeded:
            return False
        diff = self.seats - len(constituency_map)
        if diff > 0 and self.overruled < diff: 
            self.overruled += 1
            d = ("Quota overruled. Constituencies fewer than seats.")
            msg = LOG_MESSAGE.format(action=Action.COMMENT.value, desc=d)
            self.logger.info(msg)
            return False
        return True