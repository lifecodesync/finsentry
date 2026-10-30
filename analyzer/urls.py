"""
analyzer/urls.py
Route declarations for FinSentry Safe-to-Spend (STS) web application.
"""

from django.urls import path
from analyzer import views

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("setup/", views.profile_setup_view, name="profile_setup"),
    path("spend/", views.log_spend_view, name="log_spend"),
    path("toggle/<str:bill_type>/", views.toggle_obligation_view, name="toggle_obligation"),
    path("resolve-overspend/", views.resolve_overspend_view, name="resolve_overspend"),
    path("clear-simulation/", views.clear_simulation_view, name="clear_simulation"),
]
