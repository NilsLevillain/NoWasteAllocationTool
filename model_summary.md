# Model Summary

Generated for model: InventoryAllocation
Status after solve (using sample data): Optimal

## Objective Function

1000*allocation_qty_('SKU001',_'DONATE1') + 1000*allocation_qty_('SKU001',_'OUTLET1') + 1010*allocation_qty_('SKU001',_'STORE1') + 1011*allocation_qty_('SKU001',_'STORE2') + 1000*allocation_qty_('SKU002',_'DONATE1') + 1000*allocation_qty_('SKU002',_'OUTLET1') + 1012*allocation_qty_('SKU002',_'STORE1') + 1000*allocation_qty_('SKU002',_'STORE2') + 1000*allocation_qty_('SKU003',_'DONATE1') + 1005*allocation_qty_('SKU003',_'OUTLET1') + 1000*allocation_qty_('SKU003',_'STORE1') + 1000*allocation_qty_('SKU003',_'STORE2') + 1000*allocation_qty_('SKU004',_'DONATE1') + 1000*allocation_qty_('SKU004',_'OUTLET1') + 1000*allocation_qty_('SKU004',_'STORE1') + 1009*allocation_qty_('SKU004',_'STORE2')

## Decision Variables

- allocation_qty_('SKU001',_'DONATE1'): 0 <= allocation_qty_('SKU001',_'DONATE1') 
- allocation_qty_('SKU001',_'OUTLET1'): 0 <= allocation_qty_('SKU001',_'OUTLET1') 
- allocation_qty_('SKU001',_'STORE1'): 0 <= allocation_qty_('SKU001',_'STORE1') 
- allocation_qty_('SKU001',_'STORE2'): 0 <= allocation_qty_('SKU001',_'STORE2') 
- allocation_qty_('SKU002',_'DONATE1'): 0 <= allocation_qty_('SKU002',_'DONATE1') 
- allocation_qty_('SKU002',_'OUTLET1'): 0 <= allocation_qty_('SKU002',_'OUTLET1') 
- allocation_qty_('SKU002',_'STORE1'): 0 <= allocation_qty_('SKU002',_'STORE1') 
- allocation_qty_('SKU002',_'STORE2'): 0 <= allocation_qty_('SKU002',_'STORE2') 
- allocation_qty_('SKU003',_'DONATE1'): 0 <= allocation_qty_('SKU003',_'DONATE1') 
- allocation_qty_('SKU003',_'OUTLET1'): 0 <= allocation_qty_('SKU003',_'OUTLET1') 
- allocation_qty_('SKU003',_'STORE1'): 0 <= allocation_qty_('SKU003',_'STORE1') 
- allocation_qty_('SKU003',_'STORE2'): 0 <= allocation_qty_('SKU003',_'STORE2') 
- allocation_qty_('SKU004',_'DONATE1'): 0 <= allocation_qty_('SKU004',_'DONATE1') 
- allocation_qty_('SKU004',_'OUTLET1'): 0 <= allocation_qty_('SKU004',_'OUTLET1') 
- allocation_qty_('SKU004',_'STORE1'): 0 <= allocation_qty_('SKU004',_'STORE1') 
- allocation_qty_('SKU004',_'STORE2'): 0 <= allocation_qty_('SKU004',_'STORE2') 
- is_allocated_('SKU001',_'DONATE1'): 0 <= is_allocated_('SKU001',_'DONATE1') <= 1
- is_allocated_('SKU001',_'OUTLET1'): 0 <= is_allocated_('SKU001',_'OUTLET1') <= 1
- is_allocated_('SKU001',_'STORE1'): 0 <= is_allocated_('SKU001',_'STORE1') <= 1
- is_allocated_('SKU001',_'STORE2'): 0 <= is_allocated_('SKU001',_'STORE2') <= 1
- is_allocated_('SKU002',_'DONATE1'): 0 <= is_allocated_('SKU002',_'DONATE1') <= 1
- is_allocated_('SKU002',_'OUTLET1'): 0 <= is_allocated_('SKU002',_'OUTLET1') <= 1
- is_allocated_('SKU002',_'STORE1'): 0 <= is_allocated_('SKU002',_'STORE1') <= 1
- is_allocated_('SKU002',_'STORE2'): 0 <= is_allocated_('SKU002',_'STORE2') <= 1
- is_allocated_('SKU003',_'DONATE1'): 0 <= is_allocated_('SKU003',_'DONATE1') <= 1
- is_allocated_('SKU003',_'OUTLET1'): 0 <= is_allocated_('SKU003',_'OUTLET1') <= 1
- is_allocated_('SKU003',_'STORE1'): 0 <= is_allocated_('SKU003',_'STORE1') <= 1
- is_allocated_('SKU003',_'STORE2'): 0 <= is_allocated_('SKU003',_'STORE2') <= 1
- is_allocated_('SKU004',_'DONATE1'): 0 <= is_allocated_('SKU004',_'DONATE1') <= 1
- is_allocated_('SKU004',_'OUTLET1'): 0 <= is_allocated_('SKU004',_'OUTLET1') <= 1
- is_allocated_('SKU004',_'STORE1'): 0 <= is_allocated_('SKU004',_'STORE1') <= 1
- is_allocated_('SKU004',_'STORE2'): 0 <= is_allocated_('SKU004',_'STORE2') <= 1

## Constraints

