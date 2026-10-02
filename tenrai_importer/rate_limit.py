import time
from collections import deque

class RateLimiter:
    def __init__(self, requests_per_second: float, requests_per_minute: int):
        self.min_interval = 1.0 / requests_per_second
        self.rpm = requests_per_minute
        self.timestamps = deque()
        self.last_request = 0.0

    def wait(self):
        while True:
            now = time.monotonic()
            delay = self.min_interval - (now - self.last_request)
            if delay > 0:
                time.sleep(delay)
                continue

            while self.timestamps and now - self.timestamps[0] >= 60:
                self.timestamps.popleft()

            if len(self.timestamps) < self.rpm:
                now = time.monotonic()
                self.timestamps.append(now)
                self.last_request = now
                return

            sleep_for = max(0.0, 60 - (now - self.timestamps[0]) + 0.05)
            time.sleep(sleep_for)
