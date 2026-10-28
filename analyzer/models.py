"""
analyzer/models.py
Django models for FinSentry Safe-to-Spend (STS) web application.
"""

from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserFinancialProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    
    # Income & Cycle
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("60000.00"))
    salary_day = models.PositiveSmallIntegerField(default=1, help_text="Day of month salary credits (1-28)")

    # Real-time Liquidity
    available_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("35000.00"))

    # Fixed Obligations
    rent_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("12000.00"))
    rent_is_paid = models.BooleanField(default=False, help_text="Check if already paid for current salary cycle")

    emi_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("4500.00"))
    emi_is_paid = models.BooleanField(default=False, help_text="Check if already paid for current salary cycle")

    # Protected Reserves
    emergency_pool = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("5000.00"))
    savings_pool = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("3000.00"))

    # Active Financial Goal
    goal_name = models.CharField(max_length=120, default="Emergency Buffer / Upgrade")
    goal_target = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("40000.00"))
    goal_monthly_contribution = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("2500.00"))

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Financial Profile of {self.user.username}"


class DailySpendEntry(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="spends")
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.description} (₹{self.amount})"
