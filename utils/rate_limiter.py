class RateLimiter:
    def __init__(self, rate_limit, per):
        """
        Initializes the RateLimiter.

        :param rate_limit: Number of messages allowed.
        :param per: Time period in seconds for the rate limit.
        """
        self.rate_limit = rate_limit
        self.per = per
        self.timestamps = []

    def is_allowed(self):
        """
        Checks if a new message can be sent based on the rate limit.

        :return: True if allowed, False otherwise.
        """
        current_time = time.time()
        # Remove timestamps that are older than the time window
        self.timestamps = [ts for ts in self.timestamps if current_time - ts < self.per]

        if len(self.timestamps) < self.rate_limit:
            self.timestamps.append(current_time)
            return True
        return False

import time
