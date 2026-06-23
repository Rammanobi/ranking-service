# Video Walkthrough Script (target: 3–5 minutes)

Record your screen with the backend running (`uvicorn app.main:app --reload`),
`http://localhost:8000/docs` open in one tab, and the frontend
(`frontend/index.html`) open in another. Talk through the points below in
your own words — this is a script of *content*, not a word-for-word
transcript.

---

## 1. Intro (≈30s)

"This is a ranking service with three APIs — `POST /transaction`,
`GET /summary/:userId`, and `GET /ranking` — plus a small frontend that
exercises all three. It's built in Python with FastAPI and SQLite. I'll
walk through how it works, then focus on the three things this assignment
is really testing: duplicate handling, concurrency safety, and fair
ranking."

*(Show the project structure briefly — backend/app, tests, frontend.)*

## 2. API walkthrough, live (≈60–90s)

Switch to the frontend (or `/docs`):

- Submit a transaction for `alice`, amount `50`. Show the `201` response
  with `duplicate: false`.
- Submit it *again with the exact same idempotency key* — show it comes
  back `200` with `duplicate: true`, and that `/summary/alice` still shows
  `total_points: 50`, not `100`. *"This is the idempotency-key mechanism —
  the client supplies a key per logical transaction, and retries of that
  same key never get double-counted."*
- Submit a transaction with a negative amount, or a bad `user_id` (e.g. with
  spaces) — show the `422` with a clear validation message.
- Submit a few transactions for a second user (`bob`), then open
  `GET /ranking` — show both users ranked, and explain that the order is
  by `ranking_points`, not raw `total_points`.

## 3. Ranking fairness (≈45–60s)

"The ranking isn't just a sum of points — that's trivially gameable: one
person submits one giant transaction and instantly takes #1 with zero
real engagement. So the score is:

`ranking_points = 0.7 * capped_points + 0.3 * (active_days * 10)`

`capped_points` sums each transaction's amount, but caps any single
transaction's *contribution to ranking* at a configurable ceiling — the
raw total is still shown in `/summary`, just not used for ranking past
that cap. `active_days` counts distinct days the user was active, which
rewards consistent participation over one-off spikes. Both weights and the
cap are named constants in `config.py`, so the formula is fully auditable
and tunable — not a black box."

*(Optionally point at `app/ranking.py` on screen for 5 seconds.)*

## 4. Concurrency & data consistency (≈45–60s)

"Two things make this safe under concurrent load. First, every transaction
insert and its corresponding summary/ranking update happen inside a single
SQLite transaction — they commit or roll back together, so `/summary` can
never reflect a half-applied update. Second, duplicate detection is
race-safe: I wrap the check-then-insert in a process-wide lock, and even if
two identical requests somehow raced past that, the database's own UNIQUE
constraint on the idempotency key would reject the second insert, which I
catch and treat as an idempotent duplicate rather than an error."

*(Show `tests/test_api.py::test_concurrent_duplicate_requests_only_counted_once`
— fires 10 identical concurrent requests, asserts exactly one was recorded.
Run `pytest -v` on screen and let it pass.)*

## 5. Abuse prevention (≈20–30s)

"Beyond duplicate detection, there's a per-user rate limit — max 10
requests per 60-second window — so a script submitting many *distinct*
fake transactions still gets throttled with a 429. Inputs are also
strictly validated: bounded amount ranges, restricted character sets for
IDs, and explicit rejection of NaN/Infinity, which pass a naive float check
but would corrupt the running totals."

## 6. Trade-offs & limitations (≈30–45s)

"A few things I'd call out as deliberate scope cuts: this is a
single-process design — the write lock and rate limiter live in process
memory, so a multi-instance deployment would need the rate limiter moved to
something shared like Redis, and would rely on the database's UNIQUE
constraint alone for duplicate safety, which it already does as a
fallback. There's also no authentication — `user_id` is trusted from the
request body, which in a real system you'd derive from an authenticated
session instead. Both are documented in the README."

## 7. Close (≈10–15s)

"That covers the three APIs, the ranking formula, and how duplicates,
concurrency, and abuse are handled. Code, tests, and the README with setup
instructions are all in the repo."

---

### Recording checklist
- [ ] Backend running locally, `/docs` reachable
- [ ] Frontend open, API base URL pointed at the backend
- [ ] Terminal ready to run `pytest tests/ -v`
- [ ] `app/ranking.py` and `app/repository.py` open in editor tabs to glance at
- [ ] Keep total runtime to 3–5 minutes — rehearse once before recording
