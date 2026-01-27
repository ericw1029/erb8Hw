# models.py
from django.db import models
from django.core.exceptions import ValidationError
from datetime import datetime
from products.models import Product
from customers.models import Customer
from django.utils import timezone


class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]

    order_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="orders")
    quantity = models.IntegerField()
    order_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default="pending")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    #created_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-order_date"]
        indexes = [
            models.Index(fields=["order_date"]),
            models.Index(fields=["status"]),
        ]

    def clean(self):
        errors = {}

        # Quantity validation
        if self.quantity <= 0:
            errors["quantity"] = "Quantity must be greater than 0"

        # Total amount validation
        if self.total_amount <= 0:
            errors["total_amount"] = "Total amount must be greater than 0"

        # Check if product has enough stock (only for new orders or quantity changes)
        if self.pk:  # Existing order
            old_order = Order.objects.get(pk=self.pk)
            if old_order.quantity != self.quantity:
                stock_needed = self.quantity - old_order.quantity
                if stock_needed > 0 and self.product.stock_quantity < stock_needed:
                    errors["quantity"] = (
                        f"Insufficient stock. Only {self.product.stock_quantity} available."
                    )
        else:  # New order
            if self.quantity > self.product.stock_quantity:
                errors["quantity"] = (
                    f"Insufficient stock. Only {self.product.stock_quantity} available."
                )

        # Order date validation (cannot be in the future by too much)
        if self.order_date:
            # if self.order_date > datetime.now().date():
            #     from django.utils.timezone import now

            #     if self.order_date > now().date():
            #         errors["order_date"] = "Order date cannot be in the future"
            # Extract date part from datetime
            order_date_only = self.order_date.date()
            today = timezone.now().date()
            
            if order_date_only > today:
                errors['order_date'] = "Order date cannot be in the future"

        # Status validation
        if self.status not in dict(self.ORDER_STATUS_CHOICES).keys():
            errors["status"] = (
                f"Invalid status. Must be one of: {', '.join(dict(self.ORDER_STATUS_CHOICES).keys())}"
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Run full validation
        self.full_clean()

        # Update product stock
        if self.pk:  # Existing order
            old_order = Order.objects.get(pk=self.pk)
            if old_order.quantity != self.quantity:
                stock_change = old_order.quantity - self.quantity
                self.product.stock_quantity += stock_change
                self.product.save()
        else:  # New order
            self.product.stock_quantity -= self.quantity
            self.product.save()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Restore stock when order is deleted
        self.product.stock_quantity += self.quantity
        self.product.save()
        super().delete(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.order_id} - {self.customer.name} - {self.product.name}"
