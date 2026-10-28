"""
core/analytics.py
Cash-Flow Analytics Engine using Pandas & Matplotlib.

Features:
- Total income, total expenses, net savings, and savings rate calculation.
- Monthly cash-flow aggregation and spending breakdowns by category.
- Clean distinction between Cash Flow (delta over period) and Bank Balance (point-in-time asset).
- High-resolution chart generator saving PNG charts for the web dashboard.
"""

from decimal import Decimal
from typing import List, Dict, Any, Tuple
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend for web/server use
import matplotlib.pyplot as plt
import io
import base64

from core.models import Transaction, TransactionType, CashFlowSummary


class CashFlowAnalytics:
    """Calculates cash-flow aggregates and category distributions."""

    @staticmethod
    def transactions_to_dataframe(transactions: List[Transaction]) -> pd.DataFrame:
        """Converts domain Transaction objects to a Pandas DataFrame."""
        if not transactions:
            return pd.DataFrame(
                columns=["id", "date", "description", "amount", "type", "category", "is_duplicate"]
            )

        data = [
            {
                "id": t.id,
                "date": pd.to_datetime(t.date),
                "month": t.date.strftime("%Y-%m"),
                "description": t.description,
                "amount": float(t.amount),
                "type": t.type.value,
                "category": t.category,
                "is_duplicate": t.is_duplicate,
            }
            for t in transactions
        ]
        return pd.DataFrame(data)

    def calculate_summary(self, transactions: List[Transaction]) -> CashFlowSummary:
        """Computes total income, expenses, net savings, and category aggregates."""
        df = self.transactions_to_dataframe(transactions)

        if df.empty:
            return CashFlowSummary(
                total_income=Decimal("0.00"),
                total_expenses=Decimal("0.00"),
                net_savings=Decimal("0.00"),
                savings_rate_pct=0.0,
                category_totals={},
                monthly_trend={},
            )

        # Exclude flagged duplicates from top-line financial totals to prevent double-counting
        active_df = df[~df["is_duplicate"]]

        income_df = active_df[active_df["type"] == TransactionType.INCOME.value]
        expense_df = active_df[active_df["type"] == TransactionType.EXPENSE.value]

        total_income = Decimal(str(round(income_df["amount"].sum(), 2)))
        total_expenses = Decimal(str(round(expense_df["amount"].sum(), 2)))
        net_savings = total_income - total_expenses

        savings_rate = 0.0
        if total_income > Decimal("0"):
            savings_rate = float(round((net_savings / total_income) * 100, 2))

        # Category totals (for expenses)
        cat_group = expense_df.groupby("category")["amount"].sum().to_dict()
        category_totals = {cat: Decimal(str(round(amt, 2))) for cat, amt in cat_group.items()}

        # Monthly trends
        monthly_trend: Dict[str, Dict[str, Decimal]] = {}
        all_months = sorted(active_df["month"].unique())
        for m in all_months:
            m_df = active_df[active_df["month"] == m]
            m_inc = m_df[m_df["type"] == TransactionType.INCOME.value]["amount"].sum()
            m_exp = m_df[m_df["type"] == TransactionType.EXPENSE.value]["amount"].sum()
            monthly_trend[m] = {
                "income": Decimal(str(round(m_inc, 2))),
                "expense": Decimal(str(round(m_exp, 2))),
                "net": Decimal(str(round(m_inc - m_exp, 2))),
            }

        return CashFlowSummary(
            total_income=total_income,
            total_expenses=total_expenses,
            net_savings=net_savings,
            savings_rate_pct=savings_rate,
            category_totals=category_totals,
            monthly_trend=monthly_trend,
        )

    def generate_category_pie_chart_base64(self, category_totals: Dict[str, Decimal]) -> str:
        """Renders an expense category breakdown pie chart encoded as base64 PNG."""
        if not category_totals:
            return ""

        labels = list(category_totals.keys())
        values = [float(v) for v in category_totals.values()]

        fig, ax = plt.subplots(figsize=(6, 4.5), dpi=100)
        colors = plt.cm.tab20.colors[:len(labels)]
        
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            textprops=dict(color="#222222", fontsize=9)
        )
        for at in autotexts:
            at.set_fontsize(8)

        ax.set_title("Expense Distribution by Category", fontsize=12, fontweight="bold", pad=12)
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight")
        plt.close(fig)
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def generate_monthly_bar_chart_base64(self, monthly_trend: Dict[str, Dict[str, Decimal]]) -> str:
        """Renders monthly income vs expenses bar chart encoded as base64 PNG."""
        if not monthly_trend:
            return ""

        months = list(monthly_trend.keys())
        incomes = [float(monthly_trend[m]["income"]) for m in months]
        expenses = [float(monthly_trend[m]["expense"]) for m in months]

        fig, ax = plt.subplots(figsize=(7, 4), dpi=100)
        import numpy as np
        x = np.arange(len(months))
        width = 0.35

        ax.bar(x - width/2, incomes, width, label="Income", color="#10B981")
        ax.bar(x + width/2, expenses, width, label="Expense", color="#EF4444")

        ax.set_xticks(x)
        ax.set_xticklabels(months, fontsize=9)
        ax.set_ylabel("Amount (Currency Units)", fontsize=10)
        ax.set_title("Monthly Cash Inflows vs Outflows", fontsize=12, fontweight="bold", pad=12)
        ax.legend()
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight")
        plt.close(fig)
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @staticmethod
    def get_cash_flow_vs_balance_explanation() -> Dict[str, str]:
        """Provides an authoritative domain explanation for college viva and UI display."""
        return {
            "title": "Cash Flow vs. Bank Balance",
            "cash_flow": (
                "Cash Flow is the rate of net movement: (Total Inflow - Total Outflow) over a specified period. "
                "It indicates whether you lived within your means during that calendar window."
            ),
            "bank_balance": (
                "Bank Balance is an instantaneous point-in-time snapshot of liquid wealth: "
                "Current Balance = Starting Balance + Accumulated Net Cash Flow. "
                "A user can have positive cash flow this month while still having a low or critical bank balance."
            ),
            "takeaway": (
                "FinSentry tracks both: Cash flow measures behavioral surplus/deficit; runway alerts "
                "protect the actual liquid bank balance threshold."
            )
        }
