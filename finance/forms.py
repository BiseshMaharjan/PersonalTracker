from django import forms
from django.db import models
from .models import Transaction,Category
from django.utils import timezone
from .models import Transaction, Category, RecurringTransaction, Budget, Profile

class GroupedCategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if obj.parent_id:
            return f"— {obj.name}"
        return obj.name

class TransactionForm(forms.ModelForm):
    category = GroupedCategoryChoiceField(
        queryset=Category.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Transaction
        fields = ["amount", "currency", "date", "type", "category", "merchant", "notes", "receipt", "tags"]
        widgets = {
            "amount": forms.NumberInput(attrs={"class": "form-control", "min": "0.01", "step": "0.01"}),
            "currency": forms.TextInput(attrs={"class": "form-control"}),
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "type": forms.Select(attrs={"class": "form-select"}),
            "merchant": forms.TextInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "receipt": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "tags": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            categories = Category.objects.filter(user=user)
            ordered_ids = []
            for parent in categories.filter(parent__isnull=True).order_by("name"):
                ordered_ids.append(parent.id)
                for sub in categories.filter(parent=parent).order_by("name"):
                    ordered_ids.append(sub.id)

            preserved_order = models.Case(
                *[models.When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)]
            )
            self.fields["category"].queryset = categories.filter(pk__in=ordered_ids).order_by(preserved_order)

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
        }


class NewCategoryForm(forms.Form):
    name = forms.CharField(
        max_length=64, label="Category",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    subcategory_name = forms.CharField(
        max_length=64, required=False, label="Subcategory (optional)",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Category
        fields = ["name", "parent"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["parent"].queryset = Category.objects.filter(user=user, parent__isnull=True)



MONTH_CHOICES = [
    (1, "January"), (2, "February"), (3, "March"), (4, "April"),
    (5, "May"), (6, "June"), (7, "July"), (8, "August"),
    (9, "September"), (10, "October"), (11, "November"), (12, "December"),
]

class BudgetForm(forms.ModelForm):
    category = GroupedCategoryChoiceField(queryset=Category.objects.none())
    period = forms.CharField(
        widget=forms.TextInput(attrs={"type": "month", "class": "form-control"}),
        label="Month",
    )

    class Meta:
        model = Budget
        fields = ["category", "amount", "period"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            categories = Category.objects.filter(user=user)
            ordered_ids = []
            for parent in categories.filter(parent__isnull=True).order_by("name"):
                ordered_ids.append(parent.id)
                for sub in categories.filter(parent=parent).order_by("name"):
                    ordered_ids.append(sub.id)

            preserved_order = models.Case(
                *[models.When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)]
            )
            self.fields["category"].queryset = categories.filter(pk__in=ordered_ids).order_by(preserved_order)

            today = timezone.now().date()
            self.fields["period"].widget.attrs["min"] = today.strftime("%Y-%m")

class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={"class": "form-control"}))

    class Meta:
        model = Profile
        fields = ["date_of_birth", "phone", "pan_no", "gender", "photo"]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "pan_no": forms.TextInput(attrs={"class": "form-control", "placeholder": "eg 12XXXXXX"}),
            "gender": forms.RadioSelect,
            "photo": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email

    def save(self, user, commit=True):
        profile = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            profile.save()
        return profile

class RecurringTransactionForm(forms.ModelForm):
    category = GroupedCategoryChoiceField(
        queryset=Category.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = RecurringTransaction
        fields = ["amount", "type", "category", "interval", "interval_count", "next_run", "end_date"]
        widgets = {
            "amount": forms.NumberInput(attrs={"class": "form-control", "min": "0.01", "step": "0.01"}),
            "type": forms.Select(attrs={"class": "form-select"}),
            "interval": forms.Select(attrs={"class": "form-select"}, choices=[
                ("daily", "Day(s)"), ("weekly", "Week(s)"),
                ("monthly", "Month(s)"), ("yearly", "Year(s)"),
            ]),
            "interval_count": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "next_run": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            categories = Category.objects.filter(user=user)
            ordered_ids = []
            for parent in categories.filter(parent__isnull=True).order_by("name"):
                ordered_ids.append(parent.id)
                for sub in categories.filter(parent=parent).order_by("name"):
                    ordered_ids.append(sub.id)

            preserved_order = models.Case(
                *[models.When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)]
            )
            self.fields["category"].queryset = categories.filter(pk__in=ordered_ids).order_by(preserved_order)