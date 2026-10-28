"""
analyzer/views.py
Web views for the FinSentry Safe-to-Spend (STS) web application.
"""

from datetime import date
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpRequest, HttpResponse

from core.sts import SafeToSpendCalculator
from analyzer.models import UserFinancialProfile, DailySpendEntry
from analyzer.forms import RegisterForm, ProfileSetupForm, DailySpendForm


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        u = request.POST.get("username", "").strip()
        p = request.POST.get("password", "").strip()
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "auth/login.html")


def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()
            # Initialize default financial profile
            UserFinancialProfile.objects.create(user=user)
            login(request, user)
            messages.success(request, f"Account created successfully! Welcome, {user.username}!")
            return redirect("profile_setup")
    else:
        form = RegisterForm()

    return render(request, "auth/register.html", {"form": form})


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")


@login_required(login_url="login")
def dashboard_view(request: HttpRequest) -> HttpResponse:
    profile, _ = UserFinancialProfile.objects.get_or_create(user=request.user)

    # 1. Compute Safe-To-Spend
    sts = SafeToSpendCalculator.compute_sts(
        available_balance=profile.available_balance,
        rent_amount=profile.rent_amount,
        rent_is_paid=profile.rent_is_paid,
        emi_amount=profile.emi_amount,
        emi_is_paid=profile.emi_is_paid,
        emergency_alloc=profile.emergency_pool,
        savings_alloc=profile.savings_pool,
        goal_contribution=profile.goal_monthly_contribution,
        salary_day=profile.salary_day,
        reference_date=date.today(),
    )

    # 2. Today's recorded expenses
    today = date.today()
    todays_spends = DailySpendEntry.objects.filter(user=request.user, date=today)
    spent_today = sum((s.amount for s in todays_spends), Decimal("0.00"))
    remaining_today = max(Decimal("0.00"), sts.daily_sts - spent_today)

    # 3. Handle 'Check Before You Buy' Simulator
    simulation_result = None
    if request.method == "POST" and "check_buy" in request.POST:
        cost_str = request.POST.get("item_cost", "0").strip()
        item_name = request.POST.get("item_name", "Desired Purchase").strip()
        try:
            cost = Decimal(cost_str)
            simulation_result = SafeToSpendCalculator.check_before_you_buy(sts, cost)
            simulation_result["item_name"] = item_name
            simulation_result["item_cost"] = cost
        except Exception as e:
            messages.error(request, f"Invalid price amount: {e}")

    recent_spends = DailySpendEntry.objects.filter(user=request.user)[:10]

    context = {
        "profile": profile,
        "sts": sts,
        "spent_today": spent_today,
        "remaining_today": remaining_today,
        "todays_spends": todays_spends,
        "recent_spends": recent_spends,
        "simulation": simulation_result,
        "spend_form": DailySpendForm(),
    }
    return render(request, "dashboard.html", context)


@login_required(login_url="login")
def profile_setup_view(request: HttpRequest) -> HttpResponse:
    profile, _ = UserFinancialProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileSetupForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Financial credentials & allocations saved successfully!")
            return redirect("dashboard")
    else:
        form = ProfileSetupForm(instance=profile)

    return render(request, "profile_setup.html", {"form": form})


@login_required(login_url="login")
def log_spend_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = DailySpendForm(request.POST)
        if form.is_valid():
            spend = form.save(commit=False)
            spend.user = request.user
            spend.date = date.today()
            spend.save()

            # Deduct from user's live available balance
            profile = request.user.profile
            profile.available_balance = max(Decimal("0.00"), profile.available_balance - spend.amount)
            profile.save()

            messages.success(request, f"Logged expense of ₹{spend.amount:.2f} for '{spend.description}'.")
    return redirect("dashboard")


@login_required(login_url="login")
def toggle_obligation_view(request: HttpRequest, bill_type: str) -> HttpResponse:
    profile = request.user.profile
    if bill_type == "rent":
        profile.rent_is_paid = not profile.rent_is_paid
        profile.save()
        status = "Paid" if profile.rent_is_paid else "Unpaid"
        messages.info(request, f"Rent marked as {status}.")
    elif bill_type == "emi":
        profile.emi_is_paid = not profile.emi_is_paid
        profile.save()
        status = "Paid" if profile.emi_is_paid else "Unpaid"
        messages.info(request, f"EMI marked as {status}.")
    return redirect("dashboard")
