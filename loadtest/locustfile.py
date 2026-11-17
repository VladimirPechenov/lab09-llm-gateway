"""50 players, deterministic 3/10 common messages, 7/10 unique."""

import json
import os
import uuid
from pathlib import Path

from locust import HttpUser, between, events, task

COUNTS = {"responses": 0, "hits": 0, "errors": 0, "common_sent": 0, "unique_sent": 0}


class GameClient(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self):
        self.serial = 0
        self.player = uuid.uuid4().hex

    @task
    def chat(self):
        self.serial += 1
        common = self.serial % 10 < 3
        COUNTS["common_sent" if common else "unique_sent"] += 1
        message = "Привет" if common else f"Что продаёшь игроку {self.player}, диалог {self.serial}?"
        with self.client.post(
            "/v1/chat",
            name="/v1/chat",
            json={"npc": "trader", "message": message},
            headers={"X-API-Key": os.getenv("LOAD_API_KEY", "dev-key")},
            catch_response=True,
        ) as response:
            COUNTS["responses"] += 1
            if response.status_code == 200:
                try:
                    COUNTS["hits"] += int(response.json()["cached"])
                except (ValueError, KeyError):
                    COUNTS["errors"] += 1
                    response.failure("invalid response")
            else:
                COUNTS["errors"] += 1


@events.quitting.add_listener
def save_counts(environment, **kwargs):
    target = os.getenv("LOAD_COUNTS_FILE")
    if target:
        Path(target).write_text(json.dumps(COUNTS, indent=2), encoding="utf-8")
    if COUNTS["errors"]:
        environment.process_exit_code = 1
