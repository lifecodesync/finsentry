"""
core/sts.py
Core Safe-to-Spend (STS) Mathematical Engine.
Faithfully ported from Livia (D:\\livia\\lib\\formula\\sts_calculator.dart).

Formula:
1. after_fixed = available_balance - unpaid_rent - unpaid_emi
2. spendable_balance = after_fixed - emergency_alloc - savings_alloc - goal_contribution
3. days_remaining = max(1, days_until_salary)
4. daily_sts = max(0, spendable_balance / days_remaining)
5. weekly_sts = min(spendable_balance, daily_sts * 7)
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import calendar


@dataclass
class STSResult:
    available_balance: Decimal
    unpaid_rent: Decimal
    unpaid_emi: Decimal
    after_fixed: Decimal
    emergency_alloc: Decimal
    savings_alloc: Decimal
    goal_contribution: Decimal
    spendable_balance: Decimal
    days_remaining: int
    daily_sts: Decimal
    weekly_sts: Decimal
    status: str  # "HEALTHY", "TIGHT", "DEPLETED"
    status_message: str


class SafeToSpendCalculator:
    """Computes exact daily and weekly spendable ceilings based on liquidity and cycle math."""

    @staticmethod
    def calculate_days_until_salary(salary_day: int, reference_date: date = None) -> int:
        """Calculates exact calendar days remaining until the next salary credit day."""
        today = reference_date if reference_date else date.today()
        
        # Clamp salary_day between 1 and 28 to prevent leap/month edge cases
        salary_day = max(1, min(28, salary_day))

        # Check if salary day is still ahead in current month
        if today.day < salary_day:
            target_salary_date = date(today.year, today.month, salary_day)
        else:
            # Salary day in current month has passed; target next month's salary day
            if today.month == 12:
                target_salary_date = date(today.year + 1, 1, salary_day)
            else:
                target_salary_date = date(today.year, today.month + 1, salary_day)

        days_left = (target_salary_date - today).days
        return max(1, days_left)

    @classmethod
    def compute_sts(
        cls,
        available_balance: Decimal,
        rent_amount: Decimal,
        rent_is_paid: bool,
        emi_amount: Decimal,
        emi_is_paid: bool,
        emergency_alloc: Decimal,
        savings_alloc: Decimal,
        goal_contribution: Decimal,
        salary_day: int = 1,
        reference_date: date = None,
    ) -> STSResult:
        """Executes the exact Livia Safe-To-Spend formula with fixed-point precision."""
        
        # Step 1: Fixed Obligations (Only deduct if NOT yet paid)
        unpaid_rent = Decimal("0.00") if rent_is_paid else max(Decimal("0.00"), rent_amount)
        unpaid_emi = Decimal("0.00") if emi_is_paid else max(Decimal("0.00"), emi_amount)
        after_fixed = available_balance - unpaid_rent - unpaid_emi

        # Step 2: Protected Pools
        protected_total = (
            max(Decimal("0.00"), emergency_alloc) +
            max(Decimal("0.00"), savings_alloc) +
            max(Decimal("0.00"), goal_contribution)
        )
        spendable_balance = after_fixed - protected_total

        # Step 3: Days remaining until next salary
        days_remaining = cls.calculate_days_until_salary(salary_day, reference_date)

        # Step 4: Daily & Weekly Safe-to-Spend
        if spendable_balance <= Decimal("0.00"):
            daily_sts = Decimal("0.00")
            weekly_sts = Decimal("0.00")
            status = "DEPLETED"
            status_message = "Your spendable balance is depleted! Any expense will drain your Rent, EMI, or Emergency reserves."
        else:
            daily_sts = (spendable_balance / Decimal(days_remaining)).quantize(Decimal("0.01"))
            raw_weekly = (daily_sts * Decimal(7)).quantize(Decimal("0.01"))
            weekly_sts = min(raw_weekly, spendable_balance)

            if daily_sts >= Decimal("500.00"):
                status = "HEALTHY"
                status_message = "Your finances are well-shielded! You can safely spend within your daily ceiling."
            else:
                status = "TIGHT"
                status_message = "Your daily budget is tight. Monitor discretionary spending until salary arrives."

        return STSResult(
            available_balance=available_balance,
            unpaid_rent=unpaid_rent,
            unpaid_emi=unpaid_emi,
            after_fixed=after_fixed,
            emergency_alloc=emergency_alloc,
            savings_alloc=savings_alloc,
            goal_contribution=goal_contribution,
            spendable_balance=spendable_balance,
            days_remaining=days_remaining,
            daily_sts=daily_sts,
            weekly_sts=weekly_sts,
            status=status,
            status_message=status_message,
        )

    @classmethod
    def check_before_you_buy(
        cls,
        current_sts: STSResult,
        item_cost: Decimal,
    ) -> dict:
        """Simulates buying an item right now and explains the consequence on your daily budget."""
        cost = max(Decimal("0.00"), item_cost)
        new_spendable = current_sts.spendable_balance - cost

        if cost <= Decimal("0.00"):
            return {
                "can_afford": True,
                "impact": "NO_IMPACT",
                "explanation": "Please enter a valid item price greater than 0.",
                "new_daily_sts": current_sts.daily_sts,
            }

        if new_spendable < Decimal("0.00"):
            shortfall = abs(new_spendable)
            return {
                "can_afford": False,
                "impact": "RESERVE_BREACH",
                "explanation": (
                    f"⛔ Cannot afford! Purchasing this item will completely wipe out your spendable pool "
                    f"and invade your protected reserves (Rent/EMI/Emergency) by ₹{shortfall:.2f}."
                ),
                "new_daily_sts": Decimal("0.00"),
            }

        new_daily = (new_spendable / Decimal(current_sts.days_remaining)).quantize(Decimal("0.01"))
        drop_in_daily = current_sts.daily_sts - new_daily

        return {
            "can_afford": True,
            "impact": "SAFE_WITH_DROP",
            "explanation": (
                f"✅ You can afford this! After buying, your daily safe-to-spend will adjust from "
                f"₹{current_sts.daily_sts:.2f} to ₹{new_daily:.2f} for the remaining {current_sts.days_remaining} days."
            ),
            "new_daily_sts": new_daily,
            "daily_drop": drop_in_daily,
        }
