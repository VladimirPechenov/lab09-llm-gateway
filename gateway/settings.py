"""Configuration injectable into app/tests; offline mock is the default."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    api_keys: tuple = field(
        default_factory=lambda: tuple(k.strip() for k in os.getenv("API_KEYS", "dev-key").split(",") if k.strip())
    )
    rate_limit: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MIN", "30")))
    cache_ttl: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL_S", "3600")))
    cache_enabled: bool = field(default_factory=lambda: os.getenv("CACHE_ENABLED", "true").lower() == "true")
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))
    cheap_model: str = field(default_factory=lambda: os.getenv("CHEAP_MODEL", "gpt-4o-mini"))
    strong_model: str = field(default_factory=lambda: os.getenv("STRONG_MODEL", "gpt-4o"))
    fallback_model: str = field(default_factory=lambda: os.getenv("FALLBACK_MODEL", "gpt-4o-mini"))
    timeout: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_S", "5")))
    attempts: int = field(default_factory=lambda: int(os.getenv("LLM_ATTEMPTS", "3")))
    retry_delay: float = field(default_factory=lambda: float(os.getenv("RETRY_DELAY_S", "0.1")))
    mock_delay: float = field(default_factory=lambda: float(os.getenv("MOCK_DELAY_S", "0.15")))
    prefix: str = "lab09:"

    def __post_init__(self):
        if self.provider not in {"mock", "openai", "anthropic"}:
            raise ValueError("Unknown LLM_PROVIDER")
        if not self.api_keys or min(self.rate_limit, self.cache_ttl, self.attempts) < 1:
            raise ValueError("Nonempty API_KEYS and positive rate limit / TTL / attempts required")
        if self.timeout <= 0 or self.retry_delay < 0 or self.mock_delay < 0:
            raise ValueError("Invalid timeout or delay")
