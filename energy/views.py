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
