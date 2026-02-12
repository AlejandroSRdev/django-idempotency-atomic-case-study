class InsufficientEnergy(Exception):
    """Raised when an account does not have enough energy to fulfill a consumption request."""

    def __init__(self, account_id, requested, available):
        self.account_id = account_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Account {account_id}: requested {requested}, available {available}"
        )


class IdempotencyReplay(Exception):
    """Raised when a consumption request with a duplicate idempotency_key is detected."""

    def __init__(self, idempotency_key):
        self.idempotency_key = idempotency_key
        super().__init__(
            f"Idempotency replay detected for key: {idempotency_key}"
        )