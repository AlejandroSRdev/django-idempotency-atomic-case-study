"""
Application Use Case — Energy Consumption

This use case demonstrates a production-oriented implementation of a balance
deduction operation under concurrent conditions.

It intentionally focuses on correctness guarantees over architectural purism.

Core guarantees provided:

- Atomicity: The full operation executes inside a transaction.atomic() block.
- Row-level locking: select_for_update() prevents concurrent reads of stale balances.
- Idempotency: Enforced via a unique constraint on idempotency_key at the database level.
- Race-condition safety: The balance update uses a database-level F() expression.
- Explicit domain signaling: Business rule violations raise domain-specific exceptions.

Architectural note:

For simplicity and clarity, domain rules are evaluated close to the persistence
model. In larger systems, aggregate roots and repository ports would be
explicitly separated following a stricter hexagonal architecture.

This example prioritizes transactional integrity and concurrency safety,
as these are the critical concerns in real-world financial or quota-based systems.
"""

import logging

from django.db import IntegrityError, transaction
from django.db.models import F

from energy.domain.exceptions import IdempotencyReplay, InsufficientEnergy
from energy.models import Account, EnergyConsumption

logger = logging.getLogger(__name__)


def consume_energy(account_id, amount, idempotency_key):
    """
    Deducts energy from an account in a single atomic operation.

    Guarantees:
    - Atomicity via transaction.atomic()
    - Row-level locking via select_for_update() to prevent concurrent modification
    - Idempotency via unique constraint on idempotency_key
    - Race-condition safety via F() expression for the balance update
    """
    with transaction.atomic():
        # Lock the account row to prevent concurrent reads of stale balance
        account = (
            Account.objects
            .select_for_update()
            .get(id=account_id)
        )

        if account.energy < amount:
            logger.warning(
                "Insufficient energy: account=%s requested=%s available=%s",
                account_id, amount, account.energy,
            )
            raise InsufficientEnergy(account_id, amount, account.energy)

        try:
            EnergyConsumption.objects.create(
                account_id=account_id,
                amount=amount,
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            # Duplicate idempotency_key: this request was already processed
            logger.info(
                "Idempotency replay: key=%s account=%s",
                idempotency_key, account_id,
            )
            raise IdempotencyReplay(idempotency_key)

        # F() expression ensures the UPDATE uses the database value, not the Python-cached one
        Account.objects.filter(id=account_id).update(energy=F("energy") - amount)

        account.refresh_from_db()

    return {
        "account_id": account.id,
        "remaining_energy": account.energy,
        "amount_consumed": amount,
    }