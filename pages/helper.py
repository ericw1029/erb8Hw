# additional helper
# ******************************************************************************************************************************************
def parse_numeric_string(value_str, field_type="float"):
    """
    Parse numeric strings with error handling for currency and formatting
    """
    if value_str is None:
        return None if field_type == "float" else 0

    value_str = str(value_str).strip()

    # If empty string after stripping
    if not value_str:
        return None if field_type == "float" else 0

    # Remove common currency symbols and thousands separators
    value_str = value_str.replace("$", "").replace("€", "").replace("£", "")
    value_str = value_str.replace(",", "").replace(" ", "")

    try:
        if field_type == "int":
            # For integers, remove decimal part if present
            if "." in value_str:
                value_str = value_str.split(".")[0]
            return int(value_str) if value_str else 0
        else:
            # For floats
            return float(value_str) if value_str else 0.0
    except ValueError as e:
        raise ValueError(f"Invalid numeric value '{value_str}': {str(e)}")


def format_currency(value):
    """Format price for display in error messages"""
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)


def generate_product_summary(products_data):
    """Generate import summary statistics"""
    if not products_data:
        return {}

    total_price = sum(float(p.get("price", 0)) for p in products_data)
    total_stock = sum(int(p.get("stock_quantity", 0)) for p in products_data)
    total_weight = sum(
        float(p.get("weight", 0)) for p in products_data if p.get("weight")
    )

    return {
        "count": len(products_data),
        "total_price": total_price,
        "total_stock": total_stock,
        "total_weight": total_weight,
        "avg_price": total_price / len(products_data) if products_data else 0,
    }


# ******************************************************************************************************************************************
