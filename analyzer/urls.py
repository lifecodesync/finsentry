"""
analyzer/urls.py
Route declarations for FinSentry.
"""

from django.urls import path
from analyzer import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("upload/", views.upload_csv_view, name="upload_csv"),
    path("transactions/", views.transactions_view, name="transactions"),
    path("transactions/<str:txn_id>/override/", views.override_category_view, name="override_category"),
    path("anomalies/", views.anomalies_view, name="anomalies"),
    path("anomalies/<str:flag_id>/dismiss/", views.dismiss_flag_view, name="dismiss_flag"),
    path("settings/", views.settings_view, name="settings"),
]
