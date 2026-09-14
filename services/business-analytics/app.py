import os, json, time, threading, uuid, logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import psycopg, requests
from psycopg.types.json import Jsonb
from confluent_kafka import Consumer, TopicPartition
from fastapi import FastAPI, Response
from domain import calculate, validate

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("analytics")
DSN = os.environ["ANALYTICS_DSN"]
TOPIC = "bankpulse.social-split.events.v1"
state = {
    "brokerOk": False,
    "lag": None,
    "lastPoll": 0,
    "lastEvent": None,
    "sourceEventId": None,
    "sourcePending": None,
    "sourceCount": None,
    "sourceVersions": None,
    "invalid": 0,
    "liveOk": False,
    "liveError": None,
}
publish_lock = threading.RLock()
lock = threading.RLock()
stop = threading.Event()
http = requests.Session()


def connection():
    return psycopg.connect(DSN)


def initialize():
    with connection() as c:
        c.execute("CREATE SEQUENCE IF NOT EXISTS snapshot_revision")
        c.execute(
            "CREATE TABLE IF NOT EXISTS received_events(event_id text PRIMARY KEY, aggregate_id text NOT NULL, version bigint NOT NULL, payload jsonb NOT NULL, received_at timestamptz NOT NULL DEFAULT now(), UNIQUE(aggregate_id,version))"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS split_projection(aggregate_id text PRIMARY KEY,version bigint NOT NULL,payload jsonb NOT NULL)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS checkpoints(partition_id integer PRIMARY KEY,offset_value bigint NOT NULL)"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS rejected_events(partition_id integer,offset_value bigint,error text NOT NULL,PRIMARY KEY(partition_id,offset_value))"
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS snapshots(id bigserial PRIMARY KEY,computed_at timestamptz NOT NULL,payload jsonb NOT NULL)"
        )


def apply(event, partition, offset):
    validate(event)
    with connection() as c:
        existing = c.execute(
            "SELECT payload FROM received_events WHERE event_id=%s OR (aggregate_id=%s AND version=%s)",
            (event["eventId"], event["aggregateId"], event["aggregateVersion"]),
        ).fetchone()
        if existing and existing[0] != event:
            raise ValueError("conflicting event identity or version")
        inserted = c.execute(
            "INSERT INTO received_events(event_id,aggregate_id,version,payload) VALUES(%s,%s,%s,%s) ON CONFLICT(event_id) DO NOTHING RETURNING event_id",
            (
                event["eventId"],
                event["aggregateId"],
                event["aggregateVersion"],
                Jsonb(event),
            ),
        ).fetchone()
        if inserted:
            c.execute(
                "INSERT INTO split_projection VALUES(%s,%s,%s) ON CONFLICT(aggregate_id) DO UPDATE SET version=EXCLUDED.version,payload=EXCLUDED.payload WHERE split_projection.version<EXCLUDED.version",
                (event["aggregateId"], event["aggregateVersion"], Jsonb(event["data"])),
            )
        c.execute(
            "INSERT INTO checkpoints VALUES(%s,%s) ON CONFLICT(partition_id) DO UPDATE SET offset_value=GREATEST(checkpoints.offset_value,EXCLUDED.offset_value)",
            (partition, offset + 1),
        )
    return bool(inserted)


def reject(partition, offset, error):
    with connection() as c:
        c.execute(
            "INSERT INTO rejected_events VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
            (partition, offset, type(error).__name__ + ": " + str(error)[:200]),
        )
        c.execute(
            "INSERT INTO checkpoints VALUES(%s,%s) ON CONFLICT(partition_id) DO UPDATE SET offset_value=GREATEST(checkpoints.offset_value,EXCLUDED.offset_value)",
            (partition, offset + 1),
        )


def effective_offset(position, checkpoint, low, high):
    # librdkafka can report OFFSET_INVALID at an empty tail after reassignment.
    # The transactionally persisted next offset remains authoritative then.
    current = checkpoint if position < 0 else position
    if checkpoint < low or current < low:
        raise ValueError("broker retention gap")
    if checkpoint > high or current > high:
        raise ValueError("broker history truncated behind durable checkpoint")
    return current


