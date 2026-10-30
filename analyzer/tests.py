"""
analyzer/tests.py
Django web integration tests for the FinSentry Safe-to-Spend website.
"""

from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from analyzer.models import UserFinancialProfile, DailySpendEntry


class FinSentryWebTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.profile = UserFinancialProfile.objects.create(
            user=self.user,
            monthly_salary=Decimal("60000.00"),
            salary_day=1,
            available_balance=Decimal("30000.00"),
            rent_amount=Decimal("10000.00"),
            rent_is_paid=False,
            emi_amount=Decimal("4000.00"),
            emi_is_paid=False,
            emergency_pool=Decimal("5000.00"),
            savings_pool=Decimal("3000.00"),
            goal_monthly_contribution=Decimal("2000.00"),
        )

    def test_unauthenticated_redirect_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_authenticated_dashboard(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Today's Remaining Safe-To-Spend")
        self.assertContains(response, "The Money Reservoir")

    def test_log_spend_view(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.post(
            reverse("log_spend"),
            {"description": "Office Lunch", "amount": "250.00"}
        )
        self.assertEqual(response.status_code, 302)  # Redirects back to dashboard
        self.assertTrue(DailySpendEntry.objects.filter(description="Office Lunch").exists())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.available_balance, Decimal("29750.00"))  # 30000 - 250

    def test_toggle_obligation(self):
        self.client.login(username="testuser", password="password123")
        self.assertFalse(self.profile.rent_is_paid)
        response = self.client.post(reverse("toggle_obligation", kwargs={"bill_type": "rent"}))
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.rent_is_paid)

    def test_check_before_you_buy_simulator(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.post(
            reverse("dashboard"),
            {"check_buy": "1", "item_name": "Book", "item_cost": "500.00"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Purchase Approved")
        # Session persistence check
        session = self.client.session
        self.assertIn("last_simulation", session)
        self.assertEqual(session["last_simulation"]["item_name"], "Book")

    def test_overspend_choice_emergency(self):
        self.client.login(username="testuser", password="password123")
        # Log heavy spend that triggers overspend through real view
        self.client.post(
            reverse("log_spend"),
            {"description": "Big Expense", "amount": "5000.00"}
        )
        # Check dashboard triggers overspend
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["has_overspend"])
        self.assertContains(response, "Daily Overspend Alert")

        # Resolve via Emergency
        res = self.client.post(reverse("resolve_overspend"), {"choice": "emergency"})
        self.assertEqual(res.status_code, 302)
        self.profile.refresh_from_db()
        # Emergency pool should be drained by overspend amount
        self.assertLess(self.profile.emergency_pool, Decimal("5000.00"))
        self.assertGreater(self.profile.overspend_absorbed_today, Decimal("0.00"))


    def test_exact_subtraction_when_spending_money(self):
        """Verifies that spending ₹10 drops remaining_today by EXACTLY ₹10 (Livia frozen daily ceiling)."""
        self.client.login(username="testuser", password="password123")
        # 1. Check initial dashboard remaining budget
        res_initial = self.client.get(reverse("dashboard"))
        initial_remaining = res_initial.context["remaining_today"]

        # 2. Spend exactly ₹10.00
        self.client.post(
            reverse("log_spend"),
            {"description": "Chikki Snack", "amount": "10.00"}
        )

        # 3. Check updated dashboard remaining budget
        res_after = self.client.get(reverse("dashboard"))
        after_remaining = res_after.context["remaining_today"]

        # 4. Assert that remaining dropped by EXACTLY 10.00 (not 15!)
        drop = initial_remaining - after_remaining
        self.assertEqual(drop, Decimal("10.00"))
