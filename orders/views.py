from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages

# from django.db import transaction
from .models import Order
from .forms import OrderCSVForm

from customers.models import Customer
from products.models import Product

from pages.helper import parse_numeric_string
from pages.helper import format_currency


from django.conf import settings
import os
import csv
import io
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
# Create your views here.
def import_orders_with_validation(
    decoded_data, error_log_path, encoding="utf-8", delete_existing=False
):
    """
    Import orders with comprehensive validation and error logging
    Includes option to delete existing orders before import
    """
    try:
        # ====== DELETE EXISTING ORDERS IF REQUESTED ======
        orders_deleted = 0
        if delete_existing:
            try:
                # Get count before deletion
                orders_deleted = Order.objects.count()

                # Restore stock for all orders before deletion
                for order in Order.objects.all():
                    order.product.stock_quantity += order.quantity
                    order.product.save()

                # Delete all orders
                deleted_info = Order.objects.all().delete()
                orders_deleted = deleted_info[0] if deleted_info else 0

                logger.info(f"Deleted {orders_deleted} existing orders before import")
            except Exception as delete_error:
                logger.error(f"Error deleting existing orders: {str(delete_error)}")
                return 0, 0, [f"Error clearing existing orders: {str(delete_error)}"]

        # Create StringIO object from decoded data
        io_string = io.StringIO(decoded_data)
        # Try to detect dialect
        sample = decoded_data[:1024]
        sniffer = csv.Sniffer()

        try:
            dialect = sniffer.sniff(sample)
            delimiter = dialect.delimiter
            logger.info(f"Detected CSV delimiter: {repr(delimiter)}")
        except:
            delimiter = ","
            logger.warning("Could not detect CSV delimiter, using comma")

        reader = csv.reader(io_string, delimiter=delimiter, quotechar='"')

        # Read header
        try:
            header = next(reader, None)
            if not header:
                error_msg = "CSV file is empty or has no header"
                if delete_existing and orders_deleted > 0:
                    error_msg += f" (NOTE: {orders_deleted} existing orders were already deleted!)"
                return 0, 0, [error_msg]
        except Exception as e:
            error_msg = f"Error reading CSV header: {str(e)}"
            if delete_existing and orders_deleted > 0:
                error_msg += (
                    f" (NOTE: {orders_deleted} existing orders were already deleted!)"
                )
            return 0, 0, [error_msg]

       
        # Map column indices with flexible column mapping
        column_mapping = {}
        expected_columns = ["customer_email","product_sku","quantity","order_date","status","total_amount",]

        # If no mapping found, assume standard order
        if not column_mapping:
            column_mapping = {
                expected: i
                for i, expected in enumerate(expected_columns[: len(header)])
            }

        logger.info(f"Order Column mapping: {column_mapping}")

        success_count = 0
        error_count = 0
        error_details = []
        error_log_content = []  # Store log lines in memory
        imported_orders = []
        total_order_value = 0
        
        for row_num, row in enumerate(reader, start=2):
                
                row_errors = []

                # Log raw row
                error_log_content.append(f"Row {row_num}: {row}\n")

                # Check for empty row
                if not row or not any(cell and str(cell).strip() for cell in row):
                    error_log_content.append(f"  [SKIPPED] Empty row\n\n")
                    error_count += 1
                    error_details.append(f"Row {row_num}: Empty row")
                    continue

                try:
                    # Extract data based on column mapping
                    data = {}
                    for field, col_index in column_mapping.items():
                        if col_index < len(row):
                            value = row[col_index]
                            if value is not None:
                                data[field] = str(value).strip()
                            else:
                                data[field] = ""
                        else:
                            data[field] = ""

                    # Ensure all fields are present
                    for field in expected_columns:
                        if field not in data:
                            data[field] = ""

                    # Parse numeric fields
                    try:
                        # Parse quantity
                        if data.get("quantity"):
                            data["quantity"] = parse_numeric_string(data["quantity"], "int")
                        else:
                            data["quantity"] = 0
                    except ValueError as e:
                        row_errors.append(f"Invalid quantity format: {str(e)}")

                    try:
                        # Parse total amount
                        if data.get("total_amount"):
                            data["total_amount"] = parse_numeric_string(data["total_amount"], "float")
                        else:
                            data["total_amount"] = 0.0
                    except ValueError as e:
                        row_errors.append(f"Invalid total amount format: {str(e)}")

                    # If we already have errors from parsing, skip form validation
                    if row_errors:
                        error_count += 1
                        for error in row_errors:
                            error_details.append(f"Row {row_num}: {error}")
                        error_log_content.append(f"  ❌ PRE-VALIDATION ERRORS:\n")
                        for error in row_errors:
                            error_log_content.append(f"     • {error}\n")
                        error_log_content.append(f"     Raw data: {data}\n\n")
                        continue

                    # Log extracted data
                    error_log_content.append(f"  Extracted data: {data}\n")

                    # Validate using form
                    form = OrderCSVForm(data)

                    if form.is_valid():
                        cleaned_data = form.cleaned_data
                        try:
                            # Get customer and product
                            try:
                                customer = Customer.objects.get(email=cleaned_data["customer_email"])
                                
                                print("form.is_valid customer", customer)
                            except Customer.DoesNotExist:
                                row_errors.append(f"Customer with email '{cleaned_data['customer_email']}' not found")
                                raise ValueError(f"Customer not found")

                            try:
                                product = Product.objects.get(sku=cleaned_data["product_sku"])
                                print("form.is_valid product", product)
                            except Product.DoesNotExist:
                                row_errors.append(
                                    f"Product with SKU '{cleaned_data['product_sku']}' not found"
                                )
                                raise ValueError(f"Product not found")

                            # Check stock availability
                            if cleaned_data["quantity"] > product.stock_quantity:
                                print("form.is_valid quantity", cleaned_data["quantity"])
                                row_errors.append(f"Insufficient stock for '{product.name}'. "
                                    f"Requested: {cleaned_data['quantity']}, Available: {product.stock_quantity}"
                                )
                                raise ValueError(f"Insufficient stock")

                            # Check if order already exists (by customer, product, date, quantity)
                            existing_order = Order.objects.filter(
                                                                customer=customer,
                                                                product=product,
                                                                order_date=cleaned_data["order_date"],
                                                                quantity=cleaned_data["quantity"],
                                                            ).first()
                            
                            print("form.is_valid existing_order", existing_order)
                            
                            if existing_order:
                                print("order exist row", row)
                                # Update existing order
                                existing_order.status = cleaned_data["status"]
                                existing_order.total_amount = cleaned_data[
                                    "total_amount"
                                ]
                                existing_order.save()

                                error_log_content.append(f"  ✅ UPDATED existing order for {customer.email}\n")
                                error_log_content.append(f"     Product: {product.name}, Quantity: {cleaned_data['quantity']}\n")
                                error_log_content.append(f"     Total: {format_currency(cleaned_data['total_amount'])}\n\n")

                                imported_orders.append(
                                    {
                                        "order_id": existing_order.order_id,
                                        "customer": customer.email,
                                        "product": product.sku,
                                        "quantity": cleaned_data["quantity"],
                                        "total": cleaned_data["total_amount"],
                                        "action": "updated",
                                    }
                                )
                            else:
                                print("order create row", row)
                                # Create new order
                                order = Order.objects.create(
                                    customer=customer,
                                    product=product,
                                    quantity=cleaned_data["quantity"],
                                    order_date=cleaned_data["order_date"],
                                    status=cleaned_data["status"],
                                    total_amount=cleaned_data["total_amount"],
                                )

                                error_log_content.append(f"  ✅ CREATED new order #{order.order_id} for {customer.email}\n")
                                error_log_content.append(f"     Product: {product.name}, Quantity: {cleaned_data['quantity']}\n")
                                error_log_content.append(f"     Total: {format_currency(cleaned_data['total_amount'])}\n\n")

                                imported_orders.append(
                                    {
                                        "order_id": order.order_id,
                                        "customer": customer.email,
                                        "product": product.sku,
                                        "quantity": cleaned_data["quantity"],
                                        "total": cleaned_data["total_amount"],
                                        "action": "created",
                                    }
                                )

                            success_count += 1
                            total_order_value += float(cleaned_data["total_amount"])

                        except ValueError as e:
                            error_count += 1
                            for error in row_errors:
                                error_msg = f"Row {row_num}: {error}"
                                error_details.append(error_msg)

                            error_log_content.append(f"  ❌ VALIDATION ERROR: {str(e)}\n")
                            for error in row_errors:
                                error_log_content.append(f"     • {error}\n")
                            error_log_content.append(f"     Data: {cleaned_data}\n\n")

                        except Exception as db_error:
                            error_count += 1
                            error_msg = (
                                f"Row {row_num}: Database Error - {str(db_error)}"
                            )
                            error_details.append(error_msg)
                            error_log_content.append(f"  ❌ DATABASE ERROR: {str(db_error)}\n")
                            error_log_content.append(f"     Data: {cleaned_data}\n\n")

                    else:
                        # Collect all form errors
                        error_count += 1
                        for field, field_errors in form.errors.items():
                            for error in field_errors:
                                error_msg = (
                                    f"Row {row_num}: {field.capitalize()} - {error}"
                                )
                                row_errors.append(error_msg)
                                error_details.append(error_msg)

                        # Write detailed errors to log file
                        error_log_content.append(f"  ❌ FORM VALIDATION FAILED:\n")
                        for field, field_errors in form.errors.items():
                            for error in field_errors:
                                error_log_content.append(f"     • {field}: {error}\n")
                        error_log_content.append(f"     Raw data: {data}\n\n")

                except Exception as e:
                    error_count += 1
                    error_msg = f"Row {row_num}: Processing Error - {str(e)}"
                    error_details.append(error_msg)
                    error_log_content.append(f"  ❌ PROCESSING ERROR: {str(e)}\n")
                    error_log_content.append(f"     Raw row: {row}\n\n")

        # Calculate statistics
        total_rows = row_num - 1 if "row_num" in locals() else 0
        total_items = sum(order["quantity"] for order in imported_orders)
        created_count = len([o for o in imported_orders if o["action"] == "created"])
        updated_count = len([o for o in imported_orders if o["action"] == "updated"])

        # Open error log file
        with open(error_log_path, "w", encoding="utf-8") as error_file:
            # Write import summary header
            error_file.write(f"Order Import Error Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            error_file.write("=" * 80 + "\n\n")
            error_file.write(f"Encoding: {encoding}\n")
            error_file.write(f"Delimiter: {repr(delimiter)}\n")
            if delete_existing:
                error_file.write(f"IMPORT MODE: REPLACE (Deleted {orders_deleted} existing orders)\n")
            else:
                error_file.write(f"IMPORT MODE: APPEND\n")
            error_file.write(f"Header: {header}\n")
            error_file.write(f"Column Mapping: {column_mapping}\n")
            error_file.write("-" * 80 + "\n\n")

            summary = f"Order Import Error Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            summary += "=" * 80 + "\n\n"
            summary += f"IMPORT SUMMARY\n"
            summary += f"{'-' * 40}\n"
            summary += f"Encoding: {encoding}\n"
            summary += f"Delimiter: {repr(delimiter)}\n"

            if delete_existing:
                summary += f"Import Mode: REPLACE\n"
                summary += f"Existing orders deleted: {orders_deleted}\n"
            else:
                summary += f"Import Mode: APPEND\n"

            summary += f"\nPROCESSING RESULTS:\n"
            summary += f"Total rows in CSV: {total_rows}\n"
            summary += f"Successfully processed: {success_count}\n"
            summary += f"Failed to process: {error_count}\n"
            summary += (
                f"Success rate: {(success_count / max(total_rows, 1) * 100):.1f}%\n\n"
            )

            summary += f"IMPORT DETAILS:\n"
            summary += f"  • New orders created: {created_count}\n"
            summary += f"  • Existing orders updated: {updated_count}\n"
            summary += f"  • Total items ordered: {total_items}\n"
            summary += f"  • Total order value: {format_currency(total_order_value)}\n"
            summary += f"  • Average order value: {format_currency(total_order_value / max(success_count, 1))}\n"

            if imported_orders:
                # Find top products
                product_counts = {}
                for order in imported_orders:
                    product_counts[order["product"]] = (
                        product_counts.get(order["product"], 0) + order["quantity"]
                    )

                if product_counts:
                    top_product = max(product_counts.items(), key=lambda x: x[1])
                    summary += f"  • Most ordered product: {top_product[0]} ({top_product[1]} units)\n"

            summary += "\n" + "-" * 80 + "\n\n"
            
            error_file.writelines(error_details)
            error_file.writelines(error_log_content)

            # error_file.write(summary + content[len(summary) :])

        return success_count, error_count, error_details[:20]

    except Exception as e:
        logger.error(f"Error in import_orders_with_validation: {str(e)}", exc_info=True)
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"Fatal Error during order import: {str(e)}\n")
            if delete_existing and orders_deleted > 0:
                f.write(
                    f"\nWARNING: {orders_deleted} existing orders were deleted but import failed!\n"
                )
        return 0, 0, [f"Fatal error: {str(e)}"]
