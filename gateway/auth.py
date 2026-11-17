import hashlib
import secrets
from fastapi import Header, HTTPException, Request


def fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def require_api_key(request: Request, x_api_key: str = Header(default="")) -> str:
    if not any(secrets.compare_digest(x_api_key.encode(), k.encode()) for k in request.app.state.settings.api_keys):
        raise HTTPException(401, "invalid API key")
    return fingerprint(x_api_key)
