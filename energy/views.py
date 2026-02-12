"""
API Layer — Energy Consumption Endpoint (Django REST Framework)

This module exposes the HTTP interface for the energy consumption use case.

Design intent:

The view acts as a thin controller following the "fat application / thin
transport layer" principle. Its responsibilities are intentionally limited to:

- Basic input validation and type coercion
- Delegation to the application use case
- Translation of domain exceptions into HTTP responses
- Maintaining clear separation between transport concerns and business logic

Architectural decisions:

- No business rules are implemented here.
- All transactional guarantees (atomicity, locking, idempotency handling)
  are delegated to the application layer.
- Domain-specific exceptions are mapped explicitly to appropriate
  HTTP status codes (422, 404, 200 replay, etc.).

This structure reflects a pragmatic hexagonal approach:
the view is an adapter translating HTTP requests into
application-level operations without leaking transport logic
into the core use case.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from energy.application.use_cases import consume_energy
from energy.domain.exceptions import IdempotencyReplay, InsufficientEnergy
from energy.models import Account


class ConsumeEnergyView(APIView):
    """
    POST /api/energy/consume/

    Thin controller: validates input, delegates to use case, maps exceptions to HTTP responses.
    """

    def post(self, request):
        account_id = request.data.get("account_id")
        amount = request.data.get("amount")
        idempotency_key = request.data.get("idempotency_key")

        if not all([account_id, amount, idempotency_key]):
            return Response(
                {"error": "account_id, amount, and idempotency_key are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account_id = int(account_id)
            amount = int(amount)
        except (TypeError, ValueError):
            return Response(
                {"error": "account_id and amount must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount <= 0:
            return Response(
                {"error": "amount must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = consume_energy(account_id, amount, idempotency_key)
        except Account.DoesNotExist:
            return Response(
                {"error": "Account not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except InsufficientEnergy as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except IdempotencyReplay:
            return Response(
                {"message": "Request already processed."},
                status=status.HTTP_200_OK,
            )

        return Response(result, status=status.HTTP_200_OK)
