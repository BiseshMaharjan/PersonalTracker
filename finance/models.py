from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


class Category(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    color = models.CharField(max_length=7, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="subcategories"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Transaction(models.Model):
    TRAN_TYPE = [("expense", "Expense"), ("income", "Income")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default="NPR")
    date = models.DateField(default=timezone.now)
    type = models.CharField(max_length=10, choices=TRAN_TYPE)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    merchant = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)
    receipt = models.ImageField(upload_to="receipts/%Y/%m/%d/", null=True, blank=True)
    ocr_parsed = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    tags = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.type} - {self.amount} {self.currency} ({self.merchant})"


class RecurringTransaction(models.Model):
    TRAN_TYPE = [("expense", "Expense"), ("income", "Income")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="NPR")
    type = models.CharField(max_length=10, choices=TRAN_TYPE, default="expense")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    merchant = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True)

    interval = models.CharField(max_length=10, default="monthly")
    interval_count = models.PositiveIntegerField(default=1)
    next_run = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.merchant or self.category} - every {self.interval_count} {self.interval}"

class Budget(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    month = models.IntegerField()
    year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "category", "month", "year")

    def __str__(self):
        return f"{self.category.name} budget - {self.month}/{self.year}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


class Profile(models.Model):
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("others", "Others"),
        ("rather_not_say", "Rather not say"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to="profile_photos/", null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    pan_no = models.CharField(max_length=20, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)

    def __str__(self):
        return f"{self.user.username}'s profile"