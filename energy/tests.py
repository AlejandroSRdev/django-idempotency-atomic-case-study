from django.test import TestCase
from rest_framework.test import APIClient

from energy.models import Account, EnergyConsumption


class ConsumeEnergyEndpointTest(TestCase):
    """
    Tests for POST /api/energy/consume/

    Each test runs inside a transaction that is rolled back automatically,
    ensuring full isolation between test cases.
    """

    def setUp(self):
        self.client = APIClient()
        self.account = Account.objects.create(energy=100)

    def test_successful_consumption(self):
        response = self.client.post("/api/energy/consume/", {
            "account_id": self.account.id,
            "amount": 30,
            "idempotency_key": "key-success-1",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["remaining_energy"], 70)
        self.assertEqual(response.data["amount_consumed"], 30)

        self.account.refresh_from_db()
        self.assertEqual(self.account.energy, 70)
        self.assertEqual(EnergyConsumption.objects.count(), 1)

    def test_idempotency_prevents_double_deduction(self):
        """Same idempotency_key must not deduct energy twice."""
        payload = {
            "account_id": self.account.id,
            "amount": 20,
            "idempotency_key": "key-idempotent-1",
        }

        first_response = self.client.post("/api/energy/consume/", payload)
        self.assertEqual(first_response.status_code, 200)

        second_response = self.client.post("/api/energy/consume/", payload)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.data["message"], "Request already processed.")

        self.account.refresh_from_db()
        self.assertEqual(self.account.energy, 80)
        self.assertEqual(EnergyConsumption.objects.count(), 1)

    def test_insufficient_energy_rolls_back(self):
        """Requesting more energy than available must fail without side effects."""
        response = self.client.post("/api/energy/consume/", {
            "account_id": self.account.id,
            "amount": 200,
            "idempotency_key": "key-insufficient-1",
        })

        self.assertEqual(response.status_code, 422)

        self.account.refresh_from_db()
        self.assertEqual(self.account.energy, 100)
        self.assertEqual(EnergyConsumption.objects.count(), 0)

    def test_account_not_found(self):
        response = self.client.post("/api/energy/consume/", {
            "account_id": 99999,
            "amount": 10,
            "idempotency_key": "key-notfound-1",
        })

        self.assertEqual(response.status_code, 404)

    def test_missing_fields_returns_400(self):
        response = self.client.post("/api/energy/consume/", {
            "account_id": self.account.id,
        })

        self.assertEqual(response.status_code, 400)

    def test_negative_amount_returns_400(self):
        response = self.client.post("/api/energy/consume/", {
            "account_id": self.account.id,
            "amount": -5,
            "idempotency_key": "key-negative-1",
        })

        self.assertEqual(response.status_code, 400)

    def test_multiple_consumptions_accumulate(self):
        """Sequential valid requests with different keys must each deduct correctly."""
        self.client.post("/api/energy/consume/", {
            "account_id": self.account.id,
            "amount": 30,
            "idempotency_key": "key-multi-1",
        })
        self.client.post("/api/energy/consume/", {
            "account_id": self.account.id,
            "amount": 25,
            "idempotency_key": "key-multi-2",
        })

        self.account.refresh_from_db()
        self.assertEqual(self.account.energy, 45)
        self.assertEqual(EnergyConsumption.objects.count(), 2)
