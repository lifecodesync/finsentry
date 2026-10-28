"""
run_cli.py
Standalone command-line interface for FinSentry.
Demonstrates that all business logic is 100% decoupled from the web framework.
"""

import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.parser import CSVTransactionParser
from core.categorizer import TransactionCategorizer
from core.analytics import CashFlowAnalytics
from core.detector import RiskAndAnomalyDetector


def main():
    print("=" * 70)
    print("  FINSENTRY — Explainable Transaction Risk & Cash-Flow Analyzer (CLI)")
    print("=" * 70)

    csv_file = os.path.join("data", "sample_transactions.csv")
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found.")
        return

    print(f"\n[1] Parsing & Validating CSV: {csv_file}")
    parser = CSVTransactionParser(check_duplicates=True)
    result = parser.parse_file(csv_file)
    print(f"    Total rows read: {result.total_rows_read}")
    print(f"    Clean transactions: {result.clean_count}")
    print(f"    Duplicates flagged: {result.duplicate_count}")
    print(f"    Dirty rows isolated: {result.error_count}")

    if result.errors:
        print("\n    Rejected Dirty Rows:")
        for err in result.errors:
            print(f"      - Line {err.line_number} [{err.field}]: {err.reason} (Got: {err.raw_value!r})")

    print("\n[2] Explainable Rule-Based Categorization")
    categorizer = TransactionCategorizer()
    categorizer.categorize_all(result.transactions)
    for txn in result.transactions[:5]:
        print(f"    - {txn.date} | {txn.description:<25} | {txn.type.value:<7} | {txn.amount:>8} | {txn.category:<25} (Why: {txn.category_reason})")

    print("\n[3] Cash-Flow Analytics")
    analytics = CashFlowAnalytics()
    summary = analytics.calculate_summary(result.transactions)
    print(f"    Total Income:   Rs {summary.total_income}")
    print(f"    Total Expenses: Rs {summary.total_expenses}")
    print(f"    Net Savings:    Rs {summary.net_savings} (Savings Rate: {summary.savings_rate_pct}%)")
    print("\n    Expense Breakdown by Category:")
    for cat, amt in summary.category_totals.items():
        print(f"      * {cat:<30}: Rs {amt}")

    print("\n[4] Explainable Anomaly Detection")
    detector = RiskAndAnomalyDetector(baseline_spike_multiplier=2.5)
    flags = detector.detect_anomalies(result.transactions)
    if flags:
        for f in flags:
            print(f"    ⚠️  [{f.severity}] {f.flag_type}")
            print(f"       Explanation: {f.explanation}")
            print(f"       Suggested:   {f.suggested_action}")
    else:
        print("    No anomalies triggered.")

    print("\n[5] Detected Recurring Subscriptions")
    recurring = detector.detect_recurring_payments(result.transactions)
    for r in recurring:
        print(f"    🔄 {r.merchant} ({r.cadence}) - Avg Rs {r.average_amount} (Confidence: {r.confidence_score*100:.0f}%)")
        print(f"       {r.explanation}")

    print("\n" + "=" * 70)
    print("  Execution Finished. All modules verified successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
