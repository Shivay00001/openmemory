import time
from fastapi import HTTPException
try:
    import redis
    redis_available = True
    # In production, use connection pool and environment variables
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
except ImportError:
    redis_available = False

# Fallback in-memory store for environments without Redis running (e.g. testing)
_mock_redis_store = {}

class RateLimiter:
    """
    Token Bucket Rate Limiter using Redis.
    Protects the API from malicious agents spamming the endpoints.
    """
    def __init__(self, requests_per_minute: int = 60):
        self.limit = requests_per_minute
        self.window = 60 # seconds

    def check_rate_limit(self, tenant_id: str):
        """Raises HTTP 429 if limit exceeded."""
        key = f"rate_limit:{tenant_id}:{int(time.time() // self.window)}"
        
        if redis_available:
            try:
                current = redis_client.incr(key)
                if current == 1:
                    redis_client.expire(key, self.window)
                    
                if current > self.limit:
                    raise HTTPException(status_code=429, detail="Too Many Requests. Rate limit exceeded.")
                return
            except redis.ConnectionError:
                pass # Fallback to in-memory if Redis server is down
                
        # In-memory fallback
        current = _mock_redis_store.get(key, 0) + 1
        _mock_redis_store[key] = current
        
        # Simple cleanup (prevent memory leak in mock)
        if len(_mock_redis_store) > 1000:
            _mock_redis_store.clear()
            
        if current > self.limit:
            raise HTTPException(status_code=429, detail="Too Many Requests. Rate limit exceeded.")
