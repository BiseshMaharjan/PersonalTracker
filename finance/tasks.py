from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import RecurringTransaction, Transaction

@shared_task
def process_recurring_transactions():
    today = timezone.now().date()
    due = RecurringTransaction.objects.filter(active=True, next_run__lte=today)

    for r in due:
        if r.end_date and r.next_run > r.end_date:
            r.active = False
            r.save()
            continue

        already_exists = Transaction.objects.filter(
        user=r.user, date=r.next_run, merchant=r.merchant,
        amount=r.amount, type=r.type,
        ).exists()

        if not already_exists:
         Transaction.objects.create(
        user=r.user,
        amount=r.amount,
        currency=r.currency,
        date=r.next_run,
        type=r.type,
        category=r.category,
        merchant=r.merchant,
        notes=r.notes,
        tags=r.tags,
    )
        if r.interval == "daily":
            r.next_run += timedelta(days=r.interval_count)
        elif r.interval == "weekly":
            r.next_run += timedelta(weeks=r.interval_count)
        elif r.interval == "monthly":
            total_months = r.next_run.month - 1 + r.interval_count
            year = r.next_run.year + total_months // 12
            month = total_months % 12 + 1
            day = min(r.next_run.day, 28)
            r.next_run = r.next_run.replace(year=year, month=month, day=day)
        elif r.interval == "yearly":
            r.next_run = r.next_run.replace(year=r.next_run.year + r.interval_count)

        if r.end_date and r.next_run > r.end_date:
            r.active = False
        r.save()