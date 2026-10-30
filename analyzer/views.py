"""
analyzer/views.py
Web views for the FinSentry Safe-to-Spend (STS) web application.
Faithfully ported from Livia's daily rollover, frozen daily rate, and overspend resolution logic.
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
    today = date.today()

    # Livia Daily Rollover: reset daily overspend absorption on a new calendar day
    if profile.last_spend_date != today:
        profile.overspend_absorbed_today = Decimal("0.00")
        profile.last_spend_date = today
        profile.save()

    # Get today's recorded discretionary expenses
    todays_spends = DailySpendEntry.objects.filter(user=request.user, date=today)
    spent_today = sum((s.amount for s in todays_spends), Decimal("0.00"))

    # LIVIA FROZEN DAILY CEILING PRINCIPLE:
    # Today's daily spending ceiling is computed from the balance at the START of today
    # (live available_balance + spent_today).
    # This prevents the double-deduction bug:
    # If today's budget is ₹800 and you spend ₹10, remaining budget drops by EXACTLY ₹10 to ₹790.
    starting_balance_today = profile.available_balance + spent_today

    sts = SafeToSpendCalculator.compute_sts(
        available_balance=starting_balance_today,
        rent_amount=profile.rent_amount,
        rent_is_paid=profile.rent_is_paid,
        emi_amount=profile.emi_amount,
        emi_is_paid=profile.emi_is_paid,
        emergency_alloc=profile.emergency_pool,
        savings_alloc=profile.savings_pool,
        goal_contribution=profile.goal_monthly_contribution,
        salary_day=profile.salary_day,
        reference_date=today,
    )

    # Effective today's budget: Frozen base STS + any pool unlocked today
    effective_today_budget = sts.daily_sts + profile.overspend_absorbed_today
    remaining_today = max(Decimal("0.00"), effective_today_budget - spent_today)
    
    # Overspend Detection
    uncovered_overspend = max(Decimal("0.00"), spent_today - effective_today_budget)
    has_overspend = uncovered_overspend > Decimal("0.00")

    # Percentage of today's budget spent
    spend_percent = 0
    if effective_today_budget > Decimal("0.00"):
        spend_percent = min(100, int((spent_today / effective_today_budget) * 100))
    elif spent_today > Decimal("0.00"):
        spend_percent = 100

    # Handle 'Check Before You Buy' Simulator (Persisted in session so it never vanishes)
    if request.method == "POST" and "check_buy" in request.POST:
        cost_str = request.POST.get("item_cost", "0").strip()
        item_name = request.POST.get("item_name", "Desired Purchase").strip()
        try:
            cost = Decimal(cost_str)
            sim_res = SafeToSpendCalculator.check_before_you_buy(sts, cost)
            sim_res["item_name"] = item_name
            sim_res["item_cost"] = str(cost)
            sim_res["new_daily_sts"] = str(sim_res["new_daily_sts"])
            if "daily_drop" in sim_res:
                sim_res["daily_drop"] = str(sim_res["daily_drop"])
            request.session["last_simulation"] = sim_res
        except Exception as e:
            messages.error(request, f"Invalid price amount: {e}")

    simulation_result = request.session.get("last_simulation")

    recent_spends = DailySpendEntry.objects.filter(user=request.user)[:10]

    context = {
        "profile": profile,
        "sts": sts,
        "spent_today": spent_today,
        "effective_today_budget": effective_today_budget,
        "remaining_today": remaining_today,
        "spend_percent": spend_percent,
        "uncovered_overspend": uncovered_overspend,
        "has_overspend": has_overspend,
        "todays_spends": todays_spends,
        "recent_spends": recent_spends,
        "simulation": simulation_result,
        "spend_form": DailySpendForm(),
    }
    return render(request, "dashboard.html", context)


@login_required(login_url="login")
def clear_simulation_view(request: HttpRequest) -> HttpResponse:
    if "last_simulation" in request.session:
        del request.session["last_simulation"]
    return redirect("dashboard")


@login_required(login_url="login")
def resolve_overspend_view(request: HttpRequest) -> HttpResponse:
    """Handles the exact Livia user-driven overspend resolution choice."""
    if request.method == "POST":
        choice = request.POST.get("choice", "").strip()
        profile = request.user.profile
        today = date.today()

        todays_spends = DailySpendEntry.objects.filter(user=request.user, date=today)
        spent_today = sum((s.amount for s in todays_spends), Decimal("0.00"))
        starting_balance_today = profile.available_balance + spent_today

        sts = SafeToSpendCalculator.compute_sts(
            available_balance=starting_balance_today,
            rent_amount=profile.rent_amount,
            rent_is_paid=profile.rent_is_paid,
            emi_amount=profile.emi_amount,
            emi_is_paid=profile.emi_is_paid,
            emergency_alloc=profile.emergency_pool,
            savings_alloc=profile.savings_pool,
            goal_contribution=profile.goal_monthly_contribution,
            salary_day=profile.salary_day,
            reference_date=today,
        )

        effective_budget = sts.daily_sts + profile.overspend_absorbed_today
        uncovered = max(Decimal("0.00"), spent_today - effective_budget)

        if uncovered <= Decimal("0.00"):
            messages.info(request, "No uncovered overspend found.")
            return redirect("dashboard")

        if choice == "emergency":
            cover_amt = min(uncovered, profile.emergency_pool)
            profile.emergency_pool -= cover_amt
            profile.overspend_absorbed_today += cover_amt
            profile.save()
            messages.success(
                request,
                f"🛡️ Covered ₹{cover_amt:.2f} from Emergency Pool. "
                f"Upcoming days remain shielded at ₹{sts.daily_sts:.2f}/day!"
            )
        elif choice == "savings":
            cover_amt = min(uncovered, profile.savings_pool)
            profile.savings_pool -= cover_amt
            profile.overspend_absorbed_today += cover_amt
            profile.save()
            messages.success(
                request,
                f"🌿 Covered ₹{cover_amt:.2f} from Savings Pool. "
                f"Upcoming days remain shielded at ₹{sts.daily_sts:.2f}/day!"
            )
        elif choice == "spread":
            # Acknowledge overspend: let it reduce tomorrow's Safe-to-Spend naturally
            profile.overspend_absorbed_today += uncovered
            profile.save()
            messages.info(
                request,
                f"📉 Overspend absorbed. Your Safe-To-Spend will naturally adjust across the remaining "
                f"{sts.days_remaining} days until salary."
            )

    return redirect("dashboard")


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
