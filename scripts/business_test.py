"""Independent API oracle; mutation changes the service, never these assertions."""

import json, os, time, uuid, urllib.request, urllib.error
from pathlib import Path
from decimal import Decimal

BASE = os.getenv("BANKPULSE_URL", "http://localhost:18080")
RUN = "business-" + str(uuid.uuid4())
OUT = Path(os.getenv("EVIDENCE_DIR", "artifacts/business"))
OUT.mkdir(parents=True, exist_ok=True)
checks = []
observations = {}


def check(condition, label):
    checks.append({"name": label, "passed": bool(condition)})


def call(path, body=None, method=None, headers=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method or ("POST" if body is not None else "GET"),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            data = json.loads(raw)
        except ValueError:
            data = {"raw": raw}
        return e.code, data


def create(name, shares, authorize=True):
    code, s = call(
        "/api/splits",
        {
            "hostMemberId": "HOST-DEMO",
            "totalAmount": 100,
            "currency": "USD",
            "fixtureRunId": RUN + "-" + name,
        },
    )
    assert code == 201, (code, s)
    for i, amount in enumerate(shares):
        code, s = call(
            "/api/splits/" + s["id"] + "/participants",
            {"memberId": "MEMBER-" + str(i), "shareAmount": amount},
        )
        assert code == 200, (code, s)
    if authorize:
        for participant in s["participants"]:
            code, s = call(
                "/api/splits/"
                + s["id"]
                + "/participants/"
                + participant["id"]
                + "/authorize",
                {"paymentReference": "DEMO-" + participant["id"]},
            )
            assert code == 200, (code, s)
    return s


def observe(name, s):
    code, closed = call("/api/splits/" + s["id"] + "/close", method="POST")
    _, persisted = call("/api/splits/" + s["id"])
    observations[name] = {"http": code, "close": closed, "persisted": persisted}
    return code, persisted


try:
    for service in [
        "payments",
        "audit",
        "experiences",
        "travel",
        "events",
        "social-split",
    ]:
        status, data = call("/health/" + service)
        check(status == 200 and data.get("status") == "UP", "health " + service)
    healthy = create("healthy", [60, 40])
    code, closed = observe("healthy", healthy)
    check(code == 200 and closed["status"] == "COMPLETED", "100=60+40 completes")
    check(
        Decimal(str(closed["totalAmount"])) == Decimal("100")
        and sum(Decimal(str(x["shareAmount"])) for x in closed["participants"]) == 100,
        "amount and shares preserved",
    )
    code, repeated = call("/api/splits/" + closed["id"] + "/close", method="POST")
    check(
        code == 200
        and repeated["closedAt"] == closed["closedAt"]
        and repeated["aggregateVersion"] == closed["aggregateVersion"],
        "close retry has no new effect",
    )
    code, _ = call(
        "/api/splits/" + closed["id"] + "/participants",
        {"memberId": "late", "shareAmount": 1},
    )
    _, same = call("/api/splits/" + closed["id"])
    check(code == 409 and same == closed, "completed aggregate immutable")
    for name, shares, consent in [
        ("under", [60, 30], True),
        ("over", [60, 50], True),
        ("consent", [100], False),
        ("empty", [], False),
    ]:
        s = create(name, shares, consent)
        code, persisted = observe(name, s)
        check(
            code == 409
            and persisted["status"] == "OPEN"
            and persisted["closedAt"] is None,
            name + " rejected without partial close",
        )
    code, _ = call(
        "/api/splits/"
        + observations["consent"]["persisted"]["id"]
        + "/participants/"
        + observations["consent"]["persisted"]["participants"][0]["id"]
        + "/authorize",
        {"paymentReference": " "},
    )
    check(code == 400, "empty reference rejected")
    for invalid in [0, -1, None, 1.001, 100000000000000000]:
        code, _ = call(
            "/api/splits",
            {"hostMemberId": "h", "totalAmount": invalid, "currency": "USD"},
        )
        check(code == 400, "invalid total " + str(invalid) + " rejected")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        _, projection = call("/api/business/snapshot?fixtureRunId=" + RUN + "-healthy")
        if (
            projection["quality"]["status"] == "FRESH"
            and projection["kpis"].get("USD", {}).get("B-K1", {}).get("denominator")
            == 1
        ):
            break
        time.sleep(0.1)
    observations["healthyProjection"] = projection
    check(projection["quality"]["status"] == "FRESH", "projection complete and fresh")
    k = projection["kpis"].get("USD", {})
    check(
        k.get("B-K1", {}).get("value") == 100
        and Decimal(k.get("B-K2", {}).get("value", "-1")) == 0,
        "independent healthy KPI",
    )
    for name in ["under", "over"]:
        _, projection = call("/api/business/snapshot?fixtureRunId=" + RUN + "-" + name)
        observations[name + "Projection"] = projection
        check(
            projection["kpis"].get("USD", {}).get("B-K1", {}).get("value") is None,
            name + " has no closures",
        )
    # Same-key sequential/concurrent payload consistency; exact raw identity is additionally kept by smoke.sh.
    key = RUN + "-payment"
    body = {"account": "EC-DEMO", "amount": 27.50, "currency": "USD"}
    code, first = call("/api/payments", body, headers={"X-Idempotency-Key": key})
    _, retry = call("/api/payments", body, headers={"X-Idempotency-Key": key})
    check(code == 200 and first == retry, "payment response stable across persistence")
    code, _ = call(
        "/api/payments", {**body, "amount": 28}, headers={"X-Idempotency-Key": key}
    )
    check(code == 409, "key reuse with different payload conflicts")
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(
            pool.map(
                lambda _: call(
                    "/api/payments",
                    body,
                    headers={"X-Idempotency-Key": key + "-concurrent"},
                ),
                range(4),
            )
        )
    check(
        all(r[0] == 200 for r in responses)
        and len({r[1].get("id") for r in responses}) == 1,
        "concurrent retries return one payment",
    )
    _, rows = call("/api/payments")
    check(
        sum(r["idempotencyKey"] == key for r in rows) == 1,
        "one persisted payment visible",
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        _, audit = call("/api/audit")
        matches = [e for e in audit if e["aggregateId"] == first["id"]]
        if matches:
            break
        time.sleep(0.25)
    check(
        len(matches) == 1 and matches[0]["eventType"] == "PAYMENT_CREATED",
        "exact payment has one audit event",
    )
    observations["payment"] = {
        "initial": first,
        "retry": retry,
        "audit": matches,
        "concurrent": responses,
    }
except Exception as exc:
    checks.append({"name": "harness exception", "passed": False, "error": repr(exc)})
finally:
    result = {
        "fixtureRunId": RUN,
        "checks": checks,
        "observations": observations,
        "passed": all(c["passed"] for c in checks),
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "checks": len(checks),
                "failed": [c["name"] for c in checks if not c["passed"]],
                "artifact": str(OUT / "result.json"),
            },
            indent=2,
        )
    )
    raise SystemExit(0 if result["passed"] else 1)
