import pytest
from pydantic import ValidationError
import json

# Assuming schemas.py is in the parent directory or PYTHONPATH is set correctly
# If running pytest from the root directory, this import should work.
from schemas import (
    AllocationRequest,
    ProductInput,
    ChannelInput,
    InventoryInput,
    DemandInput,
    RevenueInput,
    OptimizationParameters # Import the new model
)

# --- Sample Valid Data ---

# Base data without parameters (for older tests)
BASE_VALID_PAYLOAD = {
    "products": [
        {"sku": "SKU001", "donation_eligible": True, "name": "Product A", "brand": "BrandX"},
        {"sku": "SKU002", "donation_eligible": False, "name": "Product B", "brand": "BrandY"}
    ],
    "channels": [
        {"id": "STORE1", "capacity": 100, "min_coverage": 0.8, "channel_type": "store"},
        {"id": "DONATE1", "capacity": 50, "min_coverage": 0.9, "channel_type": "donation"}
    ],
    "inventory": [
        {"product_sku": "SKU001", "quantity": 50},
        {"product_sku": "SKU002", "quantity": 30}
    ],
    "demand": [
        {"product_sku": "SKU001", "channel_id": "STORE1", "demand_quantity": 20},
        {"product_sku": "SKU002", "channel_id": "STORE1", "demand_quantity": 15}
    ],
    "revenue": [
        {"product_sku": "SKU001", "channel_id": "STORE1", "revenue_per_unit": 10.5},
        {"product_sku": "SKU002", "channel_id": "STORE1", "revenue_per_unit": 8.0},
    ]
}

# Payload including valid parameters
VALID_PAYLOAD_WITH_PARAMS = {
    "parameters": {
        "default_min_coverage": 0.75,
        "min_skus_per_store": 2,
        "restricted_brands_for_donation": ["BrandY"]
    },
    **BASE_VALID_PAYLOAD # Merge base data
}

# Payload with empty but valid parameters
VALID_PAYLOAD_EMPTY_PARAMS = {
    "parameters": {}, # Empty parameters object is valid
    **BASE_VALID_PAYLOAD
}


# --- Test Cases ---

def test_valid_payload_parsing_with_params():
    """Tests if a valid payload with parameters is parsed correctly."""
    try:
        request_data = AllocationRequest(**VALID_PAYLOAD_WITH_PARAMS)
        assert request_data.parameters.default_min_coverage == 0.75
        assert request_data.parameters.min_skus_per_store == 2
        assert request_data.parameters.restricted_brands_for_donation == ["BrandY"]
        # Check base data parsing too
        assert len(request_data.products) == 2
        assert request_data.channels[0].id == "STORE1"
    except ValidationError as e:
        pytest.fail(f"Valid payload with parameters failed validation: {e}")

def test_valid_payload_parsing_empty_params():
    """Tests if a valid payload with empty parameters is parsed correctly."""
    try:
        request_data = AllocationRequest(**VALID_PAYLOAD_EMPTY_PARAMS)
        assert request_data.parameters is not None
        assert request_data.parameters.default_min_coverage is None
        assert request_data.parameters.min_skus_per_store is None
        assert request_data.parameters.restricted_brands_for_donation is None
        assert len(request_data.products) == 2 # Check base data
    except ValidationError as e:
        pytest.fail(f"Valid payload with empty parameters failed validation: {e}")


# --- Original Test Cases (Need modification to include parameters) ---
# Note: The original tests might fail now as they lack the 'parameters' field.
# We should update them or create new ones based on VALID_PAYLOAD_WITH_PARAMS.
# For now, let's keep the original structure but use the new base payload.

def test_valid_payload_parsing():
    """Tests if a valid payload (now requiring params) is parsed correctly."""
    # This test now uses the payload with parameters
    try:
        request_data = AllocationRequest(**VALID_PAYLOAD_WITH_PARAMS) # Use payload with params
        # Basic checks to ensure base data is still parsed alongside params
        assert len(request_data.products) == 2
        assert request_data.products[0].sku == "SKU001"
        assert len(request_data.channels) == 2
        assert request_data.channels[1].channel_type == "donation"
        assert len(request_data.inventory) == 2
        assert request_data.inventory[1].quantity == 30
        assert len(request_data.demand) == 2
        assert request_data.demand[0].demand_quantity == 20
        assert len(request_data.revenue) == 2
        assert request_data.revenue[1].revenue_per_unit == 8.0
        # Check parameters are parsed
        assert request_data.parameters.default_min_coverage == 0.75
    except ValidationError as e:
        pytest.fail(f"Valid payload with parameters failed validation: {e}")

