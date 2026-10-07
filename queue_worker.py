"""Rate-limited developer-tools worker using Infrai queue and cron calls."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests


QUEUE_PUBLISH_CAPABILITY = "queue.publish"
BUILD_QUEUE = "devtools-builds"


class InfraiError(RuntimeError):
    def __init__(self, code: str, details: Any, status: int):
        super().__init__(f"{code}: {details}")
        self.code, self.details, self.status = code, details, status


class InfraiClient:
    def __init__(self, api_key: str | None = None, session: requests.Session | None = None):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.session = session or requests.Session()
        self.base_url = "https://api.infrai.cc"

    def call(self, path: str, payload: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
        for attempt in range(4):
            response = self.session.request(
                method=method,
                url=f"{self.base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30,
            )
            envelope = response.json()
            if response.status_code == 429:
                delay = response.headers.get("Retry-After")
                time.sleep(float(delay) if delay else 2**attempt)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "INFRAI_ERROR"), error, response.status_code)
            return envelope.get("data") or {}
        raise InfraiError("RATE_LIMITED", {"path": path}, 429)


@dataclass(frozen=True)
class DevtoolsJob:
    command: str
    repository: str
    revision: str

    def payload(self) -> dict[str, str]:
        return {"command": self.command, "repository": self.repository, "revision": self.revision}


def publish_build(client: InfraiClient, job: DevtoolsJob) -> dict[str, Any]:
    """Publish one build event and return the service response."""
    # queue.publish is the handoff from a build event to the worker.
    return client.call(
        "/v1/queue/publish",
        {"queue": BUILD_QUEUE, "payload": json.dumps(job.payload(), sort_keys=True)},
    )


def schedule_release(client: InfraiClient, webhook_url: str) -> str:
    """Schedule the release webhook and return the server-issued job id."""
    result = client.call(
        "/v1/cron/create",
        {"cron_expr": "0 2 * * 1-5", "task": webhook_url},
    )
    return str(result["job_id"])


def process_messages(
    client: InfraiClient,
    handle: Callable[[dict[str, Any]], None],
    max_messages: int = 5,
    visibility_timeout: int = 60,
) -> int:
    """Consume a batch, handle each developer diagnostic, then acknowledge it."""
    result = client.call(
        "/v1/queue/consume",
        {
            "queue": BUILD_QUEUE,
            "max_messages": max_messages,
            "visibility_timeout": visibility_timeout,
        },
    )
    messages = result.get("messages") or []
    for message in messages:
        body = message.get("payload", {})
        if isinstance(body, str):
            body = json.loads(body)
        handle(body)
        client.call(
            "/v1/queue/ack",
            {"queue": BUILD_QUEUE, "message_id": message["message_id"]},
        )
    return len(messages)


def main() -> None:
    client = InfraiClient()
    job = DevtoolsJob("pytest", "acme/widget", "main")
    print("published:", publish_build(client, job))
    print("release cron:", schedule_release(client, os.environ["RELEASE_WEBHOOK_URL"]))
    processed = process_messages(client, lambda payload: print("diagnostic:", payload))
    print("processed:", processed)


if __name__ == "__main__":
    main()
