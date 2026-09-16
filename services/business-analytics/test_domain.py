from datetime import datetime, timezone, timedelta
from domain import calculate

NOW = datetime(2026, 9, 14, tzinfo=timezone.utc)


def session(status="COMPLETED", shares=("60.00", "40.00"), age=10, currency="USD"):
    return {
        "currency": currency,
        "status": status,
        "totalAmount": "100.00",
        "createdAt": (NOW - timedelta(seconds=age)).isoformat(),
        "closedAt": (
            (NOW - timedelta(seconds=age)).isoformat()
            if status == "COMPLETED"
            else None
        ),
        "participants": [
            {"shareAmount": s, "authorized": True, "paymentReference": "DEMO"}
            for s in shares
        ],
    }


def test_good_and_mutated_closures():
    assert calculate([session()], NOW)["USD"]["B-K1"]["value"] == 100
    k = calculate([session(shares=("60.00", "30.00"))], NOW)["USD"]
    assert k["B-K1"]["value"] == 0 and k["B-K2"]["value"] == "10.00"


def test_no_sample_after_window_without_event():
    data = [session(age=899)]
    assert calculate(data, NOW)["USD"]["B-K1"]["value"] == 100
    assert calculate(data, NOW + timedelta(seconds=2))["USD"]["B-K1"]["value"] is None


def test_backlog_expires_without_input_and_is_not_window_limited():
    data = [session("OPEN", ("60.00",), age=120)]
    assert calculate(data, NOW)["USD"]["B-K3"]["value"] == "0.00"
    assert (
        calculate(data, NOW + timedelta(seconds=1))["USD"]["B-K3"]["value"] == "60.00"
    )
    assert calculate(data, NOW + timedelta(days=1))["USD"]["B-K3"]["value"] == "60.00"


def test_resolution_and_currency_separation():
    a = session("OPEN", ("60.00",), age=121)
    b = session(currency="EUR")
    k = calculate([a, b], NOW)
    assert k["USD"]["B-K1"]["value"] is None and k["EUR"]["B-K1"]["value"] == 100
    a["status"] = "COMPLETED"
    a["closedAt"] = NOW.isoformat()
    assert calculate([a], NOW)["USD"]["B-K3"]["value"] == "0.00"