def test_missing_parameters_field():
    """Tests validation error when the entire 'parameters' field is missing."""
    invalid_payload = json.loads(json.dumps(BASE_VALID_PAYLOAD)) # Use base without params key
    with pytest.raises(ValidationError) as excinfo:
        AllocationRequest(**invalid_payload)
    # Check that the error message indicates the 'parameters' field is required/missing
    error_string = str(excinfo.value)
    assert "parameters" in error_string # Check for the field name itself
    assert "Field required" in error_string # Check for the specific error type text


def test_missing_required_field_in_base():
    """Tests validation error for missing required fields in base data (e.g., product sku)."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS)) # Deep copy
    del invalid_payload["products"][0]["sku"]
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)

def test_invalid_data_type_in_base():
    """Tests validation error for incorrect data types in base data (e.g., capacity as string)."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS)) # Deep copy
    invalid_payload["channels"][0]["capacity"] = "not-a-number"
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)

def test_negative_quantity_in_base():
    """Tests validation error for negative quantity in base data."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS)) # Deep copy
    invalid_payload["inventory"][0]["quantity"] = -10
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)

def test_invalid_coverage_ratio_in_base():
    """Tests validation error for coverage ratio outside [0, 1] in base data."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS)) # Deep copy
    invalid_payload["channels"][0]["min_coverage"] = 1.5
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)

def test_invalid_channel_type_in_base():
    """Tests validation error for unknown channel type in base data."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS)) # Deep copy
    invalid_payload["channels"][0]["channel_type"] = "warehouse" # Not in Literal
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)

def test_inventory_sku_not_in_products_with_params():
    """Tests validation error when inventory SKU doesn't exist in products list (with params)."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS)) # Deep copy
    invalid_payload["inventory"].append({"product_sku": "SKU999", "quantity": 5})
    with pytest.raises(ValidationError) as excinfo:
        AllocationRequest(**invalid_payload)
    assert "Inventory item SKU 'SKU999' not found in products list" in str(excinfo.value)

def test_demand_channel_not_in_channels_with_params():
    """Tests validation error when demand channel ID doesn't exist in channels list (with params)."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS)) # Deep copy
    invalid_payload["demand"].append({"product_sku": "SKU001", "channel_id": "STORE99", "demand_quantity": 10})
    with pytest.raises(ValidationError) as excinfo:
        AllocationRequest(**invalid_payload)
    assert "Demand item Channel ID 'STORE99' not found in channels list" in str(excinfo.value)

def test_revenue_product_not_in_products_with_params():
    """Tests validation error when revenue product SKU doesn't exist in products list (with params)."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS)) # Deep copy
    invalid_payload["revenue"].append({"product_sku": "SKU888", "channel_id": "STORE1", "revenue_per_unit": 5.0})
    with pytest.raises(ValidationError) as excinfo:
        AllocationRequest(**invalid_payload)
    assert "Revenue item SKU 'SKU888' not found in products list" in str(excinfo.value)


# --- Tests specific to OptimizationParameters ---

def test_invalid_parameter_type():
    """Tests validation error for incorrect data type in parameters."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS))
    invalid_payload["parameters"]["min_skus_per_store"] = "two" # Should be integer
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)

def test_invalid_parameter_value_coverage():
    """Tests validation error for parameter value outside allowed range (coverage)."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS))
    invalid_payload["parameters"]["default_min_coverage"] = 1.1 # Max is 1.0
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)

def test_invalid_parameter_value_skus():
    """Tests validation error for parameter value outside allowed range (min skus)."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS))
    invalid_payload["parameters"]["min_skus_per_store"] = -1 # Min is 0
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)

def test_invalid_parameter_value_brands():
    """Tests validation error for invalid type in restricted brands list."""
    invalid_payload = json.loads(json.dumps(VALID_PAYLOAD_WITH_PARAMS))
    invalid_payload["parameters"]["restricted_brands_for_donation"] = ["BrandY", 123] # Should be list of strings
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)
