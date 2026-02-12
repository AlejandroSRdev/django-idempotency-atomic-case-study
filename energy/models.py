from django.db import models


class Account(models.Model):
    """
    Represents a simple account with a mutable energy balance.

    In a production-grade system, this would likely be part of a broader
    domain model (e.g., User aggregate). For this case study, we isolate it
    to focus on transaction safety and concurrency control.
    """

    energy = models.IntegerField()

    def __str__(self):
        return f"Account {self.id} - Energy: {self.energy}"


class EnergyConsumption(models.Model):
    """
    Stores individual energy consumption events.

    Key architectural decisions:
    - idempotency_key is UNIQUE at the database level to prevent
      duplicate processing under retries.
    - account is a foreign key to enforce referential integrity.
    - created_at provides traceability for auditing purposes.
    """

    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="consumptions"
    )

    amount = models.IntegerField()

    # Unique constraint enforces idempotency at the persistence layer.
    idempotency_key = models.CharField(
        max_length=100,
        unique=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Consumption {self.id} - {self.amount}"
