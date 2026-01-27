# forms.py
from django import forms
from django.utils import timezone
import re
from datetime import datetime


class OrderCSVForm(forms.Form):
    customer_email = forms.EmailField()
    product_sku = forms.CharField(max_length=50)
    quantity = forms.IntegerField(min_value=1)
    order_date = forms.CharField()  # Will parse in clean method
    status = forms.CharField(max_length=20)
    total_amount = forms.DecimalField(min_value=0.01, max_digits=12, decimal_places=2)

    def clean_customer_email(self):
        email = self.cleaned_data.get("customer_email", "").strip().lower()
        if not email:
            raise forms.ValidationError("Customer email is required")
        return email

    def clean_product_sku(self):
        sku = self.cleaned_data.get("product_sku", "").strip()
        if not sku:
            raise forms.ValidationError("Product SKU is required")
        return sku

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity is None:
            raise forms.ValidationError("Quantity is required")
        if quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than 0")
        if quantity > 10000:  # Reasonable limit
            raise forms.ValidationError("Quantity cannot exceed 10,000")
        return quantity

    def clean_order_date(self):
        date_str = self.cleaned_data.get("order_date", "").strip()
        if not date_str:
            raise forms.ValidationError("Order date is required")

        # Try multiple date formats
        date_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
            "%Y%m%d",
        ]

        parsed_date = None
        for date_format in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, date_format)
                break
            except ValueError:
                continue

        if parsed_date is None:
            raise forms.ValidationError(f"Invalid date format. Use formats like: YYYY-MM-DD HH:MM:SS, YYYY-MM-DD, DD/MM/YYYY")

        # Check if date is not in the future
        if parsed_date > datetime.now():
            raise forms.ValidationError("Order date cannot be in the future")

        # Make datetime timezone-aware
        aware_date = timezone.make_aware(parsed_date, timezone.get_current_timezone())

        return aware_date
        #return parsed_date

    def clean_status(self):
        status = self.cleaned_data.get("status", "").strip().lower()
        valid_statuses = [
            "pending",
            "processing",
            "shipped",
            "delivered",
            "cancelled",
            "refunded",
        ]

        if not status:
            raise forms.ValidationError("Order status is required")

        if status not in valid_statuses:
            raise forms.ValidationError(
                f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}"
            )

        return status

    def clean_total_amount(self):
        amount = self.cleaned_data.get("total_amount")
        if amount is None:
            raise forms.ValidationError("Total amount is required")
        if amount <= 0:
            raise forms.ValidationError("Total amount must be greater than 0")
        if amount > 9999999999.99:  # Max for 12 digits, 2 decimal places
            raise forms.ValidationError("Total amount cannot exceed 9,999,999,999.99")
        return amount

    def clean(self):
        cleaned_data = super().clean()

        # Additional cross-field validation
        quantity = cleaned_data.get("quantity")
        total_amount = cleaned_data.get("total_amount")

        if quantity and total_amount:
            # Check if total amount seems reasonable (at least $0.01 per item)
            if total_amount / quantity < 0.01:
                self.add_error(
                    "total_amount",
                    f"Total amount (${total_amount:.2f}) seems too low for {quantity} items",
                )

        return cleaned_data
