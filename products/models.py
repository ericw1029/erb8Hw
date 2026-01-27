# models.py - Add to your existing Product model
import re
from django.db import models
from django.core.validators import MinValueValidator
from django.core.validators import MinLengthValidator
from django.core.exceptions import ValidationError


class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(2)],
        help_text="Product name must be 2-200 characters",
    )
    sku = models.CharField(
        max_length=50, unique=True, help_text="Stock Keeping Unit - must be unique"
    )
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Price must be 0 or greater",
    )
    stock_quantity = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Stock quantity cannot be negative",
    )
    weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Weight in kg (optional)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        errors = {}

        # Name validation
        if not self.name or len(self.name.strip()) == 0:
            errors["name"] = "Product name cannot be empty"
        elif len(self.name) > 200:
            errors["name"] = "Product name cannot exceed 200 characters"

        # SKU validation
        if not self.sku or len(self.sku.strip()) == 0:
            errors["sku"] = "SKU cannot be empty"
        elif len(self.sku) > 50:
            errors["sku"] = "SKU cannot exceed 50 characters"
        else:
            # Allow alphanumeric, hyphens, and underscores
            if not re.match(r"^[a-zA-Z0-9\-_]+$", self.sku):
                errors["sku"] = (
                    "SKU can only contain letters, numbers, hyphens, and underscores"
                )

        # Price validation
        if self.price < 0:
            errors["price"] = "Price cannot be negative"

        # Stock quantity validation
        if self.stock_quantity < 0:
            errors["stock_quantity"] = "Stock quantity cannot be negative"

        # Weight validation if provided
        if self.weight is not None and self.weight < 0:
            errors["weight"] = "Weight cannot be negative"

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.name} ({self.sku})"
