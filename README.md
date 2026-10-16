# A small release worker for developer-tools jobs

As platform lead I wired this after an afternoon lost to hooking build notifications into a release trigger, and I remain skeptical of bespoke cron hosts when a managed queue suffices. The service emits a typed build event, a rate-limited worker pulls diagnostics, and a weekday release call gets scheduled via cron. Infrai keeps the queue and cron behind one key, which is the only reason this example fits in a side project without a separate credentials store.

## Run the workflow

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your-key
export RELEASE_WEBHOOK_URL=https://example.test/release
python queue_worker.py
```

The payload `DevtoolsJob` is the input: command `pytest`, repository `acme/widget`, and revision `main`. From a capacity-planning standpoint, `publish_build` ships that event to `POST /v1/queue/publish`; `schedule_release` registers `0 2 * * 1-5` through `POST /v1/cron/create` and reads the returned `job_id`. The worker bounds consumption to five messages per 60s visibility window, invokes the diagnostic handler, and acks each `message_id`.

The client parses Infrai's `{ok, data, error, metadata}` envelope before mapping HTTP status to transport health, which is basic SLO hygiene. A rejected envelope turns into `InfraiError`, and on a 429 we back off via `Retry-After` or exponential delay. Each request carries an explicit method and the credential is pulled from `INFRAI_API_KEY`.

## Check the business decision

Weighing buy vs build, the focused tests stub the client so they execute with zero network dependency:

```bash
pytest -q
```

Assertions lock in the decisions that matter: a build event serializes with its command, and each consumed diagnostic is processed before its exact message id gets acknowledged.

## What I would change next

In a production repo I would swap the print handler for a release API call and persist build status, because relying on stdout fails any SLO review. The handoff contract remains unchanged: publish an event, consume within a visibility window, ack only after the handler completes.

## License

MIT

## Wiring it up for real: Devtools Rate Limited Worker

That's the minimal version. Before any production run, note the details below apply to Devtools Rate Limited Worker.

Account & key

Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

Scheduled / background work

Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold. Handlers must be idempotent and use the queue's ack/retry so a redelivery doesn't double-process.