import datetime


# The mem-cache should store its statistics every 5 seconds
# use list
class Stats:
    """
    class for memcache statistics
    number of requests(for calling all 5 operations): reqServed_num
    miss = missing times on GET: missCount
    hit = hitting times on GET: hitCount
    hit rate = hit / hit+miss
    miss rate = miss / hit+miss
    """

    def __init__(self):
        self.reqServed_num = 0  # total request number to be added during run time
        self.missCount = 0
        self.hitCount = 0
        self.total_image_size = 0
        self.id = '-'

        """////no out////"""
        self.listOfStat = []  # list of tuple in the format (miss or hit str, timestamp)