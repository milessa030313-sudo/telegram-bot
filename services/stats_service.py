class StatsService:
    def __init__(self):
        self.data = []  # Store statistics data here

    def add_stat(self, stat):
        self.data.append(stat)  # Add a new statistic

    def get_stats(self):
        return self.data  # Return the collected statistics

    def clear_stats(self):
        self.data = []  # Clear all collected statistics
