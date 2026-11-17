"""Atomic token bucket shared by all workers. Clock comes from Redis."""
import math
from fastapi import HTTPException

SCRIPT = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
local capacity = tonumber(ARGV[1])
local rate = capacity / 60
local values = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(values[1]) or capacity
local ts = tonumber(values[2]) or now
tokens = math.min(capacity, tokens + math.max(0, now - ts) * rate)
local allowed = 0
local delay = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
else
  delay = math.ceil((1 - tokens) / rate * 1000)
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', KEYS[1], 120)
return {allowed, delay}
"""


def check(r, settings, client_id: str) -> None:
    allowed, delay = r.eval(SCRIPT, 1, settings.prefix + "rl:" + client_id, settings.rate_limit)
    if not allowed:
        raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": str(max(1, math.ceil(delay / 1000)))})
