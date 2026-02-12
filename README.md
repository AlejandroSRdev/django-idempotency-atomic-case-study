# Django Idempotency & Atomicity Case Study

A minimal, production-conscious Django endpoint that demonstrates transactional correctness, concurrency control, and idempotency enforcement at the database level.

This is not a tutorial or a feature-rich application. It is an engineering case study designed to illustrate how a simple write operation can be made safe under concurrent and retry-prone conditions.

## Architectural Intent

The project follows a clean separation of concerns inspired by hexagonal architecture:

```
energy/
├── domain/
│   └── exceptions.py        # Domain-level error semantics
├── application/
│   └── use_cases.py          # Business logic, transaction boundaries
├── models.py                 # Persistence representation (Django ORM)
├── views.py                  # Thin HTTP adapter (DRF)
├── urls.py                   # Route definitions
└── tests.py                  # Integration tests
```

- **Views** handle input validation and HTTP response mapping. No business logic.
- **Use cases** own the transaction boundary and enforce all invariants.
- **Models** are persistence representations. No domain behavior in `save()`.
- **Domain exceptions** express business-level failure modes, not framework errors.

## Why Idempotency at the Database Level

Client retries, network timeouts, and load balancer replays can cause the same request to arrive multiple times. Application-level deduplication (e.g., in-memory sets, Redis caches) introduces additional failure modes and does not survive process restarts.

A `UNIQUE` constraint on `idempotency_key` in the `EnergyConsumption` table guarantees that the database itself rejects duplicate processing, regardless of application state. If a duplicate `INSERT` is attempted, the database raises an `IntegrityError`, which the use case catches and translates into an `IdempotencyReplay` domain exception.

## Why `select_for_update()`

Without row-level locking, two concurrent requests for the same account can both read the current balance, both determine that sufficient energy exists, and both proceed to deduct, resulting in a balance that is lower than it should be, or negative.

`select_for_update()` acquires an exclusive lock on the account row within the transaction. The second concurrent request blocks until the first transaction commits or rolls back, at which point it reads the updated balance.

## Race Condition Scenario

Without protection, two concurrent requests (each consuming 60 from a balance of 100) could execute as:

```
T1: SELECT energy FROM account WHERE id=1  →  100
T2: SELECT energy FROM account WHERE id=1  →  100
T1: UPDATE account SET energy = 100 - 60   →  40
T2: UPDATE account SET energy = 100 - 60   →  40   (should have been rejected)
```

Both succeed. The account loses 120 energy from a balance of 100.

With `select_for_update()`:

```
T1: SELECT ... FOR UPDATE  →  100 (row locked)
T2: SELECT ... FOR UPDATE  →  blocks, waiting for T1
T1: UPDATE energy = 40, COMMIT
T2: SELECT ... FOR UPDATE  →  40  (now sees committed value)
T2: 40 < 60 → InsufficientEnergy raised, no deduction
```

## `transaction.atomic()`

All operations within the use case (lock, validation, insert, update) execute inside a single `transaction.atomic()` block. If any step fails, the entire transaction rolls back:

- If energy is insufficient, no `EnergyConsumption` record is created.
- If the idempotency check fails (duplicate key), the balance is not modified.
- The database never reaches an inconsistent state.

## What Breaks Without These Protections

| Protection removed          | Failure mode                                                  |
|-----------------------------|---------------------------------------------------------------|
| `transaction.atomic()`      | Partial writes: consumption record created but balance not updated, or vice versa |
| `select_for_update()`       | Race condition: concurrent requests overdraw the account      |
| `UNIQUE` on idempotency_key | Duplicate processing: retried requests deduct energy multiple times |
| `F()` expression            | Stale-read update: Python-cached balance overwrites concurrent changes |

## Running Locally

```bash
# Clone and enter the project
git clone <repository-url>
cd django-idempotency-atomicity-case-study

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install django djangorestframework

# Apply migrations
python manage.py migrate

# Run the development server
python manage.py runserver
```

### Example request

```bash
curl -X POST http://localhost:8000/api/energy/consume/ \
  -H "Content-Type: application/json" \
  -d '{"account_id": 1, "amount": 30, "idempotency_key": "abc-123"}'
```

## Tests

```bash
python manage.py test energy
```

The test suite validates:

- **Successful consumption** deducts energy and creates a consumption record.
- **Idempotency** ensures a duplicate `idempotency_key` does not deduct energy a second time.
- **Insufficient energy** rejects the request and leaves the balance unchanged (rollback).
- **Missing/invalid input** returns appropriate 400 responses.
- **Accumulation** verifies that sequential requests with distinct keys each deduct correctly.

All tests use `django.test.TestCase`, which wraps each test in a transaction and rolls back on completion.

## Production Considerations

This case study uses SQLite for simplicity. In production:

- Use PostgreSQL for proper `SELECT ... FOR UPDATE` support. SQLite serializes writes at the database level, which masks concurrency issues during development.
- Idempotency keys should have a TTL or archival strategy to prevent unbounded table growth.
- Structured logging should feed into an observability stack (e.g., ELK, Datadog).
- Authentication and rate limiting are intentionally omitted to keep the focus on transactional correctness.