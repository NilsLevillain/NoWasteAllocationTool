from pydantic import BaseModel, Field, field_validator, conint, confloat, constr, model_validator
from typing import List, Literal, Dict, Optional

class ProductInput(BaseModel):
    sku: constr(min_length=1) = Field(..., description="Unique Stock Keeping Unit")
    donation_eligible: bool = Field(..., description="Flag indicating if the product can be donated")
    name: Optional[str] = Field(None, description="Optional product name")
    category: Optional[str] = Field(None, description="Optional product category")
    brand: Optional[str] = Field(None, description="Optional product brand/signature for restrictions") # Updated description
    division: Optional[str] = Field(None, description="Product division (e.g., CPD, LLD)")
    axe: Optional[str] = Field(None, description="Product axis (e.g., makeup, haircare)")
    subaxis: Optional[str] = Field(None, description="Product subaxis (e.g., blush, shampoo)")
    metier: Optional[str] = Field(None, description="Product métier (e.g., lipstick, gloss) - finer than subaxis") # Added metier
    abc_class: Optional[Literal['A', 'B', 'C']] = Field(None, description="Product classification (A, B, C) for coverage rules") # Added abc_class

class ChannelInput(BaseModel):
    id: constr(min_length=1) = Field(..., description="Unique identifier for the channel (store, outlet, etc.)")
    capacity: conint(ge=0) = Field(..., description="Maximum total units the channel can receive (used for non-outlet channels)") # Updated description
    # max_coverage removed - now handled by coverage_days_rules
    channel_type: Literal['store', 'outlet', 'donation', 'other'] = Field(..., description="Type of the channel")

class InventoryInput(BaseModel):
    product_sku: constr(min_length=1) = Field(..., description="SKU of the product in inventory")
    quantity: conint(ge=0) = Field(..., description="Available quantity of the product")

class DemandInput(BaseModel):
    product_sku: constr(min_length=1) = Field(..., description="SKU of the product in demand")
    channel_id: constr(min_length=1) = Field(..., description="ID of the channel where demand exists")
    demand_quantity: conint(ge=1) = Field(..., description="Quantity demanded (must be positive)")

# Removed RevenueInput class

# --- New Parameter Structures ---

class CoverageDaysRule(BaseModel):
    channel_id: constr(min_length=1)
    abc_class: Literal['A', 'B', 'C']
    coverage_days: conint(ge=0)

class OutletSKUCapacityRule(BaseModel):
    channel_id: constr(min_length=1) # Should be an outlet channel
    division: constr(min_length=1)
    axe: constr(min_length=1)
    max_skus: conint(ge=0)

class OutletAssortmentRule(BaseModel):
    # channel_id: constr(min_length=1) # Assuming this applies to *all* outlets unless specified otherwise? Or add channel_id if needed.
    metier: constr(min_length=1)
    subaxis: constr(min_length=1)
    brand: constr(min_length=1) # Renamed from signature for consistency
    max_skus: conint(ge=0)


# --- Optimization Parameters ---

class OptimizationParameters(BaseModel):
    """Parameters to control the optimization algorithm's behavior."""
    # default_max_coverage removed
    # max_skus_per_store removed
    restricted_brands_for_donation: Optional[List[constr(min_length=1)]] = Field(
        None,
        description="List of brand names (signatures) that are explicitly forbidden from donation channels." # Updated description
    )
    coverage_days_rules: List[CoverageDaysRule] = Field(
        default_factory=list,
        description="List of rules defining maximum stock coverage in days per channel and product ABC class."
    )
    outlet_sku_capacity_rules: List[OutletSKUCapacityRule] = Field(
        default_factory=list,
        description="List of rules defining maximum SKU capacity for outlet channels based on division and axe."
    )
    outlet_assortment_rules: List[OutletAssortmentRule] = Field(
        default_factory=list,
        description="List of rules defining maximum SKU assortment for outlets based on metier, subaxis, and brand (signature)."
    )
    # Add other parameters as needed, e.g., max_stock_limit_override, etc.

# --- Main Allocation Request ---

class AllocationRequest(BaseModel):
    parameters: OptimizationParameters = Field(..., description="Parameters controlling the optimization")
    products: List[ProductInput] = Field(..., description="List of products")
    channels: List[ChannelInput] = Field(..., description="List of channels")
    inventory: List[InventoryInput] = Field(..., description="Current inventory levels")
    demand: List[DemandInput] = Field(..., description="Demand forecast")
    # revenue: List[RevenueInput] = Field(..., description="Revenue data") # Removed revenue field

    @field_validator('inventory')
    def check_inventory_products_exist(cls, inventory_list, values):
        # Pydantic v2 runs validators based on field definition order.
        # Ensure 'products' is available in values.data before proceeding.
        if 'products' not in values.data:
             # This case should ideally not happen if products are validated first,
             # but adding a safeguard.
             return inventory_list # Or raise an error if products must be validated first
        product_skus = {p.sku for p in values.data['products']}
        for item in inventory_list:
            if item.product_sku not in product_skus:
                raise ValueError(f"Inventory item SKU '{item.product_sku}' not found in products list.")
        return inventory_list

    @field_validator('demand')
    def check_demand_data_exists(cls, demand_list, values):
        if 'products' not in values.data or 'channels' not in values.data:
            return demand_list # Dependent fields not yet validated
        product_skus = {p.sku for p in values.data['products']}
        channel_ids = {c.id for c in values.data['channels']}
        for item in demand_list:
            if item.product_sku not in product_skus:
                raise ValueError(f"Demand item SKU '{item.product_sku}' not found in products list.")
            if item.channel_id not in channel_ids:
                raise ValueError(f"Demand item Channel ID '{item.channel_id}' not found in channels list.")
        return demand_list

    # Removed revenue validator

    # Add model validator if cross-field validation involving parameters is needed
    # @model_validator(mode='after')
    # def check_parameter_consistency(self):
    #     # Example: Check if restricted brands actually exist in product data
    #     if self.parameters.restricted_brands_for_donation:
    #         product_brands = {p.brand for p in self.products if p.brand}
    #         for restricted_brand in self.parameters.restricted_brands_for_donation:
    #             if restricted_brand not in product_brands:
    #                 # Decide whether to warn or raise error
    #                 print(f"Warning: Restricted brand '{restricted_brand}' not found in product list.")
    #     return self