def snapshot(fixture=None, persist=False):
    now = datetime.now(timezone.utc)
    with connection() as c:
        c.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        revision = c.execute("SELECT nextval('snapshot_revision')").fetchone()[0]
        sessions = [row[0] for row in c.execute("SELECT payload FROM split_projection")]
        version_sum = sum(s["aggregateVersion"] for s in sessions)
        latest = c.execute(
            "SELECT payload FROM received_events ORDER BY (payload->>'occurredAt')::timestamptz DESC,received_at DESC LIMIT 1"
        ).fetchone()
        count = c.execute("SELECT count(*) FROM received_events").fetchone()[0]
        gaps = c.execute(
            "SELECT count(*) FROM (SELECT aggregate_id,max(version) AS maxv,count(*) AS n FROM received_events GROUP BY aggregate_id HAVING count(*)<>max(version)) t"
        ).fetchone()[0]
        bad = c.execute("SELECT count(*) FROM rejected_events").fetchone()[0]
        offsets = {
            str(r[0]): r[1]
            for r in c.execute("SELECT partition_id,offset_value FROM checkpoints")
        }
    with lock:
        health = dict(state)
    complete = (
        not gaps
        and not bad
        and health["lag"] == 0
        and health["sourcePending"] == 0
        and health["sourceCount"] == len(sessions)
        and health["sourceVersions"] == version_sum
    )
    fresh = health["brokerOk"] and time.time() - health["lastPoll"] < 5
    quality = "INCOMPLETE" if not complete else ("FRESH" if fresh else "STALE")
    data = {
        "schemaVersion": 1,
        "snapshotId": str(revision),
        "revision": revision,
        "computedAt": now.isoformat(),
        "sourceEventId": latest[0]["eventId"] if latest else None,
        "watermark": {
            "occurredAt": latest[0]["occurredAt"] if latest else None,
            "partitionOffsets": offsets,
        },
        "quality": {
            "status": quality,
            "reason": {
                "gaps": gaps,
                "rejected": bad,
                "lag": health["lag"],
                "outboxPending": health["sourcePending"],
                "brokerOk": health["brokerOk"],
            },
        },
        "coverage": {
            "complete": complete,
            "aggregateCount": len(sessions),
            "eventCount": count,
        },
        "fixtureRunId": fixture,
        "kpis": calculate(sessions, now, fixture),
        "stream": {"connected": health["liveOk"], "error": health["liveError"]},
    }
    if persist:
        with connection() as c:
            c.execute(
                "INSERT INTO snapshots(computed_at,payload) VALUES(%s,%s)",
                (now, Jsonb(data)),
            )
            c.execute(
                "DELETE FROM snapshots WHERE id<(SELECT COALESCE(max(id),0)-10000 FROM snapshots)"
            )
    return data


def publish_live(data):
    lines = []
    currencies = data["kpis"] or {"USD": {}}
    for currency, kpis in currencies.items():
        fields = {
            "event_count": data["coverage"]["eventCount"],
            "aggregate_count": data["coverage"]["aggregateCount"],
            "complete": int(data["coverage"]["complete"]),
            "fresh": int(data["quality"]["status"] == "FRESH"),
            "source_event_id": data["sourceEventId"] or "bootstrap",
            "revision": data["revision"],
            "snapshot_id": data["snapshotId"],
            "computed_at": data["computedAt"],
        }
        fields.update(
            {
                "integrity_percent": (
                    kpis.get("B-K1", {}).get("value")
                    if kpis.get("B-K1", {}).get("value") is not None
                    else -1
                ),
                "closure_gap": kpis.get("B-K2", {}).get("value"),
                "unresolved_amount": kpis.get("B-K3", {}).get("value"),
                "closure_count": kpis.get("B-K1", {}).get("denominator", 0),
                "has_sample": int(kpis.get("B-K1", {}).get("value") is not None),
            }
        )
        encoded = []
        for k, v in fields.items():
            if v is None:
                continue
            encoded.append(
                k
                + "="
                + (
                    json.dumps(v)
                    if k.endswith("_id") or k == "computed_at"
                    else str(float(v))
                )
            )
        lines.append(
            "business,currency="
            + currency
            + " "
            + ",".join(encoded)
            + " "
            + str(time.time_ns())
        )
    try:
        r = http.post(
            os.getenv("GRAFANA_URL", "http://grafana:3000")
            + "/api/live/push/bankpulse",
            data="\n".join(lines),
            auth=(os.getenv("GRAFANA_USER", "admin"), os.environ["GRAFANA_PASSWORD"]),
            timeout=2,
        )
        r.raise_for_status()
        with lock:
            state.update(liveOk=True, liveError=None)
    except Exception as e:
        with lock:
            state.update(liveOk=False, liveError=type(e).__name__)