- Supply_Product_SKU001: allocation_qty_('SKU001',_'DONATE1') + allocation_qty_('SKU001',_'OUTLET1') + allocation_qty_('SKU001',_'STORE1') + allocation_qty_('SKU001',_'STORE2') <= 70
- Supply_Product_SKU002: allocation_qty_('SKU002',_'DONATE1') + allocation_qty_('SKU002',_'OUTLET1') + allocation_qty_('SKU002',_'STORE1') + allocation_qty_('SKU002',_'STORE2') <= 30
- Supply_Product_SKU003: allocation_qty_('SKU003',_'DONATE1') + allocation_qty_('SKU003',_'OUTLET1') + allocation_qty_('SKU003',_'STORE1') + allocation_qty_('SKU003',_'STORE2') <= 40
- Supply_Product_SKU004: allocation_qty_('SKU004',_'DONATE1') + allocation_qty_('SKU004',_'OUTLET1') + allocation_qty_('SKU004',_'STORE1') + allocation_qty_('SKU004',_'STORE2') <= 60
- Capacity_Channel_STORE1: allocation_qty_('SKU001',_'STORE1') + allocation_qty_('SKU002',_'STORE1') + allocation_qty_('SKU003',_'STORE1') + allocation_qty_('SKU004',_'STORE1') <= 100
- Capacity_Channel_OUTLET1: allocation_qty_('SKU001',_'OUTLET1') + allocation_qty_('SKU002',_'OUTLET1') + allocation_qty_('SKU003',_'OUTLET1') + allocation_qty_('SKU004',_'OUTLET1') <= 200
- Capacity_Channel_DONATE1: allocation_qty_('SKU001',_'DONATE1') + allocation_qty_('SKU002',_'DONATE1') + allocation_qty_('SKU003',_'DONATE1') + allocation_qty_('SKU004',_'DONATE1') <= 50
- Capacity_Channel_STORE2: allocation_qty_('SKU001',_'STORE2') + allocation_qty_('SKU002',_'STORE2') + allocation_qty_('SKU003',_'STORE2') + allocation_qty_('SKU004',_'STORE2') <= 80
- Min_Coverage_Prod_SKU001_Chan_STORE1: allocation_qty_('SKU001',_'STORE1') >= 20.0
- Min_Coverage_Prod_SKU002_Chan_STORE1: allocation_qty_('SKU002',_'STORE1') >= 10.0
- Min_Coverage_Prod_SKU001_Chan_STORE2: allocation_qty_('SKU001',_'STORE2') >= 18.0
- Min_Coverage_Prod_SKU004_Chan_STORE2: allocation_qty_('SKU004',_'STORE2') >= 30.0
- Donation_Eligibility_Prod_SKU002_Chan_DONATE1: allocation_qty_('SKU002',_'DONATE1') = 0
- Link_x_y_Prod_SKU001_Chan_STORE1: allocation_qty_('SKU001',_'STORE1') - 70*is_allocated_('SKU001',_'STORE1') <= 0
- Link_x_y_Prod_SKU001_Chan_OUTLET1: allocation_qty_('SKU001',_'OUTLET1') - 70*is_allocated_('SKU001',_'OUTLET1') <= 0
- Link_x_y_Prod_SKU001_Chan_DONATE1: allocation_qty_('SKU001',_'DONATE1') - 70*is_allocated_('SKU001',_'DONATE1') <= 0
- Link_x_y_Prod_SKU001_Chan_STORE2: allocation_qty_('SKU001',_'STORE2') - 70*is_allocated_('SKU001',_'STORE2') <= 0
- Link_x_y_Prod_SKU002_Chan_STORE1: allocation_qty_('SKU002',_'STORE1') - 30*is_allocated_('SKU002',_'STORE1') <= 0
- Link_x_y_Prod_SKU002_Chan_OUTLET1: allocation_qty_('SKU002',_'OUTLET1') - 30*is_allocated_('SKU002',_'OUTLET1') <= 0
- Link_x_y_Prod_SKU002_Chan_DONATE1: allocation_qty_('SKU002',_'DONATE1') - 30*is_allocated_('SKU002',_'DONATE1') <= 0
- Link_x_y_Prod_SKU002_Chan_STORE2: allocation_qty_('SKU002',_'STORE2') - 30*is_allocated_('SKU002',_'STORE2') <= 0
- Link_x_y_Prod_SKU003_Chan_STORE1: allocation_qty_('SKU003',_'STORE1') - 40*is_allocated_('SKU003',_'STORE1') <= 0
- Link_x_y_Prod_SKU003_Chan_OUTLET1: allocation_qty_('SKU003',_'OUTLET1') - 40*is_allocated_('SKU003',_'OUTLET1') <= 0
- Link_x_y_Prod_SKU003_Chan_DONATE1: allocation_qty_('SKU003',_'DONATE1') - 40*is_allocated_('SKU003',_'DONATE1') <= 0
- Link_x_y_Prod_SKU003_Chan_STORE2: allocation_qty_('SKU003',_'STORE2') - 40*is_allocated_('SKU003',_'STORE2') <= 0
- Link_x_y_Prod_SKU004_Chan_STORE1: allocation_qty_('SKU004',_'STORE1') - 60*is_allocated_('SKU004',_'STORE1') <= 0
- Link_x_y_Prod_SKU004_Chan_OUTLET1: allocation_qty_('SKU004',_'OUTLET1') - 60*is_allocated_('SKU004',_'OUTLET1') <= 0
- Link_x_y_Prod_SKU004_Chan_DONATE1: allocation_qty_('SKU004',_'DONATE1') - 60*is_allocated_('SKU004',_'DONATE1') <= 0
- Link_x_y_Prod_SKU004_Chan_STORE2: allocation_qty_('SKU004',_'STORE2') - 60*is_allocated_('SKU004',_'STORE2') <= 0
