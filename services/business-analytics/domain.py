from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation


def dt(value):
    if not isinstance(value, str):
        raise ValueError("timestamp string required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("UTC offset required")
    return result


def calculate(sessions, now, fixture=None):
    if fixture is not None:
        sessions = [s for s in sessions if s.get("fixtureRunId") == fixture]
    result = {}
    for currency in sorted({s["currency"] for s in sessions}):
        population = [s for s in sessions if s["currency"] == currency]
        closed = [
            s
            for s in population
            if s["status"] == "COMPLETED"
            and s.get("closedAt")
            and now - timedelta(minutes=15) < dt(s["closedAt"]) <= now
        ]

        def valid(s):
            ps = s["participants"]
            return (
                bool(ps)
                and all(
                    p["authorized"]
                    and p.get("paymentReference")
                    and p["paymentReference"].strip()
                    and Decimal(p["shareAmount"]) > 0
                    for p in ps
                )
                and sum((Decimal(p["shareAmount"]) for p in ps), Decimal(0))
                == Decimal(s["totalAmount"])
            )

        gap = sum(
            (
                abs(
                    Decimal(s["totalAmount"])
                    - sum(
                        (
                            Decimal(p["shareAmount"])
                            for p in s["participants"]
                            if p["authorized"]
                        ),
                        Decimal(0),
                    )
                )
                for s in closed
            ),
            Decimal(0),
        )
        backlog = [
            s
            for s in population
            if s["status"] == "OPEN"
            and dt(s["createdAt"]) < now - timedelta(seconds=120)
        ]
        exposed = sum(
            (
                Decimal(p["shareAmount"])
                for s in backlog
                for p in s["participants"]
                if p["authorized"]
            ),
            Decimal(0),
        )
        result[currency] = {
            "B-K1": {
                "value": (
                    100 * sum(valid(s) for s in closed) / len(closed)
                    if closed
                    else None
                ),
                "status": "OK" if closed else "NO_SAMPLE",
                "numerator": sum(valid(s) for s in closed),
                "denominator": len(closed),
                "unit": "percent",
            },
            "B-K2": {
                "value": str(gap.quantize(Decimal("0.01"))),
                "unit": currency,
                "status": "OK" if closed else "NO_SAMPLE",
            },
            "B-K3": {
                "value": str(exposed.quantize(Decimal("0.01"))),
                "unit": currency,
                "status": "OK",
                "backlogSessions": len(backlog),
            },
        }
    return result


def validate(event):
    if not isinstance(event, dict):
        raise ValueError("event must be an object")
    required = {
        "schemaVersion",
        "eventId",
        "eventType",
        "aggregateId",
        "aggregateVersion",
        "occurredAt",
        "correlationId",
        "fixtureRunId",
        "data",
    }
    if (
        not required <= event.keys()
        or event["schemaVersion"] != 1
        or type(event["aggregateVersion"]) is not int
        or not 1 <= event["aggregateVersion"] < 2**63
    ):
        raise ValueError("invalid envelope")
    if event["eventType"] not in {
        "SPLIT_CREATED",
        "PARTICIPANT_ADDED",
        "PARTICIPANT_AUTHORIZED",
        "SPLIT_COMPLETED",
    }:
        raise ValueError("unknown event type")
    for key in ("eventId", "aggregateId", "correlationId"):
        if not isinstance(event[key], str) or not event[key].strip():
            raise ValueError("nonempty identity required")
    s = event["data"]
    if (
        s["id"] != event["aggregateId"]
        or s["aggregateVersion"] != event["aggregateVersion"]
    ):
        raise ValueError("aggregate identity/version mismatch")
    if s["status"] not in {"OPEN", "COMPLETED"}:
        raise ValueError("invalid status")
    if s["status"] == "COMPLETED" and not s.get("closedAt"):
        raise ValueError("completed session lacks closedAt")
    occurred = dt(event["occurredAt"])
    created = dt(s["createdAt"])
    if s.get("closedAt") and dt(s["closedAt"]) < created:
        raise ValueError("closedAt before creation")
    import re

    if not isinstance(s["currency"], str) or not re.fullmatch(
        "[A-Z]{3}", s["currency"]
    ):
        raise ValueError("invalid currency")
    for amount in [s["totalAmount"]] + [
        part["shareAmount"] for part in s["participants"]
    ]:
        if not isinstance(amount, str) or not re.fullmatch(
            r"-?\d{1,17}\.\d{2}", amount
        ):
            raise ValueError("finite decimal string with two places required")
        if not Decimal(amount).is_finite():
            raise ValueError("finite money required")
    for part in s["participants"]:
        if type(part["authorized"]) is not bool:
            raise ValueError("boolean authorization required")
        if part.get("paymentReference") is not None and not isinstance(
            part["paymentReference"], str
        ):
            raise ValueError("reference must be string or null")
    return event
