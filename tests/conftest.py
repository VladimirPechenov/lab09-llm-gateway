import os
import uuid

import pytest
import redis
from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.settings import Settings


@pytest.fixture
def settings():
    return Settings(
        redis_url=os.getenv("TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        prefix="test09:" + uuid.uuid4().hex + ":",
        mock_delay=0,
        retry_delay=0,
        api_keys=("test-key", "other-key"),
        provider="mock",
        rate_limit=10000,
    )


@pytest.fixture
def r(settings):
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    client.ping()  # Real Redis required: no skipped integration tests.
    yield client
    keys = list(client.scan_iter(settings.prefix + "*"))
    if keys:
        client.delete(*keys)
    client.close()


@pytest.fixture
def client(settings, r):
    with TestClient(create_app(settings, r)) as c:
        yield c


@pytest.fixture
def headers():
    return {"X-API-Key": "test-key"}
