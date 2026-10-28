"""
core/detector.py
Explainable Anomaly Detection, Recurring Payments & Runway Projections.

Core Principles:
1. Explainability: Every flag includes the exact mathematical trigger and rationale.
2. Humility: Flags are indicators requiring user review, NEVER accusations of fraud.
3. Dismissability: Users can dismiss flags with documented reasons.
4. Transparency: Clear recurring confidence metrics and disclaimer-backed runway projections.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
import statistics
from typing import List, Dict, Optional, Tuple
import uuid

from core.models import (
    Transaction,
    TransactionType,
    AnomalyFlag,
    RecurringPattern,
    RunwayProjection,
)


class RiskAndAnomalyDetector:
    """Detects explainable transaction anomalies and recurring subscriptions."""

    def __init__(
        self,
        baseline_spike_multiplier: float = 2.5,
        min_baseline_sample_size: int = 3,
        duplicate_window_days: int = 2,
    ):
        self.spike_multiplier = baseline_spike_multiplier
        self.min_sample_size = min_baseline_sample_size
        self.duplicate_window_days = duplicate_window_days

    # -------------------------------------------------------------------------
    # Feature D: Explainable Anomaly Detection
    # -------------------------------------------------------------------------
    def detect_anomalies(self, transactions: List[Transaction]) -> List[AnomalyFlag]:
        """Runs transparent, rule-based anomaly scans across transactions."""
        flags: List[AnomalyFlag] = []

        # Filter active expenses
        expenses = [t for t in transactions if t.type == TransactionType.EXPENSE]
        if not expenses:
            return flags

        # 1. Exact or near-duplicate detection
        flags.extend(self._check_duplicate_anomalies(expenses))

        # 2. Category baseline spike detection
        flags.extend(self._check_category_baseline_spikes(expenses))

        # 3. Overall outlier spike detection (global baseline)
        flags.extend(self._check_global_outliers(expenses))

        return flags

    def _check_duplicate_anomalies(self, expenses: List[Transaction]) -> List[AnomalyFlag]:
        flags = []
        # Sort by description and date
        sorted_txns = sorted(expenses, key=lambda x: (x.description.lower(), x.date))

        for i in range(len(sorted_txns) - 1):
            curr = sorted_txns[i]
            nxt = sorted_txns[i + 1]

            if curr.description.lower() == nxt.description.lower() and curr.amount == nxt.amount:
                delta_days = abs((nxt.date - curr.date).days)
                if delta_days <= self.duplicate_window_days:
                    flags.append(
                        AnomalyFlag(
                            flag_id=f"FLAG-DUP-{uuid.uuid4().hex[:6].upper()}",
                            transaction_id=nxt.id,
                            flag_type="POTENTIAL_DUPLICATE",
                            severity="HIGH" if delta_days == 0 else "MEDIUM",
                            explanation=(
                                f"Transaction on {nxt.date} for {nxt.amount} matches prior charge "
                                f"'{curr.description}' on {curr.date} ({delta_days} day(s) apart). "
                                "Possible accidental double-billing."
                            ),
                            suggested_action="Review bank statement to ensure you were not charged twice."
                        )
                    )
        return flags

    def _check_category_baseline_spikes(self, expenses: List[Transaction]) -> List[AnomalyFlag]:
        flags = []
        by_category = defaultdict(list)
        for t in expenses:
            by_category[t.category].append(t)

        for category, txns in by_category.items():
            if len(txns) < self.min_sample_size:
                continue

            amounts = [float(t.amount) for t in txns]
            mean_val = statistics.mean(amounts)
            stdev_val = statistics.stdev(amounts) if len(amounts) > 1 else 0.0

            # Threshold: Mean + (Multiplier * standard deviation) or multiplier * mean
            threshold = mean_val * self.spike_multiplier

            for t in txns:
                amt_float = float(t.amount)
                if amt_float > threshold and amt_float > 1000.0:  # Ignore micro-amounts
                    ratio = round(amt_float / mean_val, 1)
                    flags.append(
                        AnomalyFlag(
                            flag_id=f"FLAG-SPIKE-{uuid.uuid4().hex[:6].upper()}",
                            transaction_id=t.id,
                            flag_type="CATEGORY_SPENDING_SPIKE",
                            severity="MEDIUM" if ratio < 4.0 else "HIGH",
                            explanation=(
                                f"Amount of {t.amount} is {ratio}x higher than your average '{category}' "
                                f"spend ({mean_val:.2f} across {len(txns)} transactions). "
                                f"Threshold is {threshold:.2f} ({self.spike_multiplier}x baseline)."
                            ),
                            suggested_action=f"Confirm this one-off '{category}' expense was intentional."
                        )
                    )
        return flags

    def _check_global_outliers(self, expenses: List[Transaction]) -> List[AnomalyFlag]:
        flags = []
        if len(expenses) < 5:
            return flags

        amounts = [float(t.amount) for t in expenses]
        sorted_amounts = sorted(amounts)
        p95_index = int(len(sorted_amounts) * 0.95)
        p95_threshold = sorted_amounts[p95_index]

        for t in expenses:
            amt = float(t.amount)
            # If greater than 95th percentile and exceeds 5000 units
            if amt > p95_threshold and amt >= 5000.0:
                flags.append(
                    AnomalyFlag(
                        flag_id=f"FLAG-OUTLIER-{uuid.uuid4().hex[:6].upper()}",
                        transaction_id=t.id,
                        flag_type="TOP_5_PERCENT_OUTLIER",
                        severity="LOW",
                        explanation=(
                            f"Amount {t.amount} places this transaction in your top 5% highest expenses "
                            f"(95th percentile cutoff: {p95_threshold:.2f})."
                        ),
                        suggested_action="Verify this high-value transaction against your budget."
                    )
                )
        return flags

    # -------------------------------------------------------------------------
    # Feature E: Recurring Payments Detection
    # -------------------------------------------------------------------------
    def detect_recurring_payments(self, transactions: List[Transaction]) -> List[RecurringPattern]:
        """Identifies repeating subscriptions and bills with transparent confidence scores."""
        patterns: List[RecurringPattern] = []

        # Group expenses by normalized merchant name
        merchant_groups = defaultdict(list)
        for t in transactions:
            if t.type == TransactionType.EXPENSE and not t.is_duplicate:
                norm_desc = self._normalize_merchant_name(t.description)
                merchant_groups[norm_desc].append(t)

        for merchant, txns in merchant_groups.items():
            if len(txns) < 2:
                continue

            # Sort chronologically
            sorted_txns = sorted(txns, key=lambda x: x.date)
            intervals = [
                (sorted_txns[i + 1].date - sorted_txns[i].date).days
                for i in range(len(sorted_txns) - 1)
            ]
            amounts = [t.amount for t in sorted_txns]
            avg_amount = sum(amounts) / Decimal(len(amounts))
            last_date = sorted_txns[-1].date

            avg_interval = statistics.mean(intervals)
            interval_variance = statistics.stdev(intervals) if len(intervals) > 1 else 0.0

            # Monthly subscription pattern: 27 to 33 days interval
            if 27 <= avg_interval <= 33 and interval_variance <= 5:
                confidence = 0.95 if len(txns) >= 3 else 0.75
                next_date = last_date + timedelta(days=30)
                patterns.append(
                    RecurringPattern(
                        merchant=merchant.title(),
                        cadence="MONTHLY",
                        average_amount=avg_amount.quantize(Decimal("0.01")),
                        confidence_score=confidence,
                        last_seen_date=last_date,
                        next_expected_date=next_date,
                        explanation=(
                            f"Detected {len(txns)} charges spaced ~{round(avg_interval)} days apart "
                            f"(average amount: {avg_amount:.2f}). Highly consistent monthly cycle."
                        )
                    )
                )

            # Weekly subscription pattern: 6 to 8 days interval
            elif 6 <= avg_interval <= 8 and interval_variance <= 2:
                confidence = 0.90 if len(txns) >= 3 else 0.70
                next_date = last_date + timedelta(days=7)
                patterns.append(
                    RecurringPattern(
                        merchant=merchant.title(),
                        cadence="WEEKLY",
                        average_amount=avg_amount.quantize(Decimal("0.01")),
                        confidence_score=confidence,
                        last_seen_date=last_date,
                        next_expected_date=next_date,
                        explanation=(
                            f"Detected {len(txns)} charges spaced ~{round(avg_interval)} days apart. "
                            "Consistent weekly billing pattern."
                        )
                    )
                )

            # Potential recurring with low consistency
            elif len(txns) >= 2 and avg_interval <= 45:
                patterns.append(
                    RecurringPattern(
                        merchant=merchant.title(),
                        cadence="UNCERTAIN",
                        average_amount=avg_amount.quantize(Decimal("0.01")),
                        confidence_score=0.45,
                        last_seen_date=last_date,
                        next_expected_date=last_date + timedelta(days=int(avg_interval)),
                        explanation=(
                            f"Seen {len(txns)} times with irregular spacing (~{round(avg_interval)} days). "
                            "Requires more history to confirm recurring schedule."
                        )
                    )
                )

        return patterns

    @staticmethod
    def _normalize_merchant_name(desc: str) -> str:
        """Strips common suffixes and order identifiers from descriptions."""
        cleaned = desc.lower().strip()
        # Remove common invoice prefixes/suffixes
        for prefix in ("order", "bill", "subscription", "trip", "ride"):
            cleaned = cleaned.replace(prefix, "")
        return " ".join(cleaned.split())

    # -------------------------------------------------------------------------
    # Feature F: Cash-Flow Runway & Low-Balance Warnings
    # -------------------------------------------------------------------------
    def project_cash_flow_runway(
        self,
        starting_balance: Decimal,
        threshold_limit: Decimal,
        upcoming_obligations: List[Tuple[date, Decimal, str]],
        average_daily_discretionary: Decimal = Decimal("150.00"),
        days_to_project: int = 30,
        start_from_date: Optional[date] = None
    ) -> RunwayProjection:
        """Projects daily balance forward and checks if balance dips below threshold."""
        current_date = start_from_date if start_from_date else date.today()
        running_balance = starting_balance
        lowest_balance = starting_balance
        breach_detected = False
        breach_date: Optional[date] = None

        # Map obligations by date
        obligation_map = defaultdict(list)
        for due_date, amt, desc in upcoming_obligations:
            obligation_map[due_date].append((amt, desc))

        for day_offset in range(1, days_to_project + 1):
            eval_date = current_date + timedelta(days=day_offset)

            # Deduct standard estimated daily burn
            running_balance -= average_daily_discretionary

            # Deduct scheduled obligations
            if eval_date in obligation_map:
                for amt, _ in obligation_map[eval_date]:
                    running_balance -= amt

            if running_balance < lowest_balance:
                lowest_balance = running_balance

            if running_balance < threshold_limit and not breach_detected:
                breach_detected = True
                breach_date = eval_date

        explanation = (
            f"Starting from {starting_balance:.2f}, factoring {average_daily_discretionary:.2f}/day "
            f"average discretionary spending plus {len(upcoming_obligations)} scheduled obligations. "
            f"Lowest estimated balance in {days_to_project} days is {lowest_balance:.2f}."
        )
        if breach_detected and breach_date:
            explanation += (
                f" WARNING: Balance is projected to drop below your threshold limit of "
                f"{threshold_limit:.2f} on {breach_date.strftime('%Y-%m-%d')}!"
            )
        else:
            explanation += f" Safe: Balance is projected to remain above your {threshold_limit:.2f} threshold."

        return RunwayProjection(
            starting_balance=starting_balance,
            threshold_limit=threshold_limit,
            projected_lowest_balance=lowest_balance,
            days_analyzed=days_to_project,
            will_breach_threshold=breach_detected,
            breach_date=breach_date,
            assumptions_explained=explanation
        )
