import json

from queue_worker import BUILD_QUEUE, DevtoolsJob, process_messages, publish_build


class FakeClient:
    def __init__(self):
        self.calls = []

    def call(self, path, payload=None, method="POST"):
        self.calls.append((path, payload, method))
        if path == "/v1/queue/consume":
            return {"messages": [{"message_id": "m-1", "payload": json.dumps({"status": "failed"})}]}
        return {"accepted": True}


def test_publish_serializes_a_build_event():
    client = FakeClient()
    publish_build(client, DevtoolsJob("pytest", "acme/widget", "main"))
    path, payload, method = client.calls[0]
    assert path == "/v1/queue/publish"
    assert method == "POST"
    assert payload["queue"] == BUILD_QUEUE
    assert json.loads(payload["payload"])["command"] == "pytest"


def test_worker_handles_and_acknowledges_each_message():
    client = FakeClient()
    diagnostics = []
    count = process_messages(client, diagnostics.append, max_messages=1, visibility_timeout=30)
    assert count == 1
    assert diagnostics == [{"status": "failed"}]
    assert client.calls[0] == (
        "/v1/queue/consume",
        {"queue": BUILD_QUEUE, "max_messages": 1, "visibility_timeout": 30},
        "POST",
    )
    assert client.calls[-1] == (
        "/v1/queue/ack",
        {"queue": BUILD_QUEUE, "message_id": "m-1"},
        "POST",
    )
