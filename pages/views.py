# views.py
from django.shortcuts import render, redirect
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from django.contrib import messages
#from django.db import transaction
from customers.models import Customer
from customers.views import import_customers_with_validation

from products.models import Product
from products.views import import_products_with_validation

from orders.models import Order
from orders.views import import_orders_with_validation

from .forms import CSVImportForm#, OrderCSVForm  # , CustomerCSVForm,ProductCSVForm,

from django.conf import settings
import os
import csv
import io
from datetime import datetime
import logging

logger = logging.getLogger(__name__)



def import_csv(request):
    if request.method == "POST":
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            model_type = form.cleaned_data["model_type"]
            delete_option = form.cleaned_data.get("delete_option", "append")
            delete_existing = delete_option == "replace"

            # Validate file type
            if not csv_file.name.endswith(".csv"):
                messages.error(request, "Please upload a CSV file (.csv extension)")
                return render(request, "pages/index.html", {"form": form})
            
            try:
                file_size = csv_file.size
                #file_name = csv_file.name

                if file_size == 0:
                    messages.error(request, "Uploaded file is empty")
                    return render(request, "csv_import.html", {"form": form})
                
                # Decode and read CSV
                data_set = csv_file.read().decode("UTF-8")
                #io_string = io.StringIO(data_set)
                
                
                # Try multiple encodings
                encodings_to_try = ["utf-8","utf-8-sig","latin-1","iso-8859-1","cp1252",]
                decoded_data = None
                encoding_used = None
                
                for encoding in encodings_to_try:
                    try:
                        csv_file.seek(0)  # Reset file pointer
                        decoded_data = csv_file.read().decode(encoding)
                        encoding_used = encoding
                        logger.info(f"Successfully decoded with {encoding}")
                        break
                    except UnicodeDecodeError as e:
                        logger.warning(f"Failed to decode with {encoding}: {str(e)}")
                        continue

                if decoded_data is None:
                    messages.error(
                        request, "Unable to decode the file. Please use UTF-8 encoding."
                    )
                    return render(request, "pages/index.html", {"form": form})

                # Create error log directory if it doesn't exist
                error_log_dir = os.path.join(settings.BASE_DIR, "error_logs")
                os.makedirs(error_log_dir, exist_ok=True)

                # Generate error log filename with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                error_log_filename = f"import_errors_{model_type}_{timestamp}.txt"
                error_log_path = os.path.join(error_log_dir, error_log_filename)

                success_count = 0
                error_count = 0
                errors = []

                # Process based on model type
                if model_type == "customer":
                    success_count, error_count, errors = (
                        import_customers_with_validation(decoded_data, error_log_path, encoding_used, delete_existing)
                    )
                    #success_count, error_count, errors = import_customers_with_validation(io_string, error_log_path)
                elif model_type == "product":
                    success_count, error_count, errors = (
                        import_products_with_validation(decoded_data, error_log_path, encoding_used, delete_existing)
                    )
                    #success_count, error_count, errors = import_products(io_string)
                elif model_type == "order":
                    success_count, error_count, errors = import_orders_with_validation(decoded_data, error_log_path, encoding_used, delete_existing)
                    #success_count, error_count, errors = import_orders(io_string)

                # Prepare response message
                if error_count == 0:
                    messages.success(
                        request,
                        f"✅ Successfully imported {success_count} {model_type} records!",
                    )
                else:
                    messages.warning(
                        request,
                        f"⚠️ Import completed with {success_count} successful and {error_count} failed records. "
                        f"Error log saved to: {error_log_filename}",
                    )
                    print("error_log_filename->", error_log_filename)
                    # Provide download link for error log
                    error_log_url = f"/download-error-log/{error_log_filename}/"
                    messages.info(
                        request,
                        mark_safe("<span><a href='"+error_log_url+"' target='_blank'>📄 Download Error Log</a></span>"),
                    )

                return render(request, "pages/index.html", {"form": form})

            except Exception as e:
                logger.error(f"CSV import error: {str(e)}")
                messages.error(request, f"❌ Error importing CSV: {str(e)}")
    else:
        form = CSVImportForm()

    return render(request, "pages/index.html", {"form": form})

def download_error_log(request, filename):
    """
    View to download error log files
    """
    error_log_dir = os.path.join(settings.BASE_DIR, "error_logs")
    file_path = os.path.join(error_log_dir, filename)

    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            response = HttpResponse(f.read(), content_type="text/plain")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
    else:
        return HttpResponse("Error log file not found", status=404)

def export_csv(request,model_type):
    if model_type == "customer":
        return export_customers_csv()
    elif model_type == "product":
        return export_products_csv()
    elif model_type == "order":
        return export_orders_csv()
    else:
        return HttpResponse("Invalid model type", status=400)

def export_customers_csv():
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="customers.csv"'

    writer = csv.writer(response)
    writer.writerow(["name", "email", "phone", "address"])

    customers = Customer.objects.all()
    for customer in customers:
        writer.writerow(
            [
                customer.name,
                customer.email,
                customer.phone or "",
                customer.address or "",
            ]
        )

    return response

def export_products_csv():
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="products.csv"'

    writer = csv.writer(response)
    writer.writerow(["name", "sku", "description", "price", "stock_quantity", "weight"])

    products = Product.objects.all()
    for product in products:
        writer.writerow(
            [
                product.name,
                product.sku,
                product.description or "",
                product.price,
                product.stock_quantity,
                product.weight or "",
            ]
        )

    return response

def export_orders_csv():
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="orders.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "customer_email",
            "product_sku",
            "quantity",
            "order_date",
            "status",
            "total_amount",
        ]
    )

    orders = Order.objects.select_related("customer", "product").all()
    for order in orders:
        writer.writerow(
            [
                order.customer.email,
                order.product.sku,
                order.quantity,
                order.order_date.strftime("%Y-%m-%d %H:%M:%S"),
                order.status,
                order.total_amount,
            ]
        )

    return response

def debug_csv_upload(request):
    
    """Debug view to test CSV uploads"""
    if request.method == "POST" and "csv_file" in request.FILES:
        csv_file = request.FILES["csv_file"]

        debug_info = {
            "file_name": csv_file.name,
            "file_size": csv_file.size,
            "content_type": csv_file.content_type,
        }

        # Try different encodings
        encodings = ["utf-8", "utf-8-sig", "latin-1", "iso-8859-1", "cp1252"]

        for encoding in encodings:
            try:
                csv_file.seek(0)
                content = csv_file.read().decode(encoding)
                debug_info[f"encoding_{encoding}"] = "SUCCESS"
                debug_info[f"content_sample_{encoding}"] = content[:500]

                # Try to parse as CSV
                import csv

                io_string = io.StringIO(content)
                reader = csv.reader(io_string)
                try:
                    header = next(reader)
                    debug_info[f"csv_header_{encoding}"] = header
                except:
                    debug_info[f"csv_header_{encoding}"] = "ERROR"

            except Exception as e:
                debug_info[f"encoding_{encoding}"] = f"FAILED: {str(e)}"

        return render(request, "pages/debug_csv.html", {"debug_info": debug_info})

    return render(request, "pages/debug_csv.html")

def index(request):
    return render(request, "pages/index.html")