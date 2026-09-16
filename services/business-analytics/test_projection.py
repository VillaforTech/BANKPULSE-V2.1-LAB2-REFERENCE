import os, uuid, copy
import pytest

pytestmark = pytest.mark.skipif(
    "analytics_contract_test" not in os.getenv("ANALYTICS_DSN", ""),
    reason="requires isolated analytics_contract_test schema",
)


def event(version=1, shares=None):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    return {
        "schemaVersion": 1,
        "eventId": str(uuid.uuid4()),
        "eventType": "SPLIT_CREATED",
        "aggregateId": "contract-session",
        "aggregateVersion": version,
        "occurredAt": now,
        "correlationId": "contract",
        "fixtureRunId": "contract",
        "data": {
            "id": "contract-session",
            "aggregateVersion": version,
            "totalAmount": "100.00",
            "currency": "USD",
            "status": "OPEN",
            "createdAt": now,
            "closedAt": None,
            "fixtureRunId": "contract",
            "participants": [],
        },
    }


@pytest.fixture(autouse=True)
def database():
    import app

    app.initialize()
    with app.connection() as c:
        c.execute(
            "TRUNCATE received_events,split_projection,checkpoints,rejected_events,snapshots"
        )
    app.state.update(
        brokerOk=True,
        lag=0,
        lastPoll=__import__("time").time(),
        sourcePending=0,
        sourceCount=1,
        sourceVersions=3,
    )


def test_duplicate_disorder_and_gap_resolution():
    import app

    first = event(1)
    third = event(3)
    app.apply(first, 0, 0)
    app.apply(third, 0, 1)
    assert app.snapshot()["quality"]["status"] == "INCOMPLETE"
    assert not app.apply(first, 0, 2)
    second = event(2)
    second["occurredAt"] = first["occurredAt"]
    app.apply(second, 0, 3)
    snapshot = app.snapshot()
    assert (
        snapshot["coverage"]["eventCount"] == 3
        and snapshot["quality"]["status"] == "FRESH"
    )
    with app.connection() as c:
        assert c.execute("SELECT version FROM split_projection").fetchone()[0] == 3
        assert c.execute("SELECT offset_value FROM checkpoints").fetchone()[0] == 4
    assert snapshot["sourceEventId"] == third["eventId"]


def test_rejection_checkpoints_and_blocks_quality():
    import app

    app.reject(0, 8, ValueError("poison JSON"))
    with app.connection() as c:
        assert c.execute("SELECT offset_value FROM checkpoints").fetchone()[0] == 9
        assert c.execute("SELECT count(*) FROM rejected_events").fetchone()[0] == 1
    assert app.snapshot()["quality"]["status"] == "INCOMPLETE"


def test_projection_transaction_rolls_back_event_and_offset():
    import app, psycopg

    with app.connection() as c:
        c.execute(
            "ALTER TABLE split_projection ADD CONSTRAINT contract_limit CHECK(version<3)"
        )
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            app.apply(event(3), 0, 0)
        with app.connection() as c:
            assert c.execute("SELECT count(*) FROM received_events").fetchone()[0] == 0
            assert c.execute("SELECT count(*) FROM checkpoints").fetchone()[0] == 0
    finally:
        with app.connection() as c:
            c.execute("ALTER TABLE split_projection DROP CONSTRAINT contract_limit")


def test_finite_money_and_timestamps_are_contract_errors():
    from domain import validate

    for amount in ["NaN", "Infinity", "1.001", "1e99", None]:
        e = event()
        e["data"]["totalAmount"] = amount
        with pytest.raises(ValueError):
            validate(e)
    for date in ["2026-09-14T00:00:00", None, 17]:
        e = event()
        e["data"]["createdAt"] = date
        with pytest.raises(ValueError):
            validate(e)


def test_empty_tail_offsets_do_not_invent_loss_but_real_gaps_fail():
    import app

    assert app.effective_offset(-1001, 138, 0, 138) == 138
    assert app.effective_offset(-1001, 138, 0, 140) == 138
    for position, checkpoint, low, high in [
        (-1001, 2, 3, 9),
        (2, 3, 3, 9),
        (-1001, 12, 0, 9),
    ]:
        with pytest.raises(ValueError):
            app.effective_offset(position, checkpoint, low, high)
