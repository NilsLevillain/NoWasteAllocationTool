import pytest
from pydantic import ValidationError
import json
from datetime import datetime

# Corrected import path
from backend.schemas import (
    AllocationRequest,
    ProductInput,
    ChannelInput,
    InventoryInput,
    DemandInput,
    OptimizationParameters,
    CoverageDaysRule,
    OutletSKUCapacityRule,
    OutletAssortmentRule,
    PushNewSKURule
)

# --- Sample Valid Data for New Schemas ---

VALID_PRODUCT_INPUT = {
    "sku": "SKU001",
    "donation_eligible": True,
    "name": "Product A",
    "brand": "BrandX",
    "division": "DivA",
    "axe": "Axe1",
    "subaxis": "Sub1",
    "metier": "MetA",
    "abc_class": "A",
    "cogs": 10.5
}

VALID_CHANNEL_INPUT = {
    "id": "STORE1",
    "capacity": 100,
    "channel_type": "store"
}

VALID_INVENTORY_INPUT = {
    "product_sku": "SKU001",
    "quantity": 50
}

VALID_DEMAND_INPUT = {
    "product_sku": "SKU001",
    "channel_id": "STORE1",
    "demand_quantity": 20
}

VALID_COVERAGE_RULE = {
    "channel_id": "STORE1",
    "abc_class": "A",
    "coverage_days": 7
}

VALID_OUTLET_CAPACITY_RULE = {
    "channel_id": "OUTLET1",
    "division": "DivA",
    "axe": "Axe1",
    "max_skus": 50
}

VALID_OUTLET_ASSORTMENT_RULE = {
    "metier": "MetA",
    "subaxis": "Sub1",
    "brand": "BrandX",
    "max_skus": 10
}

VALID_PUSH_NEW_SKU_RULE = {
    "division": "DivA",
    "subaxis": "Sub1",
    "push_quantity": 20
}

VALID_OPTIMIZATION_PARAMETERS = {
    "seasonality_coefficient": 1.0,
    "restricted_brands_for_donation": ["BrandY"],
    "coverage_days_rules": [VALID_COVERAGE_RULE],
    "outlet_sku_capacity_rules": [VALID_OUTLET_CAPACITY_RULE],
    "outlet_assortment_rules": [VALID_OUTLET_ASSORTMENT_RULE],
    "push_new_sku_rules": [VALID_PUSH_NEW_SKU_RULE]
}

VALID_ALLOCATION_REQUEST_PAYLOAD = {
    "parameters": VALID_OPTIMIZATION_PARAMETERS,
    "products": [VALID_PRODUCT_INPUT],
    "channels": [VALID_CHANNEL_INPUT, {"id": "OUTLET1", "capacity": 200, "channel_type": "outlet"}],
    "inventory": [VALID_INVENTORY_INPUT],
    "demand": [VALID_DEMAND_INPUT]
}

# --- Test Cases for Individual Schemas ---

def test_product_input_valid():
    product = ProductInput(**VALID_PRODUCT_INPUT)
    assert product.sku == "SKU001"
    assert product.abc_class == "A"
    assert product.cogs == 10.5

def test_product_input_invalid_abc_class():
    invalid_product = VALID_PRODUCT_INPUT.copy()
    invalid_product["abc_class"] = "D"
    with pytest.raises(ValidationError):
        ProductInput(**invalid_product)

def test_channel_input_valid():
    channel = ChannelInput(**VALID_CHANNEL_INPUT)
    assert channel.id == "STORE1"
    assert channel.capacity == 100
    assert channel.channel_type == "store"

def test_channel_input_missing_capacity():
    invalid_channel = VALID_CHANNEL_INPUT.copy()
    del invalid_channel["capacity"]
    with pytest.raises(ValidationError):
        ChannelInput(**invalid_channel)

def test_inventory_input_valid():
    inventory = InventoryInput(**VALID_INVENTORY_INPUT)
    assert inventory.product_sku == "SKU001"
    assert inventory.quantity == 50

def test_inventory_input_negative_quantity():
    invalid_inventory = VALID_INVENTORY_INPUT.copy()
    invalid_inventory["quantity"] = -10
    with pytest.raises(ValidationError):
        InventoryInput(**invalid_inventory)

def test_demand_input_valid():
    demand = DemandInput(**VALID_DEMAND_INPUT)
    assert demand.product_sku == "SKU001"
    assert demand.channel_id == "STORE1"
    assert demand.demand_quantity == 20

def test_demand_input_zero_demand_quantity():
    invalid_demand = VALID_DEMAND_INPUT.copy()
    invalid_demand["demand_quantity"] = 0
    with pytest.raises(ValidationError):
        DemandInput(**invalid_demand)

def test_coverage_days_rule_valid():
    rule = CoverageDaysRule(**VALID_COVERAGE_RULE)
    assert rule.channel_id == "STORE1"
    assert rule.abc_class == "A"
    assert rule.coverage_days == 7

def test_coverage_days_rule_invalid_abc_class():
    invalid_rule = VALID_COVERAGE_RULE.copy()
    invalid_rule["abc_class"] = "X"
    with pytest.raises(ValidationError):
        CoverageDaysRule(**invalid_rule)

