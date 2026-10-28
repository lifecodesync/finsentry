"""
analyzer/forms.py
Form definitions for user authentication, financial setup, and expense logging.
"""

from decimal import Decimal
from django import forms
from django.contrib.auth.models import User
from analyzer.models import UserFinancialProfile, DailySpendEntry


class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm", "placeholder": "Create a strong password"}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm", "placeholder": "Confirm password"}))

    class Meta:
        model = User
        fields = ["username", "email"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm", "placeholder": "Enter username"}),
            "email": forms.EmailInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm", "placeholder": "name@example.com"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password")
        p2 = cleaned_data.get("confirm_password")
        if p1 and p2 and p1 != p2:
            self.add_error("confirm_password", "Passwords do not match!")
        return cleaned_data


class ProfileSetupForm(forms.ModelForm):
    class Meta:
        model = UserFinancialProfile
        fields = [
            "monthly_salary",
            "salary_day",
            "available_balance",
            "rent_amount",
            "rent_is_paid",
            "emi_amount",
            "emi_is_paid",
            "emergency_pool",
            "savings_pool",
            "goal_name",
            "goal_target",
            "goal_monthly_contribution",
        ]
        widgets = {
            "monthly_salary": forms.NumberInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm font-semibold", "step": "0.01"}),
            "salary_day": forms.NumberInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm font-semibold", "min": 1, "max": 28}),
            "available_balance": forms.NumberInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm font-semibold text-indigo-700", "step": "0.01"}),
            "rent_amount": forms.NumberInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm", "step": "0.01"}),
            "rent_is_paid": forms.CheckboxInput(attrs={"class": "w-4 h-4 text-indigo-600 rounded"}),
            "emi_amount": forms.NumberInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm", "step": "0.01"}),
            "emi_is_paid": forms.CheckboxInput(attrs={"class": "w-4 h-4 text-indigo-600 rounded"}),
            "emergency_pool": forms.NumberInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm", "step": "0.01"}),
            "savings_pool": forms.NumberInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm", "step": "0.01"}),
            "goal_name": forms.TextInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm"}),
            "goal_target": forms.NumberInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm", "step": "0.01"}),
            "goal_monthly_contribution": forms.NumberInput(attrs={"class": "w-full border rounded-lg p-2.5 text-sm", "step": "0.01"}),
        }


class DailySpendForm(forms.ModelForm):
    class Meta:
        model = DailySpendEntry
        fields = ["description", "amount"]
        widgets = {
            "description": forms.TextInput(attrs={"class": "w-full border border-slate-300 rounded-lg p-2 text-sm", "placeholder": "e.g. Lunch with friends, Cab ride"}),
            "amount": forms.NumberInput(attrs={"class": "w-full border border-slate-300 rounded-lg p-2 text-sm font-semibold", "placeholder": "Amount (₹)", "step": "0.01"}),
        }
