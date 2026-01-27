from django.contrib import admin
from .models import Customer
# Register your models here.


class CustomerAdmin(admin.ModelAdmin):
    list_display = ("customer_id", "name", "email", "phone", "address", "created_at")
    list_display_links = ("customer_id", "name")
    search_fields = ("name", "email", "phone")
    list_per_page = 25


admin.site.register(Customer, CustomerAdmin)
