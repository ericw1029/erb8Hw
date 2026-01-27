from django.db import models
from django.core.validators import MinLengthValidator, RegexValidator
from django.core.exceptions import ValidationError
import re

# Create your models here.
class Customer(models.Model):
    
    customer_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100,validators=[MinLengthValidator(2)],help_text="Name must be 2-100 characters",)
    email = models.EmailField(unique=True, help_text="Valid email format required")
    phone = models.CharField(max_length=15,blank=True,null=True,
        validators=[RegexValidator(regex=r"^[\d\s\-\+\(\)]+$",message="Phone number can only contain digits, spaces, +, -, (, )",)],
        help_text="Optional phone number",)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        errors = {}

        # Name validation
        if not self.name or len(self.name.strip()) == 0:
            errors["name"] = "Name cannot be empty"
        elif len(self.name) > 100:
            errors["name"] = "Name cannot exceed 100 characters"

        # Email validation
        if not self.email:
            errors["email"] = "Email cannot be empty"
        else:
            # Additional email format check
            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_pattern, self.email):
                errors["email"] = "Invalid email format"

        # Phone validation if provided
        if self.phone and self.phone.strip():
            # Remove common separators and check if all digits remain
            phone_digits = re.sub(r"[\s\-\+\(\)]", "", self.phone)
            if not phone_digits.isdigit():
                errors["phone"] = (
                    "Phone number must contain only digits and valid separators"
                )
            elif len(phone_digits) < 7 or len(phone_digits) > 15:
                errors["phone"] = "Phone number must be 7-15 digits"

        if errors:
            raise ValidationError(errors)
        
    def __str__(self):
        return self.name