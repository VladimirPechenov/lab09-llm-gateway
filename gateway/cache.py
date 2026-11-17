import hashlib
import json

PROMPT_VERSION = "npc-v1"


def key_for(settings, npc: str, message: str, model: str) -> str:
    # Preserve case and separators to avoid semantic collisions.
    payload = [PROMPT_VERSION, settings.provider, npc, message, model, settings.fallback_model]
    return settings.prefix + "cache:" + hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def get(r, settings, key: str):
    if not settings.cache_enabled:
        return None
    value = r.get(key)
    r.hincrby(settings.prefix + "stats", "hit" if value else "miss", 1)
    return json.loads(value) if value else None


def put(r, settings, key: str, value: dict) -> None:
    if settings.cache_enabled:
        r.setex(key, settings.cache_ttl, json.dumps(value, ensure_ascii=False))


def stats(r, settings):
    counts = r.hgetall(settings.prefix + "stats")
    hit, miss = int(counts.get("hit", 0)), int(counts.get("miss", 0))
    return {"hit": hit, "miss": miss, "hit_percent": round(100 * hit / (hit + miss), 2) if hit + miss else 0}
