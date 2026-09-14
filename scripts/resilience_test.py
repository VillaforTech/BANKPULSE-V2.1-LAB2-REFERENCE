"""Destructive only to availability of this named reference stack; volumes/history retained."""

import json, os, subprocess, time, uuid, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal

BASE = os.getenv("BANKPULSE_URL", "http://localhost:18080")
RUN = "resilience-" + str(uuid.uuid4())
OUT = Path(os.getenv("EVIDENCE_DIR", "artifacts/resilience"))
OUT.mkdir(parents=True, exist_ok=True)
checks = []
evidence = {}


def call(route, body=None):
    req = urllib.request.Request(
        BASE + route,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def compose(*args, input=None):
    return subprocess.run(
        ["docker", "compose", *args],
        input=input,
        text=True,
        capture_output=True,
        check=True,
    ).stdout


def eventually(fn, seconds=30):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            last = fn()
            if last:
                return last
        except Exception as e:
            last = repr(e)
        time.sleep(0.2)
    raise AssertionError("condition timed out: " + str(last))


def fresh():
    s = call("/api/business/snapshot")
    return s if s["quality"]["status"] == "FRESH" else None


def check(value, label):
    checks.append({"name": label, "passed": bool(value)})
    if not value:
        raise AssertionError(label)


try:
    s = call(
        "/api/splits",
        {
            "hostMemberId": "DEMO",
            "totalAmount": 100,
            "currency": "USD",
            "fixtureRunId": RUN,
        },
    )
    s = call(
        "/api/splits/" + s["id"] + "/participants",
        {"memberId": "DEMO-1", "shareAmount": 60},
    )
    s = call(
        "/api/splits/"
        + s["id"]
        + "/participants/"
        + s["participants"][0]["id"]
        + "/authorize",
        {"paymentReference": "DEMO-REF"},
    )
    evidence["timerSession"] = s
    initial = eventually(fresh)
    evidence["initial"] = initial
    # Broker outage must not prevent committing a domain change and its outbox.
    compose("stop", "redpanda")
    during = call(
        "/api/splits",
        {
            "hostMemberId": "OUTAGE-DEMO",
            "totalAmount": 10,
            "currency": "USD",
            "fixtureRunId": RUN + "-outage",
        },
    )
    pending = call("/api/splits/outbox-status")
    check(pending["pending"] >= 1, "commit survives broker outage in outbox")
    evidence["outage"] = {"session": during, "outbox": pending}
    eventually(
        lambda: call("/api/business/snapshot")["quality"]["status"] != "FRESH", 10
    )
    compose("up", "-d", "--wait", "--wait-timeout", "60", "redpanda")
    recovered = eventually(fresh, 45)
    check(
        recovered["coverage"]["aggregateCount"]
        == initial["coverage"]["aggregateCount"] + 1,
        "broker recovery loses no aggregate",
    )
    evidence["brokerRecovered"] = recovered
    before = recovered["coverage"]["eventCount"]
    compose("restart", "business-analytics")
    restarted = eventually(fresh, 40)
    check(
        restarted["coverage"]["eventCount"] == before,
        "consumer restart retains projection/checkpoints without double count",
    )
    # Replay a real source event. It must not add an event or replace the newer projection.
    sql = (
        "SELECT payload FROM social_split.split_outbox WHERE aggregate_id='"
        + s["id"]
        + "' ORDER BY sequence LIMIT 1;"
    )
    payload = compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "bankpulse_admin",
        "-d",
        "bankpulse_domains",
        "-Atc",
        sql,
    ).strip()
    event = json.loads(payload)
    compose(
        "exec",
        "-T",
        "redpanda",
        "rpk",
        "topic",
        "produce",
        "bankpulse.social-split.events.v1",
        "-k",
        s["id"],
        input=payload + "\n",
    )
    old_offsets = restarted["watermark"]["partitionOffsets"]

    def replay_consumed():
        current = fresh()
        return (
            current
            if current
            and sum(current["watermark"]["partitionOffsets"].values())
            > sum(old_offsets.values())
            else None
        )

    replayed = eventually(replay_consumed)
    check(
        replayed["coverage"]["eventCount"] == before,
        "duplicate old source event adds no logical event",
    )
    evidence["replay"] = {"eventId": event["eventId"], "coverage": replayed["coverage"]}
    source_sessions = call("/api/splits/snapshot")["sessions"]
    # No business operations after this point: the 120 second transition must be timer driven.
    deadline = (
        datetime.fromisoformat(s["createdAt"].replace("Z", "+00:00")).timestamp() + 120
    )
    remaining = max(0, deadline - time.time() + 0.05)
    if remaining:
        time.sleep(remaining)
    first_seen = None

    def expired():
        global first_seen
        # History reads an already persisted timer snapshot; unlike /snapshot it does
        # not recalculate on demand, so a broken timer cannot pass this assertion.
        for data in call("/api/business/history"):
            computed = datetime.fromisoformat(data["computedAt"]).timestamp()
            if computed <= deadline:
                continue
            expected = sum(
                (
                    Decimal(str(p["shareAmount"]))
                    for item in source_sessions
                    if item["status"] == "OPEN"
                    and item["currency"] == "USD"
                    and datetime.fromisoformat(
                        item["createdAt"].replace("Z", "+00:00")
                    ).timestamp()
                    < computed - 120
                    for p in item["participants"]
                    if p["authorized"]
                ),
                Decimal(0),
            )
            actual = Decimal(data["kpis"]["USD"]["B-K3"]["value"])
            if (
                actual == expected
                and actual >= 60
                and data["quality"]["status"] == "FRESH"
            ):
                first_seen = time.time()
                return data
        return None

    timer = eventually(expired, 5)
    evidence["timer"] = {
        "persistedSnapshot": timer,
        "deadline": deadline,
        "observedAt": first_seen,
        "delaySeconds": first_seen - deadline,
    }
    check(
        first_seen - deadline <= 1,
        "120 second threshold persists within one second without new traffic",
    )
    fixture = call("/api/business/snapshot?fixtureRunId=" + RUN)
    check(
        fixture["kpis"]["USD"]["B-K3"]["value"] == "60.00",
        "expired fixture contributes exactly 60 authorized USD",
    )
    check(
        fixture["kpis"]["USD"]["B-K1"]["value"] is None,
        "no closed sessions is NO_SAMPLE",
    )
    check(
        eventually(fresh)["coverage"]["eventCount"] == before,
        "timers do not manufacture domain events",
    )
except Exception as e:
    checks.append({"name": "resilience execution", "passed": False, "error": repr(e)})
finally:
    # Restore availability even after an assertion fails, retaining all source/analytics data.
    subprocess.run(
        ["docker", "compose", "up", "-d", "redpanda", "business-analytics"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    result = {
        "fixtureRunId": RUN,
        "checks": checks,
        "evidence": evidence,
        "passed": bool(checks) and all(c["passed"] for c in checks),
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "checks": checks,
                "artifact": str(OUT / "result.json"),
            },
            indent=2,
        )
    )
    raise SystemExit(0 if result["passed"] else 1)
