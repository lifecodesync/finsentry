"""
analyzer/models.py
Database models for FinSentry SQLite persistence.
"""

from django.db import models


class StoredTransaction(models.Model):
    txn_id = models.CharField(max_length=64, unique=True, db_index=True)
    date = models.DateField(db_index=True)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=16, choices=[("INCOME", "Income"), ("EXPENSE", "Expense")])
    category = models.CharField(max_length=100, default="Uncategorized")
    category_reason = models.TextField(blank=True, default="")
    is_duplicate = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date} | {self.description} | {self.type} {self.amount}"


class StoredAnomalyFlag(models.Model):
    flag_id = models.CharField(max_length=64, unique=True)
    transaction = models.ForeignKey(StoredTransaction, on_delete=models.CASCADE, related_name="flags")
    flag_type = models.CharField(max_length=64)
    severity = models.CharField(max_length=16, choices=[("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High")])
    explanation = models.TextField()
    suggested_action = models.TextField()
    is_dismissed = models.BooleanField(default=False)
    dismissal_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_dismissed", "-created_at"]

    def __str__(self):
        return f"{self.flag_type} ({self.severity}) on {self.transaction.txn_id}"


class AppSettings(models.Model):
    starting_balance = models.DecimalField(max_digits=12, decimal_places=2, default=50000.00)
    threshold_limit = models.DecimalField(max_digits=12, decimal_places=2, default=10000.00)
    baseline_spike_multiplier = models.FloatField(default=2.5)
    daily_discretionary_burn = models.DecimalField(max_digits=10, decimal_places=2, default=200.00)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
