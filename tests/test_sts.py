"""
tests/test_sts.py
Automated unit tests for the Safe-To-Spend (STS) engine and Livia formula.
"""

from datetime import date
from decimal import Decimal
import unittest

from core.sts import SafeToSpendCalculator, STSResult


class TestSafeToSpendEngine(unittest.TestCase):
    def test_standard_sts_calculation(self):
        # 32,000 balance - (10,000 rent + 4,000 emi) = 18,000 after-fixed
        # 18,000 - (5,000 emergency + 3,000 savings + 2,000 goal) = 8,000 spendable
        sts = SafeToSpendCalculator.compute_sts(
            available_balance=Decimal("32000.00"),
            rent_amount=Decimal("10000.00"),
            rent_is_paid=False,
            emi_amount=Decimal("4000.00"),
            emi_is_paid=False,
            emergency_alloc=Decimal("5000.00"),
            savings_alloc=Decimal("3000.00"),
            goal_contribution=Decimal("2000.00"),
            salary_day=15,
            reference_date=date(2026, 10, 5),  # 10 days remaining until 15th
        )

        self.assertEqual(sts.after_fixed, Decimal("18000.00"))
        self.assertEqual(sts.spendable_balance, Decimal("8000.00"))
        self.assertEqual(sts.days_remaining, 10)
        self.assertEqual(sts.daily_sts, Decimal("800.00"))
        self.assertEqual(sts.weekly_sts, Decimal("5600.00"))
        self.assertEqual(sts.status, "HEALTHY")

    def test_rent_already_paid(self):
        # When rent is already paid, rent is NOT deducted from current balance again
        sts = SafeToSpendCalculator.compute_sts(
            available_balance=Decimal("32000.00"),
            rent_amount=Decimal("10000.00"),
            rent_is_paid=True,  # Paid!
            emi_amount=Decimal("4000.00"),
            emi_is_paid=False,
            emergency_alloc=Decimal("5000.00"),
            savings_alloc=Decimal("3000.00"),
            goal_contribution=Decimal("2000.00"),
            salary_day=15,
            reference_date=date(2026, 10, 5),
        )

        self.assertEqual(sts.unpaid_rent, Decimal("0.00"))
        self.assertEqual(sts.spendable_balance, Decimal("18000.00"))
        self.assertEqual(sts.daily_sts, Decimal("1800.00"))

    def test_depleted_runway(self):
        # Obligations exceed available balance
        sts = SafeToSpendCalculator.compute_sts(
            available_balance=Decimal("5000.00"),
            rent_amount=Decimal("10000.00"),
            rent_is_paid=False,
            emi_amount=Decimal("4000.00"),
            emi_is_paid=False,
            emergency_alloc=Decimal("2000.00"),
            savings_alloc=Decimal("1000.00"),
            goal_contribution=Decimal("0.00"),
            salary_day=1,
            reference_date=date(2026, 10, 20),
        )

        self.assertEqual(sts.status, "DEPLETED")
        self.assertEqual(sts.daily_sts, Decimal("0.00"))
        self.assertEqual(sts.weekly_sts, Decimal("0.00"))

    def test_check_before_you_buy(self):
        sts = SafeToSpendCalculator.compute_sts(
            available_balance=Decimal("32000.00"),
            rent_amount=Decimal("10000.00"),
            rent_is_paid=False,
            emi_amount=Decimal("4000.00"),
            emi_is_paid=False,
            emergency_alloc=Decimal("5000.00"),
            savings_alloc=Decimal("3000.00"),
            goal_contribution=Decimal("2000.00"),
            salary_day=15,
            reference_date=date(2026, 10, 5),  # 10 days, 8000 pool, 800/day
        )

        # 1. Affordable purchase (₹2,000 item)
        res_afford = SafeToSpendCalculator.check_before_you_buy(sts, Decimal("2000.00"))
        self.assertTrue(res_afford["can_afford"])
        self.assertEqual(res_afford["new_daily_sts"], Decimal("600.00"))  # (8000 - 2000) / 10 = 600

        # 2. Unaffordable purchase (₹12,000 item > 8,000 spendable pool)
        res_expensive = SafeToSpendCalculator.check_before_you_buy(sts, Decimal("12000.00"))
        self.assertFalse(res_expensive["can_afford"])
        self.assertEqual(res_expensive["impact"], "RESERVE_BREACH")
        self.assertEqual(res_expensive["new_daily_sts"], Decimal("0.00"))


if __name__ == "__main__":
    unittest.main()
