"""
seed_sample_data.py
Populates the FinSentry SQLite database using data/sample_transactions.csv.
"""

import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from core.parser import CSVTransactionParser
from core.categorizer import TransactionCategorizer
from core.detector import RiskAndAnomalyDetector
from analyzer.models import StoredTransaction, StoredAnomalyFlag, AppSettings


def run():
    csv_path = os.path.join(os.path.dirname(__file__), "data", "sample_transactions.csv")
    print(f"Reading synthetic dataset from: {csv_path}")

    parser = CSVTransactionParser(check_duplicates=True)
    result = parser.parse_file(csv_path)

    categorizer = TransactionCategorizer()
    categorizer.categorize_all(result.transactions)

    settings = AppSettings.get_settings()
    detector = RiskAndAnomalyDetector(baseline_spike_multiplier=settings.baseline_spike_multiplier)
    flags = detector.detect_anomalies(result.transactions)

    # Clear previous test data
    StoredTransaction.objects.all().delete()
    StoredAnomalyFlag.objects.all().delete()

    created_txns = {}
    for t in result.transactions:
        obj = StoredTransaction.objects.create(
            txn_id=t.id,
            date=t.date,
            description=t.description,
            amount=t.amount,
            type=t.type.value,
            category=t.category,
            category_reason=t.category_reason,
            is_duplicate=t.is_duplicate,
        )
        created_txns[t.id] = obj

    for f in flags:
        target_obj = created_txns.get(f.transaction_id)
        if target_obj:
            StoredAnomalyFlag.objects.create(
                flag_id=f.flag_id,
                transaction=target_obj,
                flag_type=f.flag_type,
                severity=f.severity,
                explanation=f.explanation,
                suggested_action=f.suggested_action,
            )

    print("\n[SUCCESS] Database Seeding Complete:")
    print(f"  - Total CSV Rows Read: {result.total_rows_read}")
    print(f"  - Valid Transactions Saved: {len(result.transactions)}")
    print(f"  - Duplicates Flagged: {result.duplicate_count}")
    print(f"  - Dirty Rows Safely Isolated: {len(result.errors)}")
    print(f"  - Anomaly Flags Created: {len(flags)}")


if __name__ == "__main__":
    run()
