\* InventoryAllocation *\
Maximize
Maximize_Total_Allocation: allocation_qty_('SKU001',_'DONATE1')
 + allocation_qty_('SKU001',_'OUTLET1') + allocation_qty_('SKU001',_'OUTLET2')
 + allocation_qty_('SKU001',_'STORE1') + allocation_qty_('SKU001',_'STORE2')
 + allocation_qty_('SKU002',_'DONATE1') + allocation_qty_('SKU002',_'OUTLET1')
 + allocation_qty_('SKU002',_'OUTLET2') + allocation_qty_('SKU002',_'STORE1')
 + allocation_qty_('SKU002',_'STORE2') + allocation_qty_('SKU003',_'DONATE1')
 + allocation_qty_('SKU003',_'OUTLET1') + allocation_qty_('SKU003',_'OUTLET2')
 + allocation_qty_('SKU003',_'STORE1') + allocation_qty_('SKU003',_'STORE2')
 + allocation_qty_('SKU004',_'DONATE1') + allocation_qty_('SKU004',_'OUTLET1')
 + allocation_qty_('SKU004',_'OUTLET2') + allocation_qty_('SKU004',_'STORE1')
 + allocation_qty_('SKU004',_'STORE2') + allocation_qty_('SKU005',_'DONATE1')
 + allocation_qty_('SKU005',_'OUTLET1') + allocation_qty_('SKU005',_'OUTLET2')
 + allocation_qty_('SKU005',_'STORE1') + allocation_qty_('SKU005',_'STORE2')
Subject To
Capacity_Channel_DONATE1: allocation_qty_('SKU001',_'DONATE1')
 + allocation_qty_('SKU002',_'DONATE1') + allocation_qty_('SKU003',_'DONATE1')
 + allocation_qty_('SKU004',_'DONATE1') + allocation_qty_('SKU005',_'DONATE1')
 <= 50
Capacity_Channel_STORE1: allocation_qty_('SKU001',_'STORE1')
 + allocation_qty_('SKU002',_'STORE1') + allocation_qty_('SKU003',_'STORE1')
 + allocation_qty_('SKU004',_'STORE1') + allocation_qty_('SKU005',_'STORE1')
 <= 100
Capacity_Channel_STORE2: allocation_qty_('SKU001',_'STORE2')
 + allocation_qty_('SKU002',_'STORE2') + allocation_qty_('SKU003',_'STORE2')
 + allocation_qty_('SKU004',_'STORE2') + allocation_qty_('SKU005',_'STORE2')
 <= 80
Link_x_y_Prod_SKU001_Chan_DONATE1: allocation_qty_('SKU001',_'DONATE1')
 - 70 is_allocated_('SKU001',_'DONATE1') <= 0
Link_x_y_Prod_SKU001_Chan_OUTLET1: allocation_qty_('SKU001',_'OUTLET1')
 - 70 is_allocated_('SKU001',_'OUTLET1') <= 0
Link_x_y_Prod_SKU001_Chan_OUTLET2: allocation_qty_('SKU001',_'OUTLET2')
 - 70 is_allocated_('SKU001',_'OUTLET2') <= 0
Link_x_y_Prod_SKU001_Chan_STORE1: allocation_qty_('SKU001',_'STORE1')
 - 70 is_allocated_('SKU001',_'STORE1') <= 0
Link_x_y_Prod_SKU001_Chan_STORE2: allocation_qty_('SKU001',_'STORE2')
 - 70 is_allocated_('SKU001',_'STORE2') <= 0
Link_x_y_Prod_SKU002_Chan_DONATE1: allocation_qty_('SKU002',_'DONATE1')
 - 30 is_allocated_('SKU002',_'DONATE1') <= 0
Link_x_y_Prod_SKU002_Chan_OUTLET1: allocation_qty_('SKU002',_'OUTLET1')
 - 30 is_allocated_('SKU002',_'OUTLET1') <= 0
Link_x_y_Prod_SKU002_Chan_OUTLET2: allocation_qty_('SKU002',_'OUTLET2')
 - 30 is_allocated_('SKU002',_'OUTLET2') <= 0
