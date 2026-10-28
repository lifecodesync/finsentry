"""
analyzer/views.py
Web views connecting Django templates with FinSentry core domain engines.
"""

from datetime import date, datetime
from decimal import Decimal
import io

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpRequest, HttpResponse

from core.models import Transaction, TransactionType
from core.parser import CSVTransactionParser
from core.categorizer import TransactionCategorizer
from core.analytics import CashFlowAnalytics
from core.detector import RiskAndAnomalyDetector
from analyzer.models import StoredTransaction, StoredAnomalyFlag, AppSettings


def get_core_transactions():
    """Helper to retrieve DB records and convert them into domain Transaction entities."""
    db_txns = StoredTransaction.objects.all().order_by("date")
    domain_txns = []
    for t in db_txns:
        domain_txns.append(
            Transaction(
                id=t.txn_id,
                date=t.date,
                description=t.description,
                amount=t.amount,
                type=TransactionType(t.type),
                category=t.category,
                category_reason=t.category_reason,
                is_duplicate=t.is_duplicate,
            )
        )
    return domain_txns, db_txns


def dashboard_view(request: HttpRequest) -> HttpResponse:
    settings = AppSettings.get_settings()
    domain_txns, db_txns = get_core_transactions()

    analytics = CashFlowAnalytics()
    summary = analytics.calculate_summary(domain_txns)
    pie_chart = analytics.generate_category_pie_chart_base64(summary.category_totals)
    bar_chart = analytics.generate_monthly_bar_chart_base64(summary.monthly_trend)
    explanation = analytics.get_cash_flow_vs_balance_explanation()

    detector = RiskAndAnomalyDetector(baseline_spike_multiplier=settings.baseline_spike_multiplier)
    recurring = detector.detect_recurring_payments(domain_txns)

    # Calculate runway projection
    runway = detector.project_cash_flow_runway(
        starting_balance=settings.starting_balance,
        threshold_limit=settings.threshold_limit,
        upcoming_obligations=[],
        average_daily_discretionary=settings.daily_discretionary_burn,
        days_to_project=30,
        start_from_date=date.today()
    )

    active_flags = StoredAnomalyFlag.objects.filter(is_dismissed=False)
    recent_txns = db_txns[:10]

    context = {
        "summary": summary,
        "pie_chart": pie_chart,
        "bar_chart": bar_chart,
        "explanation": explanation,
        "recurring_payments": recurring,
        "runway": runway,
        "active_flags_count": active_flags.count(),
        "recent_transactions": recent_txns,
        "total_transactions_count": db_txns.count(),
        "settings": settings,
    }
    return render(request, "dashboard.html", context)


def upload_csv_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST" and request.FILES.get("csv_file"):
        uploaded_file = request.FILES["csv_file"]

        try:
            # Read and parse buffer
            content = uploaded_file.read().decode("utf-8-sig", errors="replace")
            parser = CSVTransactionParser(check_duplicates=True)
            result = parser.parse_file(io.StringIO(content))

            # Categorize transactions
            categorizer = TransactionCategorizer()
            categorizer.categorize_all(result.transactions)

            # Detect anomalies
            settings = AppSettings.get_settings()
            detector = RiskAndAnomalyDetector(baseline_spike_multiplier=settings.baseline_spike_multiplier)
            flags = detector.detect_anomalies(result.transactions)

            # Persist transactions
            created_count = 0
            txn_map = {}
            for t in result.transactions:
                obj, created = StoredTransaction.objects.update_or_create(
                    txn_id=t.id,
                    defaults={
                        "date": t.date,
                        "description": t.description,
                        "amount": t.amount,
                        "type": t.type.value,
                        "category": t.category,
                        "category_reason": t.category_reason,
                        "is_duplicate": t.is_duplicate,
                    }
                )
                txn_map[t.id] = obj
                if created:
                    created_count += 1

            # Persist anomaly flags
            for f in flags:
                target_obj = txn_map.get(f.transaction_id)
                if target_obj:
                    StoredAnomalyFlag.objects.get_or_create(
                        flag_id=f.flag_id,
                        defaults={
                            "transaction": target_obj,
                            "flag_type": f.flag_type,
                            "severity": f.severity,
                            "explanation": f.explanation,
                            "suggested_action": f.suggested_action,
                        }
                    )

            messages.success(
                request,
                f"Successfully parsed {result.total_rows_read} rows. "
                f"Imported {created_count} clean transactions ({result.duplicate_count} duplicates flagged). "
                f"Isolated {len(result.errors)} invalid rows."
            )
            return render(request, "upload.html", {"parse_result": result})

        except Exception as e:
            messages.error(request, f"Failed to parse CSV: {e}")
            return render(request, "upload.html")

    return render(request, "upload.html")


