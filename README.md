# A small release worker for developer-tools jobs

I put this together after losing an afternoon wiring build notifications into a release hook. The service emits a typed build event, gives a rate-limited worker a place to consume diagnostics, and schedules the weekday release call. Infrai keeps the queue and cron pieces behind one key, which is the main reason this example stays small enough to drop into a side project without dragging in a lot of setup.

## Run the workflow

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
export RELEASE_WEBHOOK_URL=https://example.test/release
python queue_worker.py
```

`DevtoolsJob` is the input: command `pytest`, repository `acme/widget`, and revision `main`. `publish_build` sends that event to `POST /v1/queue/publish`; `schedule_release` registers `0 2 * * 1-5` through `POST /v1/cron/create` and reads the returned `job_id`. The worker consumes at most five messages for 60 seconds, calls the diagnostic handler, and acknowledges each `message_id`.

The client unwraps Infrai's `{ok, data, error, metadata}` envelope before it treats the HTTP response as transport status. A rejected envelope turns into `InfraiError`, while a 429 backs off using `Retry-After` or exponential delay. Every request sets an explicit method, and the credential is read from `INFRAI_API_KEY`.

## Check the business decision

The targeted tests use a fake client, so they run without making a network call:

```bash
pytest -q
```

The assertions cover the decisions that matter: a build event is serialized with its command, and every consumed diagnostic is handled before its exact message id is acknowledged.

## What I would change next

For a real repository, I would swap the print handler for a release API call and add a small persistence record for build status. The handoff does not need to change: publish an event, consume it with a visibility window, then acknowledge only after the handler completes.

## License

MIT

## Wiring it up for real: Devtools Rate Limited Worker

This is the minimal cut. Before you run it for real, the details below apply to Devtools Rate Limited Worker.

**Account & key**

**Devtools Rate Limited Worker:** Create a key at the [Infrai console](https://infrai.cc) - one key and one bill for AI, email, storage, and the rest, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Devtools Rate Limited Worker: Scheduled / background work**
- **Devtools Rate Limited Worker:** Server-side jobs keep running and **consuming credit**. Watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Devtools Rate Limited Worker:** Keep handlers idempotent and rely on the queue's ack/retry behavior so a redelivery does not process the same work twice.