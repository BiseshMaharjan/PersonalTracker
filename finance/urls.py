from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("signup/", views.signup, name="signup"),
    path("logout/", views.logout_view, name="logout"),

    path("transactions/", views.transaction_list, name="transaction_list"),
    path("transactions/new/", views.transaction_create, name="transaction_create"),
    path("transactions/<int:pk>/edit/", views.transaction_edit, name="transaction_edit"),
    path("transactions/<int:pk>/delete/", views.transaction_delete, name="transaction_delete"),

    path("categories/", views.category_list, name="category_list"),
    path("categories/new/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("categories/<int:parent_pk>/subcategories/new/", views.subcategory_create, name="subcategory_create"),

    path("reports/", views.reports_landing, name="reports_landing"),
    path("reports/spending/", views.spending_report, name="spending_report"),
    path("reports/income/", views.income_report, name="income_report"),

    path("budgets/", views.budget_overview, name="budget_overview"),
    path("budgets/new/", views.budget_create, name="budget_create"),

    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),

    path("recurring/", views.recurring_list, name="recurring_list"),
    path("recurring/new/", views.recurring_create, name="recurring_create"),

    path("export/<str:page_key>/pdf/", views.export_pdf, name="export_pdf"),
]