Link_x_y_Prod_SKU002_Chan_STORE1: allocation_qty_('SKU002',_'STORE1')
 - 30 is_allocated_('SKU002',_'STORE1') <= 0
Link_x_y_Prod_SKU002_Chan_STORE2: allocation_qty_('SKU002',_'STORE2')
 - 30 is_allocated_('SKU002',_'STORE2') <= 0
Link_x_y_Prod_SKU003_Chan_DONATE1: allocation_qty_('SKU003',_'DONATE1')
 - 40 is_allocated_('SKU003',_'DONATE1') <= 0
Link_x_y_Prod_SKU003_Chan_OUTLET1: allocation_qty_('SKU003',_'OUTLET1')
 - 40 is_allocated_('SKU003',_'OUTLET1') <= 0
Link_x_y_Prod_SKU003_Chan_OUTLET2: allocation_qty_('SKU003',_'OUTLET2')
 - 40 is_allocated_('SKU003',_'OUTLET2') <= 0
Link_x_y_Prod_SKU003_Chan_STORE1: allocation_qty_('SKU003',_'STORE1')
 - 40 is_allocated_('SKU003',_'STORE1') <= 0
Link_x_y_Prod_SKU003_Chan_STORE2: allocation_qty_('SKU003',_'STORE2')
 - 40 is_allocated_('SKU003',_'STORE2') <= 0
Link_x_y_Prod_SKU004_Chan_DONATE1: allocation_qty_('SKU004',_'DONATE1')
 - 60 is_allocated_('SKU004',_'DONATE1') <= 0
Link_x_y_Prod_SKU004_Chan_OUTLET1: allocation_qty_('SKU004',_'OUTLET1')
 - 60 is_allocated_('SKU004',_'OUTLET1') <= 0
Link_x_y_Prod_SKU004_Chan_OUTLET2: allocation_qty_('SKU004',_'OUTLET2')
 - 60 is_allocated_('SKU004',_'OUTLET2') <= 0
Link_x_y_Prod_SKU004_Chan_STORE1: allocation_qty_('SKU004',_'STORE1')
 - 60 is_allocated_('SKU004',_'STORE1') <= 0
Link_x_y_Prod_SKU004_Chan_STORE2: allocation_qty_('SKU004',_'STORE2')
 - 60 is_allocated_('SKU004',_'STORE2') <= 0
Link_x_y_Prod_SKU005_Chan_DONATE1: allocation_qty_('SKU005',_'DONATE1')
 - 25 is_allocated_('SKU005',_'DONATE1') <= 0
Link_x_y_Prod_SKU005_Chan_OUTLET1: allocation_qty_('SKU005',_'OUTLET1')
 - 25 is_allocated_('SKU005',_'OUTLET1') <= 0
Link_x_y_Prod_SKU005_Chan_OUTLET2: allocation_qty_('SKU005',_'OUTLET2')
 - 25 is_allocated_('SKU005',_'OUTLET2') <= 0
Link_x_y_Prod_SKU005_Chan_STORE1: allocation_qty_('SKU005',_'STORE1')
 - 25 is_allocated_('SKU005',_'STORE1') <= 0
Link_x_y_Prod_SKU005_Chan_STORE2: allocation_qty_('SKU005',_'STORE2')
 - 25 is_allocated_('SKU005',_'STORE2') <= 0
Max_Coverage_Days_SKU001_OUTLET2: allocation_qty_('SKU001',_'OUTLET2') <= 140
Max_Coverage_Days_SKU001_STORE1: allocation_qty_('SKU001',_'STORE1') <= 28
Max_Coverage_Days_SKU002_STORE1: allocation_qty_('SKU002',_'STORE1') <= 21
Max_Coverage_Days_SKU003_OUTLET1: allocation_qty_('SKU003',_'OUTLET1') <= 84
Max_Coverage_Days_SKU005_OUTLET1: allocation_qty_('SKU005',_'OUTLET1') <= 21
Max_Coverage_Days_Zero_Demand_SKU001_OUTLET1:
 allocation_qty_('SKU001',_'OUTLET1') <= 0
