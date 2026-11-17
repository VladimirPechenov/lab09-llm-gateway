"""Record versions used for the measurements, without environment secrets."""

import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
packages = [
    "fastapi",
    "uvicorn",
    "redis",
    "openai",
    "anthropic",
    "pydantic",
    "locust",
    "httpx",
    "prometheus-client",
    "pytest",
    "ruff",
    "reportlab",
    "pillow",
    "matplotlib",
]
data = {
    "python": sys.version,
    "host": platform.platform(),
    "packages": {name: importlib.metadata.version(name) for name in packages},
}
for name, command in {
    "docker": ["docker", "version", "--format", "{{json .Server}}"],
    "images": [
        "docker",
        "image",
        "inspect",
        "redis:7-alpine",
        "lab09-llm-gateway-gateway:latest",
        "--format",
        "{{.Id}} {{json .RepoDigests}}",
    ],
    "compose": ["docker", "compose", "version", "--short"],
}.items():
    data[name] = subprocess.check_output(command, cwd=ROOT, text=True).strip()
(ROOT / "results/environment.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("Version snapshot saved")
