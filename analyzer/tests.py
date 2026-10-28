"""
analyzer/tests.py
Integration and Web View Tests for FinSentry.
"""

from decimal import Decimal
import io
from django.test import TestCase, Client
from django.urls import reverse

from analyzer.models import StoredTransaction, StoredAnomalyFlag, AppSettings


class FinSentryWebTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.settings = AppSettings.get_settings()
        self.txn = StoredTransaction.objects.create(
            txn_id="TXN-TEST-1",
            date="2026-10-01",
            description="Test Grocery Store",
            amount=Decimal("1500.00"),
            type="EXPENSE",
            category="Groceries & Essentials",
            category_reason="Matched keyword 'grocery'"
        )

    def test_dashboard_status_code(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Grocery Store")
        self.assertContains(response, "Financial Overview")

    def test_transactions_view(self):
        response = self.client.get(reverse("transactions"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Grocery Store")

    def test_upload_csv_view_get(self):
        response = self.client.get(reverse("upload_csv"))
        self.assertEqual(response.status_code, 200)

    def test_upload_csv_post(self):
        csv_data = (
            "date,description,amount,type\n"
            "2026-10-15,New Salary,80000.00,INCOME\n"
        )
        csv_file = io.BytesIO(csv_data.encode("utf-8"))
        csv_file.name = "upload_test.csv"

        response = self.client.post(reverse("upload_csv"), {"csv_file": csv_file})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(StoredTransaction.objects.filter(description="New Salary").exists())

    def test_override_category(self):
        response = self.client.post(
            reverse("override_category", kwargs={"txn_id": self.txn.txn_id}),
            {"category": "Special Expense", "note": "Manual review"}
        )
        self.assertEqual(response.status_code, 302)  # Redirects back to ledger
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.category, "Special Expense")
        self.assertIn("User override", self.txn.category_reason)
