# forms.py
import re
from django import forms
from .models import Customer


class CustomerCSVForm(forms.Form):
    name = forms.CharField(max_length=100, min_length=2)
    email = forms.EmailField()
    phone = forms.CharField(required=False, max_length=15)
    address = forms.CharField(required=False)

    def clean_name(self):
        #print("CustomerCSVForm", "clean_name")
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Name cannot be empty")
        if len(name) > 100:
            raise forms.ValidationError("Name cannot exceed 100 characters")
        return name

    def clean_phone(self):
        #print("CustomerCSVForm", "clean_phone")
        phone = self.cleaned_data.get("phone", "").strip()
        if phone:
            # Remove common separators
            phone_digits = re.sub(r"[\s\-\+\(\)]", "", phone)
            if not phone_digits.isdigit():
                raise forms.ValidationError(
                    "Phone number can only contain digits and these separators: space, -, +, (, )"
                )
            if len(phone_digits) < 7 or len(phone_digits) > 15:
                raise forms.ValidationError("Phone number must be 7-15 digits")
        return phone

    def clean_email(self):
        #print("CustomerCSVForm", "clean_email")
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise forms.ValidationError("Email cannot be empty")

        # Enhanced email validation
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise forms.ValidationError(
                "Invalid email format. Example: user@example.com"
            )

        return email
