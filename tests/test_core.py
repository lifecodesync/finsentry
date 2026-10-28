"""
tests/test_core.py
Comprehensive automated test suite for FinSentry core logic.
Uses Python's standard unittest framework.
"""

from datetime import date, timedelta
from decimal import Decimal
import io
import unittest

from core.exceptions import CSVFormatError, InvalidRowError
from core.models import Transaction, TransactionType
from core.parser import CSVTransactionParser
from core.categorizer import TransactionCategorizer
from core.analytics import CashFlowAnalytics
from core.detector import RiskAndAnomalyDetector


class TestCSVTransactionParser(unittest.TestCase):
    def setUp(self):
        self.parser = CSVTransactionParser(check_duplicates=True)

    def test_valid_csv_parsing(self):
        sample = (
            "date,description,amount,type\n"
            "2026-10-01,Salary,50000.00,INCOME\n"
            "2026-10-02,Groceries,1500.50,EXPENSE\n"
        )
        result = self.parser.parse_file(io.StringIO(sample))
        self.assertEqual(result.clean_count, 2)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.transactions[0].amount, Decimal("50000.00"))
        self.assertEqual(result.transactions[0].type, TransactionType.INCOME)
        self.assertEqual(result.transactions[1].type, TransactionType.EXPENSE)

    def test_missing_header_raises_error(self):
        sample = "date,description,amount\n2026-10-01,Salary,50000\n"
        with self.assertRaises(CSVFormatError):
            self.parser.parse_file(io.StringIO(sample))

    def test_dirty_rows_are_isolated(self):
        sample = (
            "date,description,amount,type\n"
            "2026-10-01,Salary,50000.00,INCOME\n"
            "2026-10-32,Bad Date,500.00,EXPENSE\n"
            "2026-10-03,Negative Amt,-200.00,EXPENSE\n"
            "2026-10-04,String Amt,NotANumber,EXPENSE\n"
        )
        result = self.parser.parse_file(io.StringIO(sample))
        self.assertEqual(result.clean_count, 1)
        self.assertEqual(result.error_count, 3)
        # Check error attributes
        self.assertEqual(result.errors[0].field, "date")
        self.assertEqual(result.errors[1].field, "amount")
        self.assertEqual(result.errors[2].field, "amount")

    def test_duplicate_detection(self):
        sample = (
            "date,description,amount,type\n"
            "2026-10-01,Dinner,1200.00,EXPENSE\n"
            "2026-10-01,Dinner,1200.00,EXPENSE\n"
        )
        result = self.parser.parse_file(io.StringIO(sample))
        self.assertEqual(result.clean_count, 2)
        self.assertEqual(result.duplicate_count, 1)
        self.assertFalse(result.transactions[0].is_duplicate)
        self.assertTrue(result.transactions[1].is_duplicate)


class TestCategorizer(unittest.TestCase):
    def setUp(self):
        self.categorizer = TransactionCategorizer()

    def test_explainable_categorization(self):
        txn = Transaction(
            id="TXN-1",
            date=date(2026, 10, 2),
            description="Netflix Subscription",
            amount=Decimal("649.00"),
            type=TransactionType.EXPENSE
        )
        self.categorizer.categorize_transaction(txn)
        self.assertEqual(txn.category, "Entertainment & Subscriptions")
        self.assertIn("netflix", txn.category_reason)

    def test_user_override(self):
        txn = Transaction(
            id="TXN-2",
            date=date(2026, 10, 2),
            description="Special Tool",
            amount=Decimal("2000.00"),
            type=TransactionType.EXPENSE,
            category="Miscellaneous"
        )
        self.categorizer.apply_user_override(txn, "Work & Education", "Purchased IDE license")
        self.assertEqual(txn.category, "Work & Education")
        self.assertIn("User override", txn.category_reason)
        self.assertIn("Purchased IDE license", txn.category_reason)


class TestAnalytics(unittest.TestCase):
    def setUp(self):
        self.analytics = CashFlowAnalytics()
        self.transactions = [
            Transaction("1", date(2026, 10, 1), "Salary", Decimal("60000.00"), TransactionType.INCOME, "Income"),
            Transaction("2", date(2026, 10, 2), "Rent", Decimal("15000.00"), TransactionType.EXPENSE, "Rent"),
            Transaction("3", date(2026, 10, 3), "Groceries", Decimal("5000.00"), TransactionType.EXPENSE, "Groceries"),
        ]

    def test_cash_flow_calculation(self):
        summary = self.analytics.calculate_summary(self.transactions)
        self.assertEqual(summary.total_income, Decimal("60000.00"))
        self.assertEqual(summary.total_expenses, Decimal("20000.00"))
        self.assertEqual(summary.net_savings, Decimal("40000.00"))
        self.assertAlmostEqual(summary.savings_rate_pct, 66.67, places=1)


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.detector = RiskAndAnomalyDetector(baseline_spike_multiplier=2.5)

    def test_baseline_spike_detection(self):
        txns = [
            Transaction("1", date(2026, 10, 1), "Dinner A", Decimal("1000.00"), TransactionType.EXPENSE, "Food"),
            Transaction("2", date(2026, 10, 5), "Dinner B", Decimal("1200.00"), TransactionType.EXPENSE, "Food"),
            Transaction("3", date(2026, 10, 10), "Dinner C", Decimal("1100.00"), TransactionType.EXPENSE, "Food"),
            Transaction("4", date(2026, 10, 15), "Luxury Feast", Decimal("8500.00"), TransactionType.EXPENSE, "Food"),
        ]
        flags = self.detector.detect_anomalies(txns)
        spike_flags = [f for f in flags if f.flag_type == "CATEGORY_SPENDING_SPIKE"]
        self.assertEqual(len(spike_flags), 1)
        self.assertIn("higher than your average", spike_flags[0].explanation)

    def test_runway_projection_breach(self):
        starting_balance = Decimal("10000.00")
        threshold_limit = Decimal("5000.00")
        obligations = [
            (date(2026, 11, 5), Decimal("4000.00"), "Rent"),
            (date(2026, 11, 10), Decimal("3000.00"), "Loan EMI"),
        ]
        projection = self.detector.project_cash_flow_runway(
            starting_balance=starting_balance,
            threshold_limit=threshold_limit,
            upcoming_obligations=obligations,
            average_daily_discretionary=Decimal("100.00"),
            days_to_project=15,
            start_from_date=date(2026, 11, 1)
        )
        self.assertTrue(projection.will_breach_threshold)
        self.assertIsNotNone(projection.breach_date)
        self.assertIn("WARNING", projection.assumptions_explained)


if __name__ == "__main__":
    unittest.main()