Max_Coverage_Days_Zero_Demand_SKU002_OUTLET1:
 allocation_qty_('SKU002',_'OUTLET1') <= 0
Max_Coverage_Days_Zero_Demand_SKU003_OUTLET2:
 allocation_qty_('SKU003',_'OUTLET2') <= 0
Max_Coverage_Days_Zero_Demand_SKU003_STORE1:
 allocation_qty_('SKU003',_'STORE1') <= 0
Max_Coverage_Days_Zero_Demand_SKU005_STORE1:
 allocation_qty_('SKU005',_'STORE1') <= 0
Outlet_Assortment_OUTLET1_Eau_de_Toilette_Men_Fragrance_BrandA:
 is_allocated_('SKU001',_'OUTLET1') <= 1
Outlet_Assortment_OUTLET1_Lipstick_Lip_Makeup_BrandC:
 is_allocated_('SKU004',_'OUTLET1') <= 1
Outlet_Assortment_OUTLET2_Eau_de_Toilette_Men_Fragrance_BrandA:
 is_allocated_('SKU001',_'OUTLET2') <= 1
Outlet_Assortment_OUTLET2_Lipstick_Lip_Makeup_BrandC:
 is_allocated_('SKU004',_'OUTLET2') <= 1
Outlet_Capacity_SKU_OUTLET1_CPD_Skincare: is_allocated_('SKU003',_'OUTLET1')
 <= 1
Outlet_Capacity_SKU_OUTLET1_LLD_Fragrance: is_allocated_('SKU001',_'OUTLET1')
 + is_allocated_('SKU002',_'OUTLET1') + is_allocated_('SKU005',_'OUTLET1')
 <= 2
Outlet_Capacity_SKU_OUTLET2_LLD_Fragrance: is_allocated_('SKU001',_'OUTLET2')
 + is_allocated_('SKU002',_'OUTLET2') + is_allocated_('SKU005',_'OUTLET2')
 <= 1
Restricted_Brand_BrandB_Prod_SKU003_Chan_DONATE1:
 allocation_qty_('SKU003',_'DONATE1') = 0
Supply_Product_SKU001: allocation_qty_('SKU001',_'DONATE1')
 + allocation_qty_('SKU001',_'OUTLET1') + allocation_qty_('SKU001',_'OUTLET2')
 + allocation_qty_('SKU001',_'STORE1') + allocation_qty_('SKU001',_'STORE2')
 <= 70
Supply_Product_SKU002: allocation_qty_('SKU002',_'DONATE1')
 + allocation_qty_('SKU002',_'OUTLET1') + allocation_qty_('SKU002',_'OUTLET2')
 + allocation_qty_('SKU002',_'STORE1') + allocation_qty_('SKU002',_'STORE2')
 <= 30
Supply_Product_SKU003: allocation_qty_('SKU003',_'DONATE1')
 + allocation_qty_('SKU003',_'OUTLET1') + allocation_qty_('SKU003',_'OUTLET2')
 + allocation_qty_('SKU003',_'STORE1') + allocation_qty_('SKU003',_'STORE2')
 <= 40
Supply_Product_SKU004: allocation_qty_('SKU004',_'DONATE1')
 + allocation_qty_('SKU004',_'OUTLET1') + allocation_qty_('SKU004',_'OUTLET2')
 + allocation_qty_('SKU004',_'STORE1') + allocation_qty_('SKU004',_'STORE2')
 <= 60
Supply_Product_SKU005: allocation_qty_('SKU005',_'DONATE1')
 + allocation_qty_('SKU005',_'OUTLET1') + allocation_qty_('SKU005',_'OUTLET2')
 + allocation_qty_('SKU005',_'STORE1') + allocation_qty_('SKU005',_'STORE2')
 <= 25
