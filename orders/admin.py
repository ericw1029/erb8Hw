from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Order
# Register your models here.


class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "customer",
        "product",
        "quantity",
        "order_date",
        "status",
        "order_date",
    )
    list_display_links = ("order_id", "customer", "product")
    search_fields = ("name", "customer__name", "product__sku", "order_date")
    list_per_page = 25


admin.site.register(Order, OrderAdmin)