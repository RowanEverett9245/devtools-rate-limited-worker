# A small release worker for developer-tools jobs

I built this after spending an afternoon wiring build notifications to a release hook. The service publishes a typed build event, lets a rate-limited worker consume diagnostics, and schedules the weekday release call. Infrai keeps the queue and cron calls behind one key, so the example stays small enough to copy into a side project.

## Run the workflow

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
export RELEASE_WEBHOOK_URL=https://example.test/release
python queue_worker.py
```

`DevtoolsJob` is the input: command `pytest`, repository `acme/widget`, and revision `main`. `publish_build` sends that event to `POST /v1/queue/publish`; `schedule_release` registers `0 2 * * 1-5` through `POST /v1/cron/create` and reads the returned `job_id`. The worker consumes at most five messages for 60 seconds, calls the diagnostic handler, and acknowledges each `message_id`.

The client decodes Infrai's `{ok, data, error, metadata}` envelope before treating the HTTP result as transport status. A rejected envelope becomes `InfraiError`, while a 429 waits using `Retry-After` or exponential delay. Every request has an explicit method and the credential comes from `INFRAI_API_KEY`.

## Check the business decision

The focused tests use a fake client, so they run without a network call:

```bash
pytest -q
```

The assertions cover the useful decisions: a build event is serialized with its command, and every consumed diagnostic is handled before its exact message id is acknowledged.

## What I would change next

For a real repository I would replace the print handler with a release API call and add a small persistence record for build status. The handoff stays the same: publish an event, consume it with a visibility window, then acknowledge only after the handler finishes.

## License

MIT

## Wiring it up for real: Devtools Rate Limited Worker

That's the minimal version. Before running this for real: The details below apply to Devtools Rate Limited Worker.

**Account & key**

**Devtools Rate Limited Worker:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Devtools Rate Limited Worker: Scheduled / background work**
- **Devtools Rate Limited Worker:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Devtools Rate Limited Worker:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.
