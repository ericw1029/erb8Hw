from django.contrib import admin
from .models import Product
# Register your models here.


class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_id",
        "name",
        "sku",
        "description",
        "price",
        "stock_quantity",
        "weight",
        "created_at",
    )
    list_display_links = ("product_id", "name")
    search_fields = ("name", "sku", "description")
    list_per_page = 25


admin.site.register(Product, ProductAdmin)
