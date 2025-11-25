import asyncio
import time
from collections import defaultdict
from typing import Dict

class RateLimiter:
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed in the time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, list] = defaultdict(list)
        
    async def acquire(self, key: str = "default"):
        """
        Acquire permission to make a request.
        
        Args:
            key: Identifier for the rate limit bucket (e.g., IP address, parser name)
        """
        now = time.time()
        
        # Clean up old requests outside the time window
        self.requests[key] = [
            req_time for req_time in self.requests[key] 
            if now - req_time < self.time_window
        ]
        
        # Check if we're within the rate limit
        if len(self.requests[key]) >= self.max_requests:
            # Calculate sleep time until the oldest request expires
            oldest_request = min(self.requests[key])
            sleep_time = self.time_window - (now - oldest_request)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                # Clean up again after sleeping
                self.requests[key] = [
                    req_time for req_time in self.requests[key] 
                    if now - req_time < self.time_window
                ]
        
        # Record this request
        self.requests[key].append(now)
        
    def reset(self, key: str = "default"):
        """Reset the rate limit for a specific key."""
        if key in self.requests:
            del self.requests[key]

# Global rate limiter instance
rate_limiter = RateLimiter(max_requests=5, time_window=60)  # 5 requests per minute