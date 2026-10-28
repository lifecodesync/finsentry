"""
core/models.py
Domain models and data structures for FinSentry.
Built using standard Python dataclasses for immutability and testability.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List


class TransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"

    @classmethod
    def from_string(cls, val: str) -> "TransactionType":
        cleaned = val.strip().upper()
        if cleaned in ("INCOME", "CREDIT", "CR"):
            return cls.INCOME
        if cleaned in ("EXPENSE", "DEBIT", "DR"):
            return cls.EXPENSE
        raise ValueError(f"Unknown transaction type: '{val}'. Expected 'INCOME' or 'EXPENSE'.")


@dataclass
class Transaction:
    """Represents a validated financial transaction."""
    id: str
    date: date
    description: str
    amount: Decimal
    type: TransactionType
    category: str = "Uncategorized"
    category_reason: str = "Awaiting categorization"
    is_duplicate: bool = False
    line_number: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "description": self.description,
            "amount": float(self.amount),
            "type": self.type.value,
            "category": self.category,
            "category_reason": self.category_reason,
            "is_duplicate": self.is_duplicate,
            "line_number": self.line_number,
        }


@dataclass
class AnomalyFlag:
    """Represents an explainable risk/anomaly indicator.
    
    NOTE: A flag is NEVER proof of fraud; it is an indicator for review.
    """
    flag_id: str
    transaction_id: str
    flag_type: str  # DUPLICATE, BASELINE_SPIKE, UNUSUAL_VELOCITY
    severity: str   # LOW, MEDIUM, HIGH
    explanation: str
    suggested_action: str
    is_dismissed: bool = False
    dismissal_note: Optional[str] = None


@dataclass
class RecurringPattern:
    """Represents a detected recurring subscription or bill."""
    merchant: str
    cadence: str  # MONTHLY, WEEKLY, UNCERTAIN
    average_amount: Decimal
    confidence_score: float  # 0.0 to 1.0 (0% to 100%)
    last_seen_date: date
    next_expected_date: Optional[date]
    explanation: str


@dataclass
class CashFlowSummary:
    """High-level summary of cash movements."""
    total_income: Decimal
    total_expenses: Decimal
    net_savings: Decimal
    savings_rate_pct: float
    category_totals: Dict[str, Decimal] = field(default_factory=dict)
    monthly_trend: Dict[str, Dict[str, Decimal]] = field(default_factory=dict)


@dataclass
class RunwayProjection:
    """Forward-looking projection to warn about potential cash shortfalls."""
    starting_balance: Decimal
    threshold_limit: Decimal
    projected_lowest_balance: Decimal
    days_analyzed: int
    will_breach_threshold: bool
    breach_date: Optional[date]
    assumptions_explained: str
    disclaimer: str = (
        "Notice: This is an automated mathematical projection based on past transactions "
        "and entered obligations. It is NOT financial advice."
    )