Bounds
 0 <= allocation_qty_('SKU001',_'DONATE1')
 0 <= allocation_qty_('SKU001',_'OUTLET1')
 0 <= allocation_qty_('SKU001',_'OUTLET2')
 0 <= allocation_qty_('SKU001',_'STORE1')
 0 <= allocation_qty_('SKU001',_'STORE2')
 0 <= allocation_qty_('SKU002',_'DONATE1')
 0 <= allocation_qty_('SKU002',_'OUTLET1')
 0 <= allocation_qty_('SKU002',_'OUTLET2')
 0 <= allocation_qty_('SKU002',_'STORE1')
 0 <= allocation_qty_('SKU002',_'STORE2')
 0 <= allocation_qty_('SKU003',_'DONATE1')
 0 <= allocation_qty_('SKU003',_'OUTLET1')
 0 <= allocation_qty_('SKU003',_'OUTLET2')
 0 <= allocation_qty_('SKU003',_'STORE1')
 0 <= allocation_qty_('SKU003',_'STORE2')
 0 <= allocation_qty_('SKU004',_'DONATE1')
 0 <= allocation_qty_('SKU004',_'OUTLET1')
 0 <= allocation_qty_('SKU004',_'OUTLET2')
 0 <= allocation_qty_('SKU004',_'STORE1')
 0 <= allocation_qty_('SKU004',_'STORE2')
 0 <= allocation_qty_('SKU005',_'DONATE1')
 0 <= allocation_qty_('SKU005',_'OUTLET1')
 0 <= allocation_qty_('SKU005',_'OUTLET2')
 0 <= allocation_qty_('SKU005',_'STORE1')
 0 <= allocation_qty_('SKU005',_'STORE2')
Generals
allocation_qty_('SKU001',_'DONATE1')
allocation_qty_('SKU001',_'OUTLET1')
allocation_qty_('SKU001',_'OUTLET2')
allocation_qty_('SKU001',_'STORE1')
allocation_qty_('SKU001',_'STORE2')
allocation_qty_('SKU002',_'DONATE1')
allocation_qty_('SKU002',_'OUTLET1')
allocation_qty_('SKU002',_'OUTLET2')
allocation_qty_('SKU002',_'STORE1')
allocation_qty_('SKU002',_'STORE2')
allocation_qty_('SKU003',_'DONATE1')
allocation_qty_('SKU003',_'OUTLET1')
allocation_qty_('SKU003',_'OUTLET2')
allocation_qty_('SKU003',_'STORE1')
allocation_qty_('SKU003',_'STORE2')
allocation_qty_('SKU004',_'DONATE1')
allocation_qty_('SKU004',_'OUTLET1')
allocation_qty_('SKU004',_'OUTLET2')
allocation_qty_('SKU004',_'STORE1')
allocation_qty_('SKU004',_'STORE2')
allocation_qty_('SKU005',_'DONATE1')
allocation_qty_('SKU005',_'OUTLET1')
allocation_qty_('SKU005',_'OUTLET2')
allocation_qty_('SKU005',_'STORE1')
allocation_qty_('SKU005',_'STORE2')
Binaries
is_allocated_('SKU001',_'DONATE1')
is_allocated_('SKU001',_'OUTLET1')
is_allocated_('SKU001',_'OUTLET2')
is_allocated_('SKU001',_'STORE1')
is_allocated_('SKU001',_'STORE2')
is_allocated_('SKU002',_'DONATE1')
is_allocated_('SKU002',_'OUTLET1')
is_allocated_('SKU002',_'OUTLET2')
is_allocated_('SKU002',_'STORE1')
is_allocated_('SKU002',_'STORE2')
is_allocated_('SKU003',_'DONATE1')
is_allocated_('SKU003',_'OUTLET1')
is_allocated_('SKU003',_'OUTLET2')
is_allocated_('SKU003',_'STORE1')
is_allocated_('SKU003',_'STORE2')
is_allocated_('SKU004',_'DONATE1')
is_allocated_('SKU004',_'OUTLET1')
is_allocated_('SKU004',_'OUTLET2')
is_allocated_('SKU004',_'STORE1')
is_allocated_('SKU004',_'STORE2')
is_allocated_('SKU005',_'DONATE1')
is_allocated_('SKU005',_'OUTLET1')
is_allocated_('SKU005',_'OUTLET2')
is_allocated_('SKU005',_'STORE1')
is_allocated_('SKU005',_'STORE2')
End