def test_outlet_sku_capacity_rule_valid():
    rule = OutletSKUCapacityRule(**VALID_OUTLET_CAPACITY_RULE)
    assert rule.channel_id == "OUTLET1"
    assert rule.max_skus == 50

def test_outlet_sku_capacity_rule_negative_max_skus():
    invalid_rule = VALID_OUTLET_CAPACITY_RULE.copy()
    invalid_rule["max_skus"] = -5
    with pytest.raises(ValidationError):
        OutletSKUCapacityRule(**invalid_rule)

def test_outlet_assortment_rule_valid():
    rule = OutletAssortmentRule(**VALID_OUTLET_ASSORTMENT_RULE)
    assert rule.metier == "MetA"
    assert rule.max_skus == 10

def test_push_new_sku_rule_valid():
    rule = PushNewSKURule(**VALID_PUSH_NEW_SKU_RULE)
    assert rule.division == "DivA"
    assert rule.push_quantity == 20

# --- Test Cases for OptimizationParameters ---

def test_optimization_parameters_valid():
    params = OptimizationParameters(**VALID_OPTIMIZATION_PARAMETERS)
    assert params.seasonality_coefficient == 1.0
    assert params.restricted_brands_for_donation == ["BrandY"]
    assert len(params.coverage_days_rules) == 1
    assert params.coverage_days_rules[0].coverage_days == 7

def test_optimization_parameters_empty_lists():
    params_data = VALID_OPTIMIZATION_PARAMETERS.copy()
    params_data["coverage_days_rules"] = []
    params_data["outlet_sku_capacity_rules"] = []
    params_data["outlet_assortment_rules"] = []
    params_data["push_new_sku_rules"] = []
    params = OptimizationParameters(**params_data)
    assert len(params.coverage_days_rules) == 0
    assert len(params.outlet_sku_capacity_rules) == 0

def test_optimization_parameters_invalid_rule_type():
    invalid_params = VALID_OPTIMIZATION_PARAMETERS.copy()
    invalid_params["coverage_days_rules"] = [{"channel_id": "CH1", "abc_class": "A", "coverage_days": "seven"}] # Invalid type
    with pytest.raises(ValidationError):
        OptimizationParameters(**invalid_params)

# --- Test Cases for AllocationRequest ---

def test_allocation_request_valid_payload():
    request_data = AllocationRequest(**VALID_ALLOCATION_REQUEST_PAYLOAD)
    assert len(request_data.products) == 1
    assert request_data.products[0].sku == "SKU001"
    assert len(request_data.channels) == 2
    assert request_data.channels[0].id == "STORE1"
    assert len(request_data.inventory) == 1
    assert request_data.inventory[0].quantity == 50
    assert len(request_data.demand) == 1
    assert request_data.demand[0].demand_quantity == 20
    assert request_data.parameters.seasonality_coefficient == 1.0
    assert len(request_data.parameters.coverage_days_rules) == 1

def test_allocation_request_missing_parameters_field():
    invalid_payload = VALID_ALLOCATION_REQUEST_PAYLOAD.copy()
    del invalid_payload["parameters"]
    with pytest.raises(ValidationError) as excinfo:
        AllocationRequest(**invalid_payload)
    assert "parameters" in str(excinfo.value)
    assert "Field required" in str(excinfo.value)

def test_allocation_request_inventory_sku_not_in_products():
    invalid_payload = VALID_ALLOCATION_REQUEST_PAYLOAD.copy()
    invalid_payload["inventory"].append({"product_sku": "SKU999", "quantity": 5})
    with pytest.raises(ValidationError) as excinfo:
        AllocationRequest(**invalid_payload)
    assert "Inventory item SKU 'SKU999' not found in products list" in str(excinfo.value)

def test_allocation_request_demand_channel_not_in_channels():
    invalid_payload = VALID_ALLOCATION_REQUEST_PAYLOAD.copy()
    invalid_payload["demand"].append({"product_sku": "SKU001", "channel_id": "STORE99", "demand_quantity": 10})
    with pytest.raises(ValidationError) as excinfo:
        AllocationRequest(**invalid_payload)
    assert "Demand item Channel ID 'STORE99' not found in channels list" in str(excinfo.value)

def test_allocation_request_invalid_product_data():
    invalid_payload = VALID_ALLOCATION_REQUEST_PAYLOAD.copy()
    invalid_payload["products"] = [{"sku": "", "donation_eligible": True}] # Invalid SKU
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)

def test_allocation_request_invalid_channel_data():
    invalid_payload = VALID_ALLOCATION_REQUEST_PAYLOAD.copy()
    invalid_payload["channels"] = [{"id": "CH1", "capacity": -10, "channel_type": "store"}] # Invalid capacity
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)

def test_allocation_request_invalid_demand_data():
    invalid_payload = VALID_ALLOCATION_REQUEST_PAYLOAD.copy()
    invalid_payload["demand"] = [{"product_sku": "SKU001", "channel_id": "STORE1", "demand_quantity": -5}] # Invalid demand_quantity
    with pytest.raises(ValidationError):
        AllocationRequest(**invalid_payload)
