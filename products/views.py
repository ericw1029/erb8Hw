
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages

# from django.db import transaction
from products.models import Product
from products.forms import ProductCSVForm

from pages.helper import parse_numeric_string
from pages.helper import format_currency

from django.conf import settings
import os
import csv
import io
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def validate_sku_format(sku):
    """Validate SKU format"""
    import re

    if not re.match(r"^[a-zA-Z0-9\-_]+$", sku):
        return (
            False,
            "SKU can only contain letters, numbers, hyphens (-), and underscores (_)",
        )
    if len(sku) > 50:
        return False, "SKU cannot exceed 50 characters"
    if len(sku) == 0:
        return False, "SKU cannot be empty"
    return True, ""

def import_products_with_validation(decoded_data, error_log_path, encoding="utf-8",delete_existing=False):
    """
    Import products with comprehensive validation and error logging
    """
    try:
        # ====== DELETE EXISTING PRODUCTS IF REQUESTED ======
        products_deleted = 0
        if delete_existing:
            try:
                # Get count before deletion
                products_deleted = Product.objects.count()

                # Delete all orders
                deleted_info = Product.objects.all().delete()
                products_deleted = deleted_info[0] if deleted_info else 0

                logger.info(
                    f"Deleted {products_deleted} existing products before import"
                )
            except Exception as delete_error:
                logger.error(f"Error deleting existing products: {str(delete_error)}")
                return 0, 0, [f"Error clearing existing products: {str(delete_error)}"]
            
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
                return 0, 0, ["CSV file is empty or has no header"]
        except Exception as e:
            return 0, 0, [f"Error reading CSV header: {str(e)}"]

        # Log header info
        logger.info(f"Product CSV Header: {header}")
        logger.info(f"Number of columns: {len(header)}")

        # # Normalize header names
        # normalized_header = [col.strip().lower() for col in header]
        # logger.info(f"Normalized Header: {normalized_header}")

        # Map column indices (flexible column mapping)
        column_mapping = {}
        expected_columns = ["name","sku","description","price","stock_quantity","weight",]

       
        # If no mapping found, assume standard order
        if not column_mapping:
            column_mapping = {
                expected: i
                for i, expected in enumerate(expected_columns[: len(header)])
            }

        logger.info(f"Product Column mapping: {column_mapping}")

        success_count = 0
        error_count = 0
        error_details = []
        error_log_content = []  # Store log lines in memory
        
        for row_num, row in enumerate(reader, start=2):
            print("product row num",row_num)
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

                # Special handling for numeric fields
                # Convert empty strings to None for optional fields
                if data.get("weight", "").strip() == "":
                    data["weight"] = ""

                # Convert numeric fields, handle commas as thousands separators
                for field in ["price", "stock_quantity", "weight"]:
                    if field in data and data[field]:
                        # Remove currency symbols, commas, and whitespace
                        value_str = str(data[field]).strip()
                        value_str = (
                            value_str.replace("$", "").replace("€", "").replace("£", "")
                        )
                        value_str = value_str.replace(",", "")

                        try:
                            if field == "stock_quantity":
                                # Remove decimal for integer
                                if "." in value_str:
                                    value_str = value_str.split(".")[0]
                                data[field] = int(value_str) if value_str else 0
                            elif field in ["price", "weight"]:
                                data[field] = float(value_str) if value_str else ""
                        except ValueError:
                            # Keep original for validation error
                            pass

                # ====== USE HELPER 1: Parse numeric fields ======
                try:
                    # Parse price using helper
                    if data.get("price"):
                        data["price"] = parse_numeric_string(data["price"], "float")
                    else:
                        data["price"] = 0.0
                except ValueError as e:
                    row_errors.append(f"Invalid price format: {str(e)}")
                    data["price"] = data.get(
                        "price", ""
                    )  # Keep original for error display

                try:
                    # Parse stock quantity using helper
                    if data.get('stock_quantity'):
                        data['stock_quantity'] = parse_numeric_string(data['stock_quantity'], 'int')
                    else:
                        data['stock_quantity'] = 0
                except ValueError as e:
                    row_errors.append(f"Invalid stock quantity format: {str(e)}")
                    data['stock_quantity'] = data.get('stock_quantity', '')
                    
                try:
                    # Parse weight using helper (optional field)
                    if data.get('weight') and str(data['weight']).strip():
                        data['weight'] = parse_numeric_string(data['weight'], 'float')
                    else:
                        data['weight'] = None  # Set to None for optional field
                except ValueError as e:
                    row_errors.append(f"Invalid weight format: {str(e)}")
                    print("weight",row_errors)
                    data['weight'] = data.get('weight', '')
                    
                
                # ====== USE HELPER 2: Validate SKU format ======
                sku_value = data.get('sku', '')
                if sku_value:
                    sku_valid, sku_error_msg = validate_sku_format(sku_value)
                    if not sku_valid:
                        row_errors.append(sku_error_msg)
                
                # If we already have errors from helper functions, skip form validation
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
                form = ProductCSVForm(data)

                if form.is_valid():
                    cleaned_data = form.cleaned_data

                    try:
                        # Check for duplicate SKU
                        print(cleaned_data["sku"]);
                        if Product.objects.filter(sku=cleaned_data["sku"]).exists():
                            product = Product.objects.get(sku=cleaned_data["sku"])

                            # Check if we should update or skip
                            update_existing = True  # You can make this configurable

                            if update_existing:
                                # Update existing product
                                product.name = cleaned_data["name"]
                                product.description = (cleaned_data.get("description") or "")
                                product.price = cleaned_data["price"]
                                product.stock_quantity = cleaned_data["stock_quantity"]
                                product.weight = cleaned_data.get("weight")
                                product.save()
                                error_log_content.append(f"  ✅ UPDATED existing product: {cleaned_data['sku']}\n\n")
                            else:
                                error_log_content.append(f"  ⚠️ SKIPPED duplicate SKU: {cleaned_data['sku']}\n\n")
                                error_count += 1
                                error_details.append(f"Row {row_num}: Duplicate SKU - {cleaned_data['sku']}")
                                continue
                        else:
                            # Create new product
                            Product.objects.create(
                                name=cleaned_data["name"],
                                sku=cleaned_data["sku"],
                                description=cleaned_data.get("description") or "",
                                price=cleaned_data["price"],
                                stock_quantity=cleaned_data["stock_quantity"],
                                weight=cleaned_data.get("weight"),
                            )
                            error_log_content.append(f"  ✅ CREATED new product: {cleaned_data['sku']}\n\n")
                            
                        #print("error_log_content", error_log_content)
                        success_count += 1

                    except Exception as db_error:
                        error_count += 1
                        error_msg = f"Row {row_num}: Database Error - {str(db_error)}"
                        row_errors.append(error_msg)
                        error_details.append(error_msg)
                        error_log_content.append(f"  ❌ DATABASE ERROR: {str(db_error)}\n")
                        error_log_content.append(f"     Data: {cleaned_data}\n\n")

                else:
                    # Collect all form errors
                    error_count += 1
                    for field, field_errors in form.errors.items():
                        for error in field_errors:
                            error_msg = f"Row {row_num}: {field.capitalize()} - {error}"
                            row_errors.append(error_msg)
                            error_details.append(error_msg)

                    # Write detailed errors to log file
                    error_log_content.append(f"  ❌ VALIDATION FAILED:\n")
                    for field, field_errors in form.errors.items():
                        for error in field_errors:
                            error_log_content.append(f"     • {field}: {error}\n")
                    error_log_content.append(f"     Raw data: {data}\n\n")

            except Exception as e:
                error_count += 1
                error_msg = f"Row {row_num}: Processing Error - {str(e)}"
                row_errors.append(error_msg)
                error_details.append(error_msg)
                error_log_content.append(f"  ❌ PROCESSING ERROR: {str(e)}\n")
                error_log_content.append(f"     Raw row: {row}\n\n")

        # Update summary
        total_rows = row_num - 1 if "row_num" in locals() else 0
        
        # Create summary
        summary_lines = [
            f"Product Import Error Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            "=" * 80 + "\n\n",
            f"Encoding: {encoding}\n",
            f"Delimiter: {repr(delimiter)}\n",
            f"Total rows processed: {total_rows}\n",
            f"Successful: {success_count}\n",
            f"Failed: {error_count}\n",
            f"Success rate: {(success_count / max(total_rows, 1) * 100):.1f}%\n",
            f"Duplicates handled: {'Update existing'}\n",
            "-" * 80 + "\n\n",
        ]
        
        
        # Open error log file
        with open(error_log_path, "w", encoding="utf-8") as error_file:
            error_file.write(f"Product Import Error Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            error_file.write("=" * 80 + "\n\n")
            error_file.write(f"Encoding: {encoding}\n")
            error_file.write(f"Delimiter: {repr(delimiter)}\n")
            error_file.write(f"Header: {header}\n")
            error_file.write(f"Column Mapping: {column_mapping}\n")
            error_file.write("-" * 80 + "\n\n")     
            error_file.writelines(summary_lines)
            error_file.writelines(row_errors)
            error_file.writelines(error_log_content)
            #error_file.write(summary + content[len(summary) :])

        return success_count, error_count, error_details[:20]

    except Exception as e:
        logger.error(
            f"Error in import_products_with_validation: {str(e)}", exc_info=True
        )
        # Create minimal error log
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"Fatal Error during product import: {str(e)}\n")
        return 0, 0, [f"Fatal error: {str(e)}"]
