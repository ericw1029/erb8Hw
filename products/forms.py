# forms.py
import re
from django import forms


class ProductCSVForm(forms.Form):
    name = forms.CharField(max_length=200, min_length=2)
    sku = forms.CharField(max_length=50)
    description = forms.CharField(required=False, max_length=1000)
    price = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2)
    stock_quantity = forms.IntegerField(min_value=0)
    weight = forms.DecimalField(
        required=False, min_value=0, max_digits=8, decimal_places=3
    )

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Product name cannot be empty")
        if len(name) > 200:
            raise forms.ValidationError("Product name cannot exceed 200 characters")
        return name

    def clean_sku(self):
        sku = self.cleaned_data.get("sku", "").strip()
        if not sku:
            raise forms.ValidationError("SKU cannot be empty")
        if len(sku) > 50:
            raise forms.ValidationError("SKU cannot exceed 50 characters")

        # Validate SKU format (alphanumeric with hyphens and underscores)
        if not re.match(r"^[a-zA-Z0-9\-_]+$", sku):
            raise forms.ValidationError(
                "SKU can only contain letters, numbers, hyphens (-), and underscores (_)"
            )

        return sku

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price is None:
            raise forms.ValidationError("Price is required")
        if price < 0:
            raise forms.ValidationError("Price cannot be negative")
        if price > 99999999.99:  # Max for 10 digits, 2 decimal places
            raise forms.ValidationError("Price cannot exceed 99,999,999.99")
        return price

    def clean_stock_quantity(self):
        quantity = self.cleaned_data.get("stock_quantity")
        if quantity is None:
            raise forms.ValidationError("Stock quantity is required")
        if quantity < 0:
            raise forms.ValidationError("Stock quantity cannot be negative")
        if quantity > 2147483647:  # Max for IntegerField
            raise forms.ValidationError("Stock quantity is too large")
        return quantity

    def clean_weight(self):
        weight = self.cleaned_data.get("weight")
        if weight is not None and weight < 0:
            raise forms.ValidationError("Weight cannot be negative")
        if (
            weight is not None and weight > 99999.999
        ):  # Max for 8 digits, 3 decimal places
            raise forms.ValidationError("Weight cannot exceed 99,999.999 kg")
        return weight
