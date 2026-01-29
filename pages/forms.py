# forms.py
from django import forms
from datetime import datetime
from django.core.exceptions import ValidationError
import re

class CSVImportForm(forms.Form):
    csv_file = forms.FileField(
        label="Upload a CSV file",
        help_text="",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".csv"}),
    )
    MODEL_CHOICES = [
        ("customer", "Customer"),
        ("product", "Product"),
        ("order", "Order"),
    ]
    
    DELETE_OPTIONS = [
        ("append", "Append to existing data"),
        ("replace", "Delete all existing data before import"),
    ]

    model_type = forms.ChoiceField(
        choices=MODEL_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    
    delete_option = forms.ChoiceField(
        choices=DELETE_OPTIONS,
        label="Import Option",
        initial="append",
        required=False,
        widget=forms.RadioSelect(attrs={"class": "form-check-input pl-5"}),
        help_text="Choose whether to append or replace existing data",
    )
    
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]

        # Check file extension
        if not csv_file.name.endswith(".csv"):
            raise ValidationError("File must be a CSV file (.csv)")

        # Check file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if csv_file.size > max_size:
            raise ValidationError(
                f"File size must be less than {max_size / 1024 / 1024}MB"
            )

        # Check if file is empty
        if csv_file.size == 0:
            raise ValidationError("File is empty")

        return csv_file