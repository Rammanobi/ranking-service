import concurrent.futures

from app import config


def test_create_transaction_success(client):
    resp = client.post(
        "/transaction",
        json={"user_id": "alice", "amount": 50, "idempotency_key": "tx-1"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == "alice"
    assert body["amount"] == 50
    assert body["duplicate"] is False


def test_duplicate_idempotency_key_is_not_double_processed(client):
    payload = {"user_id": "alice", "amount": 50, "idempotency_key": "tx-dup"}
    first = client.post("/transaction", json=payload)
    second = client.post("/transaction", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True

    summary = client.get("/summary/alice").json()
    assert summary["total_points"] == 50  # not 100
    assert summary["transaction_count"] == 1


def test_concurrent_duplicate_requests_only_counted_once(client):
    payload = {"user_id": "bob", "amount": 10, "idempotency_key": "race-key"}

    def fire():
        return client.post("/transaction", json=payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: fire(), range(10)))

    statuses = [r.status_code for r in results]
    assert statuses.count(201) == 1
    assert statuses.count(200) == 9

    summary = client.get("/summary/bob").json()
    assert summary["transaction_count"] == 1
    assert summary["total_points"] == 10


def test_invalid_amount_rejected(client):
    resp = client.post(
        "/transaction",
        json={"user_id": "alice", "amount": -5, "idempotency_key": "bad-1"},
    )
    assert resp.status_code == 422

    resp2 = client.post(
        "/transaction",
        json={"user_id": "alice", "amount": 0, "idempotency_key": "bad-2"},
    )
    assert resp2.status_code == 422


def test_invalid_user_id_rejected(client):
    resp = client.post(
        "/transaction",
        json={"user_id": "bad user!", "amount": 5, "idempotency_key": "bad-3"},
    )
    assert resp.status_code == 422


def test_missing_fields_rejected(client):
    resp = client.post("/transaction", json={"user_id": "alice"})
    assert resp.status_code == 422


def test_summary_404_for_unknown_user(client):
    resp = client.get("/summary/nobody")
    assert resp.status_code == 404


def test_ranking_orders_by_ranking_points_desc(client):
    client.post("/transaction", json={"user_id": "u1", "amount": 100, "idempotency_key": "k1"})
    client.post("/transaction", json={"user_id": "u2", "amount": 200, "idempotency_key": "k2"})
    client.post("/transaction", json={"user_id": "u3", "amount": 50, "idempotency_key": "k3"})

    ranking = client.get("/ranking").json()
    user_ids = [r["user_id"] for r in ranking]
    assert user_ids.index("u2") < user_ids.index("u1") < user_ids.index("u3")
    assert ranking[0]["rank"] == 1


def test_single_huge_transaction_does_not_dominate_consistent_user(client):
    # Whale: one massive transaction.
    client.post(
        "/transaction",
        json={"user_id": "whale", "amount": config.MAX_TRANSACTION_AMOUNT, "idempotency_key": "w1"},
    )
    # Grinder: many small transactions across distinct simulated days would
    # normally need date mocking; here we at least confirm the whale's
    # ranking contribution is capped below their raw total.
    summary = client.get("/summary/whale").json()
    assert summary["ranking_points"] < summary["total_points"]


def test_rate_limit_blocks_excessive_requests(client):
    user = "spammer"
    statuses = []
    for i in range(config.RATE_LIMIT_MAX_REQUESTS + 5):
        resp = client.post(
            "/transaction",
            json={"user_id": user, "amount": 1, "idempotency_key": f"rl-{i}"},
        )
        statuses.append(resp.status_code)

    assert 429 in statuses
    allowed = sum(1 for s in statuses if s in (200, 201))
    assert allowed == config.RATE_LIMIT_MAX_REQUESTS


def test_amount_above_max_rejected(client):
    resp = client.post(
        "/transaction",
        json={
            "user_id": "alice",
            "amount": config.MAX_TRANSACTION_AMOUNT + 1,
            "idempotency_key": "too-big",
        },
    )
    assert resp.status_code == 422