def transactions_view(request: HttpRequest) -> HttpResponse:
    query_type = request.GET.get("type", "").strip().upper()
    query_cat = request.GET.get("category", "").strip()

    qs = StoredTransaction.objects.all()
    if query_type in ("INCOME", "EXPENSE"):
        qs = qs.filter(type=query_type)
    if query_cat:
        qs = qs.filter(category=query_cat)

    categories = StoredTransaction.objects.values_list("category", flat=True).distinct()

    return render(request, "transactions.html", {
        "transactions": qs,
        "categories": categories,
        "selected_type": query_type,
        "selected_category": query_cat,
    })


def override_category_view(request: HttpRequest, txn_id: str) -> HttpResponse:
    if request.method == "POST":
        txn = get_object_or_404(StoredTransaction, txn_id=txn_id)
        new_cat = request.POST.get("category", "").strip()
        note = request.POST.get("note", "").strip()

        if new_cat:
            categorizer = TransactionCategorizer()
            domain_txn = Transaction(
                id=txn.txn_id,
                date=txn.date,
                description=txn.description,
                amount=txn.amount,
                type=TransactionType(txn.type),
                category=txn.category
            )
            categorizer.apply_user_override(domain_txn, new_cat, note)
            txn.category = domain_txn.category
            txn.category_reason = domain_txn.category_reason
            txn.save()
            messages.success(request, f"Updated category for '{txn.description}' to '{txn.category}'.")

    return redirect("transactions")


def anomalies_view(request: HttpRequest) -> HttpResponse:
    active_flags = StoredAnomalyFlag.objects.filter(is_dismissed=False)
    dismissed_flags = StoredAnomalyFlag.objects.filter(is_dismissed=True)
    return render(request, "anomalies.html", {
        "active_flags": active_flags,
        "dismissed_flags": dismissed_flags,
    })


def dismiss_flag_view(request: HttpRequest, flag_id: str) -> HttpResponse:
    if request.method == "POST":
        flag = get_object_or_404(StoredAnomalyFlag, flag_id=flag_id)
        note = request.POST.get("dismissal_note", "").strip()
        flag.is_dismissed = True
        flag.dismissal_note = note if note else "Dismissed by user after manual review."
        flag.save()
        messages.info(request, f"Flag {flag.flag_id} dismissed.")
    return redirect("anomalies")


def settings_view(request: HttpRequest) -> HttpResponse:
    settings = AppSettings.get_settings()
    simulation_result = None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_settings":
            settings.starting_balance = Decimal(request.POST.get("starting_balance", "50000.00"))
            settings.threshold_limit = Decimal(request.POST.get("threshold_limit", "10000.00"))
            settings.baseline_spike_multiplier = float(request.POST.get("baseline_spike_multiplier", "2.5"))
            settings.daily_discretionary_burn = Decimal(request.POST.get("daily_discretionary_burn", "200.00"))
            settings.save()
            messages.success(request, "Settings updated successfully.")
        elif action == "run_simulation":
            sim_balance = Decimal(request.POST.get("sim_balance", str(settings.starting_balance)))
            sim_threshold = Decimal(request.POST.get("sim_threshold", str(settings.threshold_limit)))
            sim_burn = Decimal(request.POST.get("sim_burn", str(settings.daily_discretionary_burn)))
            
            # Future obligation test
            ob_desc = request.POST.get("ob_desc", "Scheduled Obligation")
            ob_amt_str = request.POST.get("ob_amt", "0")
            ob_days_str = request.POST.get("ob_days", "15")

            try:
                ob_amt = Decimal(ob_amt_str) if ob_amt_str else Decimal("0")
                ob_days = int(ob_days_str) if ob_days_str else 15
                target_date = date.today() + timedelta(days=ob_days)
                obligations = [(target_date, ob_amt, ob_desc)] if ob_amt > 0 else []

                detector = RiskAndAnomalyDetector()
                simulation_result = detector.project_cash_flow_runway(
                    starting_balance=sim_balance,
                    threshold_limit=sim_threshold,
                    upcoming_obligations=obligations,
                    average_daily_discretionary=sim_burn,
                    days_to_project=30,
                    start_from_date=date.today()
                )
            except Exception as e:
                messages.error(request, f"Simulation input error: {e}")

    return render(request, "settings.html", {
        "settings": settings,
        "simulation": simulation_result
    })



def clear_data_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        StoredTransaction.objects.all().delete()
        StoredAnomalyFlag.objects.all().delete()
        messages.info(request, "All transactions and risk flags have been cleared. Database is empty.")
    return redirect("dashboard")
