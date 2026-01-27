from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages

# from django.db import transaction
from customers.models import Customer
from customers.forms import CustomerCSVForm


from django.conf import settings
import os
import csv
import io
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
# Create your views here.

def import_customers_with_validation(decoded_data, error_log_path, encoding="utf-8", delete_existing=False):
    """
    Import customers with comprehensive validation and error logging
    """
    try:
        # ====== DELETE EXISTING CUSTOMERS IF REQUESTED ======
        customers_deleted = 0
        if delete_existing:
            try:
                # Get count before deletion
                customers_deleted = Customer.objects.count()

                # Delete all orders
                deleted_info = Customer.objects.all().delete()
                customers_deleted = deleted_info[0] if deleted_info else 0

                logger.info(f"Deleted {customers_deleted} existing customers before import")
            except Exception as delete_error:
                logger.error(f"Error deleting existing customers: {str(delete_error)}")
                return 0, 0, [f"Error clearing existing customers: {str(delete_error)}"]
            
        # Create StringIO object from decoded data
        io_string = io.StringIO(decoded_data)

        # Try to detect dialect
        sample = decoded_data[:1024]  # Read first 1024 chars
        sniffer = csv.Sniffer()

        try:
            dialect = sniffer.sniff(sample)
            delimiter = dialect.delimiter
            logger.info(f"Detected CSV delimiter: {repr(delimiter)}")
        except:
            delimiter = ","  # Default to comma
            logger.warning("Could not detect CSV delimiter, using comma")

        reader = csv.reader(io_string, delimiter=delimiter, quotechar='"')

        # Read header
        try:
            header = next(reader, None)
            if not header:
                return 0, 0, ["CSV file is empty or has no header"]
        except Exception as e:
            return 0, 0, [f"Error reading CSV header: {str(e)}"]

        # Log header info for debugging
        logger.info(f"CSV Header: {header}")
        logger.info(f"Number of columns: {len(header)}")

        # # Normalize header names (strip whitespace, lowercase)
        # normalized_header = [col.strip().lower() for col in header]
        # logger.info(f"Normalized Header: {normalized_header}")

        # Map column indices
        column_mapping = {}
        expected_columns = ["name", "email", "phone", "address"]

        # for i, col_name in enumerate(normalized_header):
        #     for expected in expected_columns:
        #         if expected in col_name or col_name in expected:
        #             column_mapping[expected] = i
        #             break

        # If no mapping found, assume standard order
        if not column_mapping:
            column_mapping = {
                expected: i for i, expected in enumerate(expected_columns)
            }

        logger.info(f"Column mapping: {column_mapping}")

        success_count = 0
        error_count = 0
        error_details = []
        error_log_content = []  # Store log lines in memory
        
        for row_num, row in enumerate(reader, start=2):  # start=2 because of header
                row_errors = []

                # Log raw row for debugging
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

                    # Log extracted data
                    error_log_content.append(f"  Extracted data: {data}\n")

                    # Validate using form
                    form = CustomerCSVForm(data)

                    if form.is_valid():
                        cleaned_data = form.cleaned_data

                        # Check for duplicate email
                        try:
                            if Customer.objects.filter(email=cleaned_data["email"]).exists():
                                customer = Customer.objects.get(email=cleaned_data["email"])
                                # Update existing customer
                                customer.name = cleaned_data["name"]
                                customer.phone = cleaned_data["phone"] or None
                                customer.address = data.get("address") or None
                                customer.save()
                                error_log_content.append(
                                    f"  ✅ UPDATED existing customer: {cleaned_data['email']}\n\n"
                                )
                            else:
                                # Create new customer
                                Customer.objects.create(
                                    name=cleaned_data["name"],
                                    email=cleaned_data["email"],
                                    phone=cleaned_data["phone"] or None,
                                    address=data.get("address") or None,
                                )
                                error_log_content.append(
                                    f"  ✅ CREATED new customer: {cleaned_data['email']}\n\n"
                                )

                            success_count += 1

                        except Exception as db_error:
                            error_count += 1
                            error_msg = (
                                f"Row {row_num}: Database Error - {str(db_error)}"
                            )
                            row_errors.append(error_msg)
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
            f"Customer Import Error Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
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

        # error_file.write(summary + content[len(summary) :])
        # Open error log file
        with open(error_log_path, "w", encoding="utf-8") as error_file:
            error_file.write(f"Customer Import Error Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            error_file.write("=" * 80 + "\n\n")
            error_file.write(f"Encoding: {encoding}\n")
            error_file.write(f"Delimiter: {repr(delimiter)}\n")
            error_file.write(f"Header: {header}\n")
            error_file.write(f"Column Mapping: {column_mapping}\n")
            error_file.write("-" * 80 + "\n\n")
            error_file.writelines(summary_lines)
            error_file.writelines(row_errors)
            error_file.writelines(error_log_content)            

        return success_count, error_count, error_details[:20]

    except Exception as e:
        logger.error(
            f"Error in import_customers_with_validation: {str(e)}", exc_info=True
        )
        # Create minimal error log
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"Fatal Error during import: {str(e)}\n")
        return 0, 0, [f"Fatal error: {str(e)}"]
