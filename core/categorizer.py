"""
core/categorizer.py
Explainable Rule-Based Transaction Categorization Engine.

Features:
- Deterministic keyword and regex-based rule matching.
- Generates transparent, human-readable explanations for every assigned category.
- Supports user manual category overrides without losing history.
"""

import re
from typing import List, Dict, Tuple, Optional
from core.models import Transaction, TransactionType

DEFAULT_CATEGORY_RULES: List[Tuple[str, str, List[str]]] = [
    # (Category, Explanation Template, Keywords/Patterns)
    (
        "Income / Salary",
        "Matched income keyword '{keyword}'",
        ["salary", "freelance", "consulting", "payroll", "interest credit", "dividend", "bonus"]
    ),
    (
        "Utilities & Bills",
        "Matched utility billing keyword '{keyword}'",
        ["electricity", "water bill", "wifi", "internet", "broadband", "mobile recharge", "gas bill"]
    ),
    (
        "Groceries & Essentials",
        "Matched grocery store keyword '{keyword}'",
        ["supermarket", "groceries", "grocery", "mart", "milk", "vegetables", "bigbasket", "blinkit", "zepto"]
    ),
    (
        "Food & Dining",
        "Matched dining or restaurant keyword '{keyword}'",
        ["restaurant", "dinner", "lunch", "cafe", "coffee", "swiggy", "zomato", "mcdonald", "starbucks", "burger"]
    ),
    (
        "Entertainment & Subscriptions",
        "Matched digital subscription keyword '{keyword}'",
        ["netflix", "spotify", "prime", "hotstar", "youtube", "disney", "hulu", "playstation", "cinema"]
    ),
    (
        "Transport & Travel",
        "Matched transit/ride service keyword '{keyword}'",
        ["uber", "ola", "metro", "fuel", "petrol", "diesel", "flight", "irctc", "railway", "taxi"]
    ),
    (
        "Investments & Savings",
        "Matched investment instrument keyword '{keyword}'",
        ["sip", "mutual fund", "zerodha", "groww", "stock", "etf", "deposit", "ppf", "nps"]
    ),
    (
        "Shopping & Electronics",
        "Matched retail/e-commerce keyword '{keyword}'",
        ["amazon", "flipkart", "electronics", "myntra", "clothing", "shoes", "retail"]
    ),
    (
        "Health & Fitness",
        "Matched health or wellness keyword '{keyword}'",
        ["gym", "fitness", "pharmacy", "medicine", "hospital", "clinic", "lab", "doctor"]
    ),
    (
        "Cash & ATM",
        "Matched cash withdrawal pattern '{keyword}'",
        ["atm", "cash withdrawal", "atm cash", "self withdrawal"]
    ),
]


class TransactionCategorizer:
    """Assigns categories using documented, explainable rules."""

    def __init__(self, custom_rules: Optional[List[Tuple[str, str, List[str]]]] = None):
        self.rules = custom_rules if custom_rules is not None else DEFAULT_CATEGORY_RULES

    def categorize_transaction(self, txn: Transaction) -> Transaction:
        """Assigns category and category_reason to a single transaction."""
        desc_lower = txn.description.lower().strip()

        # Check rules in priority order
        for category, template, keywords in self.rules:
            for kw in keywords:
                # Use word boundary or substring match
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, desc_lower) or kw in desc_lower:
                    txn.category = category
                    txn.category_reason = template.format(keyword=kw)
                    return txn

        # Fallback category
        if txn.type == TransactionType.INCOME:
            txn.category = "Other Income"
            txn.category_reason = "No specific keyword matched; classified as Other Income by transaction type."
        else:
            txn.category = "Miscellaneous"
            txn.category_reason = "No rule matched the description. Classified as Miscellaneous for manual review."

        return txn

    def categorize_all(self, transactions: List[Transaction]) -> List[Transaction]:
        """Categorizes an entire batch of transactions in place."""
        for txn in transactions:
            self.categorize_transaction(txn)
        return transactions

    def apply_user_override(self, txn: Transaction, new_category: str, note: str = "") -> Transaction:
        """Allows a user to correct a category, recording transparency."""
        old_category = txn.category
        txn.category = new_category.strip()
        explanation = f"User override: changed from '{old_category}' to '{txn.category}'"
        if note:
            explanation += f" (Note: {note})"
        txn.category_reason = explanation
        return txn
