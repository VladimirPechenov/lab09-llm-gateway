import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Literal

import redis
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from pydantic import BaseModel, StringConstraints

from . import cache, llm, moderation, ratelimit, router
from .auth import require_api_key
from .settings import Settings

log = logging.getLogger("gateway")
logging.basicConfig(level=logging.INFO, format="%(message)s")


class ChatIn(BaseModel):
    npc: Literal["trader", "guard"]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ChatOut(BaseModel):
    reply: str
    model: str
    cached: bool
    latency_ms: float
    attempts: int
    degraded: bool
    moderated: bool


def create_app(settings: Settings | None = None, redis_client=None) -> FastAPI:
    config = settings or Settings()
    r = redis_client or redis.Redis.from_url(
        config.redis_url, decode_responses=True, socket_timeout=1, socket_connect_timeout=1)

    @asynccontextmanager
    async def lifespan(app):
        yield
        r.close()

    app = FastAPI(title="Game NPC LLM gateway", version="1.0.0", lifespan=lifespan)
    app.state.settings = config
    app.state.redis = r
    registry = CollectorRegistry()
    reqs = Counter("gateway_requests_total", "All chat responses", ["status"], registry=registry)
    lat = Histogram("gateway_latency_seconds", "Full chat latency including auth/errors", registry=registry)
    calls = Counter("gateway_provider_attempts_total", "Provider attempts", registry=registry)
    hits = Counter("gateway_cache_total", "Cache decisions", ["result"], registry=registry)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        started = time.perf_counter()
        request_id = uuid.uuid4().hex
        request.state.audit = {}
        response = await call_next(request)
        if request.url.path == "/v1/chat":
            elapsed = time.perf_counter() - started
            reqs.labels(str(response.status_code)).inc()
            lat.observe(elapsed)
            log.info(json.dumps({"request_id": request_id, "status": response.status_code,
                                 "latency_ms": round(elapsed * 1000, 3), **request.state.audit}))
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    @app.get("/health")
    def health(response: Response):
        try:
            r.ping()
            return {"status": "ok", "provider": config.provider, "cache_enabled": config.cache_enabled,
                    "redis": "ok", "cache": cache.stats(r, config)}
        except redis.RedisError:
            response.status_code = 503
            return {"status": "unavailable", "redis": "unavailable"}

    @app.post("/v1/chat", response_model=ChatOut)
    def chat(body: ChatIn, request: Request, client_id: str = Depends(require_api_key)):
        started = time.perf_counter()
        request.state.audit = {"client_id": client_id[:12], "npc": body.npc}
        try:
            ratelimit.check(r, config, client_id)
            if not moderation.check_input(body.message):
                raise HTTPException(400, "message rejected by moderation")
            model = router.choose_model(body.message, config)
            key = cache.key_for(config, body.npc, body.message, model)
            hit = cache.get(r, config, key)
            hits.labels("disabled" if not config.cache_enabled else "hit" if hit else "miss").inc()
            if hit:
                result = {**hit, "cached": True, "attempts": 0}
            else:
                generated = llm.call_with_fallback(config, model, body.npc, body.message)
                calls.inc(generated.attempts)
                reply, moderated = moderation.clean_output(generated.reply)
                value = {"reply": reply, "model": generated.model, "degraded": generated.degraded,
                         "moderated": moderated}
                if not generated.degraded and not moderated:
                    cache.put(r, config, key, value)
                result = {**value, "cached": False, "attempts": generated.attempts}
        except redis.RedisError as exc:
            raise HTTPException(503, "storage unavailable") from exc
        request.state.audit.update(model=result["model"], cached=result["cached"], attempts=result["attempts"],
                                   degraded=result["degraded"], moderated=result["moderated"])
        return ChatOut(**result, latency_ms=round((time.perf_counter() - started) * 1000, 3))

    return app


app = create_app()
