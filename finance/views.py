from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.db import models
from django.utils import timezone
import json
from .models import Transaction, Category, Budget, Profile, RecurringTransaction
from .forms import TransactionForm, CategoryForm, NewCategoryForm, BudgetForm, ProfileForm, RecurringTransactionForm
from playwright.sync_api import sync_playwright
from django.http import HttpResponse
import tempfile
import os
from django.urls import reverse
from fpdf import FPDF



@login_required
def dashboard(request):
    user = request.user

    txs = Transaction.objects.filter(user=user)

    income = txs.filter(type="income").aggregate(total=Sum("amount"))["total"] or 0
    expenses = txs.filter(type="expense").aggregate(total=Sum("amount"))["total"] or 0
    balance = income - expenses

    by_category = (
        txs.filter(type="expense")
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    category_labels = [c["category__name"] or "Uncategorized" for c in by_category]
    category_values = [float(c["total"]) for c in by_category]

    cashflow = (
        txs.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(income=Sum("amount", filter=models.Q(type="income")),
                  expense=Sum("amount", filter=models.Q(type="expense")))
        .order_by("month")
    )
    cashflow_labels = [c["month"].strftime("%b %Y") for c in cashflow]
    cashflow_income = [float(c["income"] or 0) for c in cashflow]
    cashflow_expense = [float(c["expense"] or 0) for c in cashflow]

    all_ordered = txs.order_by("date", "id")
    running = 0
    balances = {}
    for t in all_ordered:
        if t.type == "income":
            running += t.amount
        else:
            running -= t.amount
        balances[t.id] = running

    recent = list(txs.order_by("-date", "-id")[:5])
    for t in recent:
        t.running_balance = balances[t.id]

    context = {
        "balance": balance,
        "income": income,
        "expenses": expenses,
        "recent": recent,
        "category_labels": json.dumps(category_labels),
        "category_values": json.dumps(category_values),
        "cashflow_labels": json.dumps(cashflow_labels),
        "cashflow_income": json.dumps(cashflow_income),
        "cashflow_expense": json.dumps(cashflow_expense),
    }
    return render(request, "finance/dashboard.html", context)


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def transaction_list(request):
    transactions = Transaction.objects.filter(user=request.user).select_related("category")

    date_from = request.GET.get("from")
    date_to = request.GET.get("to")
    type_filter = request.GET.get("type")
    category_filter = request.GET.get("category")
    merchant_filter = request.GET.get("merchant")
    sort = request.GET.get("sort", "-date")

    if date_from:
        transactions = transactions.filter(date__gte=date_from)
    if date_to:
        transactions = transactions.filter(date__lte=date_to)
    if type_filter:
        transactions = transactions.filter(type=type_filter)
    if category_filter:
        transactions = transactions.filter(category_id=category_filter)
    if merchant_filter:
        transactions = transactions.filter(merchant=merchant_filter)

    # Running balance needs full unfiltered chronological order first
    all_ordered = Transaction.objects.filter(user=request.user).order_by("date", "id")
    running = 0
    balances = {}
    for t in all_ordered:
        if t.type == "income":
            running += t.amount
        else:
            running -= t.amount
        balances[t.id] = running

    valid_sorts = ["date", "-date", "amount", "-amount"]
    if sort not in valid_sorts:
        sort = "-date"
    transactions = transactions.order_by(sort, "-id")

    transactions = list(transactions)
    for t in transactions:
        t.running_balance = balances[t.id]

    categories = Category.objects.filter(user=request.user)
    merchants = (
        Transaction.objects.filter(user=request.user)
        .exclude(merchant="")
        .values_list("merchant", flat=True)
        .distinct()
        .order_by("merchant")
    )

    context = {
        "transactions": transactions,
        "date_from": date_from or "",
        "date_to": date_to or "",
        "type_filter": type_filter or "",
        "category_filter": category_filter or "",
        "merchant_filter": merchant_filter or "",
        "sort": sort,
        "categories": categories,
        "merchants": merchants,
        "count": len(transactions),
    }
    return render(request, "finance/transaction_list.html", context)


@login_required
def transaction_create(request):
    if request.method == "POST":
        form = TransactionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            tx = form.save(commit=False)
            tx.user = request.user
            tx.save()
            return redirect("transaction_list")
    else:
        form = TransactionForm(user=request.user)

    return render(request, "finance/transaction_form.html", {"form": form})


@login_required
def transaction_edit(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == "POST":
        form = TransactionForm(request.POST, request.FILES, instance=tx, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("transaction_list")
    else:
        form = TransactionForm(instance=tx, user=request.user)
    return render(request, "finance/transaction_form.html", {"form": form})


@login_required
def transaction_delete(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == "POST":
        tx.delete()
        return redirect("transaction_list")
    return render(request, "finance/transaction_confirm_delete.html", {"transaction": tx})


DEFAULT_CATEGORIES = ["Food and Household", "Transport", "Rent", "Salary and Wages", "Utilities", "Entertainment", "Other"]

def create_default_categories(user):
    for name in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(user=user, name=name, parent=None)


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            create_default_categories(user)
            login(request, user)
            return redirect("dashboard")
    else:
        form = UserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user)
    return render(request, "finance/category_list.html", {"categories": categories})


@login_required
def category_create(request):
    if request.method == "POST":
        form = NewCategoryForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            sub_name = form.cleaned_data["subcategory_name"]

            cat = Category.objects.create(user=request.user, name=name)

            if sub_name:
                Category.objects.create(user=request.user, name=sub_name, parent=cat)

            return redirect("category_list")
    else:
        form = NewCategoryForm()
    return render(request, "finance/category_form.html", {"form": form})


@login_required
def category_edit(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            return redirect("category_list") if not cat.parent_id else redirect("category_edit", pk=cat.parent_id)
    else:
        form = CategoryForm(instance=cat)

    subcategories = cat.subcategories.filter(user=request.user) if not cat.parent_id else None
    return render(request, "finance/category_edit.html", {
        "form": form, "category": cat, "subcategories": subcategories,
    })


@login_required
def subcategory_create(request, parent_pk):
    parent = get_object_or_404(Category, pk=parent_pk, user=request.user, parent__isnull=True)
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.user = request.user
            sub.parent = parent
            sub.save()
            return redirect("category_edit", pk=parent.pk)
    else:
        form = CategoryForm()
    return render(request, "finance/subcategory_form.html", {"form": form, "parent": parent})


@login_required
def category_delete(request, pk):
    cat = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == "POST":
        cat.delete()
        return redirect("category_list")
    return render(request, "finance/category_confirm_delete.html", {"category": cat})


def _category_chart_data(user, tran_type, date_from=None, date_to=None):
    top_categories = Category.objects.filter(user=user, parent__isnull=True)

    labels = []
    own_totals = []
    sub_names = []
    sub_data = {}
    totals_per_category = []

    for cat in top_categories:
        labels.append(cat.name)

        direct_qs = Transaction.objects.filter(user=user, type=tran_type, category=cat)
        if date_from:
            direct_qs = direct_qs.filter(date__gte=date_from)
        if date_to:
            direct_qs = direct_qs.filter(date__lte=date_to)
        direct_total = direct_qs.aggregate(total=Sum("amount"))["total"] or 0
        own_totals.append(float(direct_total))

        cat_total = float(direct_total)
        subs_for_this_cat = {}
        for sub in cat.subcategories.filter(user=user):
            sub_qs = Transaction.objects.filter(user=user, type=tran_type, category=sub)
            if date_from:
                sub_qs = sub_qs.filter(date__gte=date_from)
            if date_to:
                sub_qs = sub_qs.filter(date__lte=date_to)
            sub_total = sub_qs.aggregate(total=Sum("amount"))["total"] or 0
            subs_for_this_cat[sub.name] = float(sub_total)
            cat_total += float(sub_total)
            if sub.name not in sub_names:
                sub_names.append(sub.name)
                sub_data[sub.name] = [0] * len(labels[:-1])

        for name in sub_names:
            sub_data[name].append(subs_for_this_cat.get(name, 0))

        totals_per_category.append(cat_total)

    datasets = [{"label": "Direct (no subcategory)", "data": own_totals}]
    for name in sub_names:
        datasets.append({"label": name, "data": sub_data[name]})

    return labels, datasets, totals_per_category


@login_required
def reports_landing(request):
    return render(request, "finance/reports_landing.html")


@login_required
def spending_report(request):
    user = request.user
    date_from = request.GET.get("from")
    date_to = request.GET.get("to")

    labels, datasets, totals = _category_chart_data(user, "expense", date_from, date_to)

    context = {
        "chart_labels": json.dumps(labels),
        "chart_datasets": json.dumps(datasets),
        "doughnut_labels": json.dumps(labels),
        "doughnut_values": json.dumps(totals),
        "date_from": date_from or "",
        "date_to": date_to or "",
    }
    return render(request, "finance/spending_report.html", context)


@login_required
def income_report(request):
    user = request.user
    labels, datasets, totals = _category_chart_data(user, "income")

    context = {
        "chart_labels": json.dumps(labels),
        "chart_datasets": json.dumps(datasets),
    }
    return render(request, "finance/income_report.html", context)


@login_required
def budget_overview(request):
    user = request.user
    today = timezone.now().date()

    earliest_tx = Transaction.objects.filter(user=user).order_by("date").first()
    earliest_budget = Budget.objects.filter(user=user).order_by("year", "month").first()

    candidates = []
    if earliest_tx:
        candidates.append((earliest_tx.date.year, earliest_tx.date.month))
    if earliest_budget:
        candidates.append((earliest_budget.year, earliest_budget.month))

    if candidates:
        min_year, min_month = min(candidates)
    else:
        min_year, min_month = today.year, today.month

    min_period = f"{min_year:04d}-{min_month:02d}"

    period = request.GET.get("period")
    if period:
        try:
            year, month = period.split("-")
            month, year = int(month), int(year)
        except (ValueError, TypeError):
            month, year = today.month, today.year
    else:
        month, year = today.month, today.year

    before_start = (year, month) < (min_year, min_month)

    items = []
    alerts = []
    total_budget = 0
    total_spent = 0
    chart_labels = []
    chart_spent = []
    overall_percentage = 0
    overall_raw_percentage = 0
    overall_status = "within_budget"

    if not before_start:
        budgets = Budget.objects.filter(user=user, month=month, year=year).select_related("category")

        for b in budgets:
            spent = Transaction.objects.filter(
                user=user, type="expense", category=b.category, date__month=month, date__year=year
            ).aggregate(total=Sum("amount"))["total"] or 0
            spent = float(spent)
            budget_amt = float(b.amount)
            remaining = budget_amt - spent
            percentage = (spent / budget_amt * 100) if budget_amt else 0

            if spent > budget_amt:
                status = "overspent"
            elif percentage >= 90:
                status = "near_limit"
            elif percentage >= 80:
                status = "approaching"
            else:
                status = "within_budget"

            items.append({
                "budget": b, "spent": spent, "budget_amount": budget_amt,
                "remaining": remaining, "percentage": min(percentage, 100),
                "raw_percentage": percentage, "status": status,
            })

            total_budget += budget_amt
            total_spent += spent

            if status == "overspent":
                alerts.append({"level": "danger", "text": f"{b.category.name}: exceeded budget by Rs. {spent - budget_amt:.2f}."})
            elif status == "near_limit":
                alerts.append({"level": "warning", "text": f"{b.category.name}: {percentage:.0f}% of budget used — near limit."})
            elif status == "approaching":
                alerts.append({"level": "warning", "text": f"{b.category.name}: {percentage:.0f}% of budget used."})
            elif budget_amt and percentage < 50:
                alerts.append({"level": "success", "text": f"{b.category.name}: Rs. {remaining:.2f} under budget."})

        for item in items:
            item["chart_percentage"] = round((item["spent"] / total_spent * 100), 0) if total_spent else 0

        chart_labels = [item["budget"].category.name for item in items]
        chart_spent = [item["spent"] for item in items]

        overall_raw_percentage = (total_spent / total_budget * 100) if total_budget else 0
        overall_percentage = min(overall_raw_percentage, 100)
        if total_spent > total_budget and total_budget:
            overall_status = "overspent"
        elif overall_raw_percentage >= 90:
            overall_status = "near_limit"
        elif overall_raw_percentage >= 80:
            overall_status = "approaching"
        else:
            overall_status = "within_budget"

    context = {
        "items": items, "alerts": alerts,
        "total_budget": total_budget, "total_spent": total_spent,
        "total_remaining": total_budget - total_spent,
        "month": month, "year": year,
        "period_value": f"{year:04d}-{month:02d}",
        "min_period": min_period,
        "chart_labels": json.dumps(chart_labels),
        "chart_spent": json.dumps(chart_spent),
        "overall_percentage": overall_percentage,
        "overall_raw_percentage": overall_raw_percentage,
        "overall_percentage_remainder": 100 - overall_percentage,
        "overall_status": overall_status,
        "before_start": before_start,
    }
    return render(request, "finance/budget_overview.html", context)


@login_required
def budget_create(request):
    if request.method == "POST":
        form = BudgetForm(request.POST, user=request.user)
        if form.is_valid():
            year, month = form.cleaned_data["period"].split("-")
            Budget.objects.update_or_create(
                user=request.user,
                category=form.cleaned_data["category"],
                month=int(month),
                year=int(year),
                defaults={"amount": form.cleaned_data["amount"]},
            )
            return redirect("budget_overview")
    else:
        form = BudgetForm(user=request.user)
    return render(request, "finance/budget_form.html", {"form": form})


@login_required
def profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    return render(request, "finance/profile.html", {"profile": profile})


@login_required
def profile_edit(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save(user=request.user)
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile, user=request.user)

    return render(request, "finance/profile_edit.html", {"form": form})

@login_required
def recurring_list(request):
    recurrences = RecurringTransaction.objects.filter(user=request.user).select_related("category").order_by("next_run")
    return render(request, "finance/recurring_list.html", {"recurrences": recurrences})

@login_required
def recurring_create(request):
    if request.method == "POST":
        form = RecurringTransactionForm(request.POST, user=request.user)
        if form.is_valid():
            r = form.save(commit=False)
            r.user = request.user
            r.save()
            return redirect("recurring_list")
    else:
        form = RecurringTransactionForm(user=request.user)
    return render(request, "finance/recurring_form.html", {"form": form})

EXPORTABLE_PAGES = {
    "budget": {"url_name": "budget_overview", "selector": ".container-fluid", "filename": "budget_overview"},
    "transactions": {"url_name": "transaction_list", "selector": "#transactions-export-area", "filename": "transactions"},
    "spending": {"url_name": "spending_report", "selector": ".container-fluid", "filename": "spending_report"},
    "income": {"url_name": "income_report", "selector": ".container-fluid", "filename": "income_report"},
}

@login_required
def export_pdf(request, page_key):
    config = EXPORTABLE_PAGES.get(page_key)
    if not config:
        return HttpResponse("Invalid export target.", status=404)

    target_url = request.build_absolute_uri(reverse(config["url_name"]))

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
        img_path = tmp_img.name

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.context.add_cookies([{
            "name": "sessionid",
            "value": request.COOKIES.get("sessionid", ""),
            "url": request.build_absolute_uri("/"),
        }])
        page.goto(target_url, wait_until="networkidle")
        page.locator(config["selector"]).screenshot(path=img_path)
        browser.close()

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.image(img_path, x=10, y=10, w=190)
    pdf_path = img_path.replace(".png", ".pdf")
    pdf.output(pdf_path)

    os.remove(img_path)
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()
    os.remove(pdf_path)

    response = HttpResponse(pdf_data, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{config["filename"]}.pdf"'
    return response