def consume():
    consumer = Consumer(
        {
            "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "redpanda:9092"),
            "group.id": "bankpulse-business-analytics-v1",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "enable.partition.eof": True,
        }
    )

    def assigned(c, partitions):
        with connection() as db:
            checkpoints = dict(
                db.execute(
                    "SELECT partition_id,offset_value FROM checkpoints"
                ).fetchall()
            )
        for p in partitions:
            p.offset = checkpoints.get(p.partition, 0)
        c.assign(partitions)

    consumer.subscribe([TOPIC], on_assign=assigned)
    next_health = 0
    try:
        while not stop.is_set():
            try:
                msg = consumer.poll(0.1)
                if msg and not msg.error():
                    try:
                        event = json.loads(msg.value())
                        inserted = apply(event, msg.partition(), msg.offset())
                    except (ValueError, KeyError, TypeError, OverflowError) as e:
                        reject(msg.partition(), msg.offset(), e)
                        consumer.commit(message=msg, asynchronous=False)
                        continue
                    consumer.commit(message=msg, asynchronous=False)
                    if inserted:
                        with publish_lock:
                            publish_live(snapshot(persist=True))
                if time.time() > next_health:
                    next_health = time.time() + 0.5
                    assignments = consumer.assignment()
                    lag = 0
                    with connection() as db:
                        durable_offsets = dict(
                            db.execute(
                                "SELECT partition_id,offset_value FROM checkpoints"
                            ).fetchall()
                        )
                    for position in consumer.position(assignments):
                        low, high = consumer.get_watermark_offsets(position, timeout=2)
                        current = effective_offset(
                            position.offset,
                            durable_offsets.get(position.partition, 0),
                            low,
                            high,
                        )
                        lag += high - current
                    source = http.get(
                        os.getenv("SOURCE_URL", "http://social-split-api:8086")
                        + "/api/splits/outbox-status",
                        timeout=2,
                    ).json()
                    with lock:
                        state.update(
                            brokerOk=bool(assignments),
                            lag=lag if assignments else None,
                            lastPoll=time.time(),
                            sourcePending=source["pending"],
                            sourceCount=source["aggregateCount"],
                            sourceVersions=source["versionSum"],
                        )
                    next_health = time.time() + 0.5
            except Exception as e:
                with lock:
                    state.update(brokerOk=False)
                log.warning(
                    "consumer unavailable: %s: %s", type(e).__name__, str(e)[:160]
                )
                stop.wait(0.5)
    finally:
        consumer.close()


def timer():
    while not stop.wait(0.25):
        try:
            with publish_lock:
                publish_live(snapshot(persist=True))
        except Exception as e:
            log.warning("snapshot unavailable: %s", type(e).__name__)


@asynccontextmanager
async def lifespan(app):
    initialize()
    workers = [threading.Thread(target=f, daemon=True) for f in (consume, timer)]
    for w in workers:
        w.start()
    yield
    stop.set()
    for w in workers:
        w.join(5)


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    with connection() as c:
        c.execute("SELECT 1")
    return {"status": "UP"}


@app.get("/api/business/snapshot")
def get_snapshot(fixtureRunId: str | None = None):
    return snapshot(fixtureRunId)


@app.get("/api/business/history")
def history():
    with connection() as c:
        return [
            r[0]
            for r in c.execute(
                "SELECT payload FROM snapshots ORDER BY id DESC LIMIT 100"
            )
        ]


@app.get("/metrics")
def metrics():
    s = snapshot()
    lines = ["bankpulse_analytics_complete " + str(int(s["coverage"]["complete"]))]
    for currency, k in s["kpis"].items():
        for key, name in [
            ("B-K1", "integrity_percent"),
            ("B-K2", "closure_gap"),
            ("B-K3", "unresolved_amount"),
        ]:
            if k[key]["value"] is not None:
                lines.append(
                    f'bankpulse_{name}{{currency="{currency}"}} {k[key]["value"]}'
                )
    return Response("\n".join(lines) + "\n", media_type="text/plain")
