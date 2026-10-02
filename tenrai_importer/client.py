import random
import time
import requests

from .config import Config
from .rate_limit import RateLimiter

RETRYABLE = {500, 502, 503, 504}

class TenraiError(RuntimeError):
    pass

class TenraiClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": config.user_agent,
        })
        if config.server_key:
            self.session.headers["X-Server-Key"] = config.server_key
        self.limiter = RateLimiter(
            config.requests_per_second,
            config.requests_per_minute,
        )
        self.request_count = 0

    def get(self, path, params=None):
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        for attempt in range(self.config.max_retries + 1):
            self.limiter.wait()
            try:
                response = self.session.get(
                    url, params=params, timeout=self.config.timeout_seconds
                )
                self.request_count += 1
            except requests.RequestException as exc:
                if attempt >= self.config.max_retries:
                    raise TenraiError(f"Request failed: {url}: {exc}") from exc
                self._backoff(attempt)
                continue

            if response.status_code == 200:
                return response.json()

            if response.status_code == 429:
                value = response.headers.get("Retry-After")
                try:
                    delay = max(1.0, float(value)) if value else self._backoff_seconds(attempt)
                except ValueError:
                    delay = self._backoff_seconds(attempt)
                time.sleep(delay)
                continue

            if response.status_code == 403:
                if attempt >= self.config.max_retries:
                    raise TenraiError(f"HTTP 403 temporary block persisted: {url}")
                # Do not hammer a service that has explicitly blocked the request.
                time.sleep(max(30.0, self._backoff_seconds(attempt) * 3))
                continue

            if response.status_code in RETRYABLE:
                if attempt >= self.config.max_retries:
                    raise TenraiError(
                        f"HTTP {response.status_code}: {url}: {response.text[:500]}"
                    )
                self._backoff(attempt)
                continue

            if response.status_code == 404:
                raise TenraiError(f"HTTP 404: {url}")

            raise TenraiError(
                f"HTTP {response.status_code}: {url}: {response.text[:1000]}"
            )

        raise TenraiError(f"Request failed: {url}")

    @staticmethod
    def _backoff_seconds(attempt):
        return min(120.0, 2 ** (attempt + 1)) + random.uniform(0, 1)

    def _backoff(self, attempt):
        time.sleep(self._backoff_seconds(attempt))
