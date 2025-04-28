*SENSE:Maximize
NAME          InventoryAllocation
ROWS
 N  OBJ
 L  Supply_Product_SKU001
 L  Supply_Product_SKU002
 L  Supply_Product_SKU003
 L  Supply_Product_SKU004
 L  Capacity_Channel_STORE1
 L  Capacity_Channel_OUTLET1
 L  Capacity_Channel_DONATE1
 L  Capacity_Channel_STORE2
 G  Min_Coverage_Prod_SKU001_Chan_STORE1
 G  Min_Coverage_Prod_SKU002_Chan_STORE1
 G  Min_Coverage_Prod_SKU001_Chan_STORE2
 G  Min_Coverage_Prod_SKU004_Chan_STORE2
 E  Donation_Eligibility_Prod_SKU002_Chan_DONATE1
 L  Link_x_y_Prod_SKU001_Chan_STORE1
 L  Link_x_y_Prod_SKU001_Chan_OUTLET1
 L  Link_x_y_Prod_SKU001_Chan_DONATE1
 L  Link_x_y_Prod_SKU001_Chan_STORE2
 L  Link_x_y_Prod_SKU002_Chan_STORE1
 L  Link_x_y_Prod_SKU002_Chan_OUTLET1
 L  Link_x_y_Prod_SKU002_Chan_DONATE1
 L  Link_x_y_Prod_SKU002_Chan_STORE2
 L  Link_x_y_Prod_SKU003_Chan_STORE1
 L  Link_x_y_Prod_SKU003_Chan_OUTLET1
 L  Link_x_y_Prod_SKU003_Chan_DONATE1
 L  Link_x_y_Prod_SKU003_Chan_STORE2
 L  Link_x_y_Prod_SKU004_Chan_STORE1
 L  Link_x_y_Prod_SKU004_Chan_OUTLET1
 L  Link_x_y_Prod_SKU004_Chan_DONATE1
 L  Link_x_y_Prod_SKU004_Chan_STORE2
COLUMNS
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU001',_'DONATE1')  Supply_Product_SKU001   1.000000000000e+00
    allocation_qty_('SKU001',_'DONATE1')  Capacity_Channel_DONATE1   1.000000000000e+00
    allocation_qty_('SKU001',_'DONATE1')  Link_x_y_Prod_SKU001_Chan_DONATE1   1.000000000000e+00
    allocation_qty_('SKU001',_'DONATE1')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU001',_'OUTLET1')  Supply_Product_SKU001   1.000000000000e+00
    allocation_qty_('SKU001',_'OUTLET1')  Capacity_Channel_OUTLET1   1.000000000000e+00
    allocation_qty_('SKU001',_'OUTLET1')  Link_x_y_Prod_SKU001_Chan_OUTLET1   1.000000000000e+00
    allocation_qty_('SKU001',_'OUTLET1')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU001',_'STORE1')  Supply_Product_SKU001   1.000000000000e+00
    allocation_qty_('SKU001',_'STORE1')  Capacity_Channel_STORE1   1.000000000000e+00
    allocation_qty_('SKU001',_'STORE1')  Min_Coverage_Prod_SKU001_Chan_STORE1   1.000000000000e+00
    allocation_qty_('SKU001',_'STORE1')  Link_x_y_Prod_SKU001_Chan_STORE1   1.000000000000e+00
    allocation_qty_('SKU001',_'STORE1')  OBJ        1.010000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU001',_'STORE2')  Supply_Product_SKU001   1.000000000000e+00
    allocation_qty_('SKU001',_'STORE2')  Capacity_Channel_STORE2   1.000000000000e+00
    allocation_qty_('SKU001',_'STORE2')  Min_Coverage_Prod_SKU001_Chan_STORE2   1.000000000000e+00
    allocation_qty_('SKU001',_'STORE2')  Link_x_y_Prod_SKU001_Chan_STORE2   1.000000000000e+00
    allocation_qty_('SKU001',_'STORE2')  OBJ        1.011000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU002',_'DONATE1')  Supply_Product_SKU002   1.000000000000e+00
    allocation_qty_('SKU002',_'DONATE1')  Capacity_Channel_DONATE1   1.000000000000e+00
    allocation_qty_('SKU002',_'DONATE1')  Donation_Eligibility_Prod_SKU002_Chan_DONATE1   1.000000000000e+00
    allocation_qty_('SKU002',_'DONATE1')  Link_x_y_Prod_SKU002_Chan_DONATE1   1.000000000000e+00
    allocation_qty_('SKU002',_'DONATE1')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU002',_'OUTLET1')  Supply_Product_SKU002   1.000000000000e+00
    allocation_qty_('SKU002',_'OUTLET1')  Capacity_Channel_OUTLET1   1.000000000000e+00
    allocation_qty_('SKU002',_'OUTLET1')  Link_x_y_Prod_SKU002_Chan_OUTLET1   1.000000000000e+00
    allocation_qty_('SKU002',_'OUTLET1')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU002',_'STORE1')  Supply_Product_SKU002   1.000000000000e+00
    allocation_qty_('SKU002',_'STORE1')  Capacity_Channel_STORE1   1.000000000000e+00
    allocation_qty_('SKU002',_'STORE1')  Min_Coverage_Prod_SKU002_Chan_STORE1   1.000000000000e+00
    allocation_qty_('SKU002',_'STORE1')  Link_x_y_Prod_SKU002_Chan_STORE1   1.000000000000e+00
    allocation_qty_('SKU002',_'STORE1')  OBJ        1.012000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU002',_'STORE2')  Supply_Product_SKU002   1.000000000000e+00
    allocation_qty_('SKU002',_'STORE2')  Capacity_Channel_STORE2   1.000000000000e+00
    allocation_qty_('SKU002',_'STORE2')  Link_x_y_Prod_SKU002_Chan_STORE2   1.000000000000e+00
    allocation_qty_('SKU002',_'STORE2')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU003',_'DONATE1')  Supply_Product_SKU003   1.000000000000e+00
    allocation_qty_('SKU003',_'DONATE1')  Capacity_Channel_DONATE1   1.000000000000e+00
    allocation_qty_('SKU003',_'DONATE1')  Link_x_y_Prod_SKU003_Chan_DONATE1   1.000000000000e+00
    allocation_qty_('SKU003',_'DONATE1')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU003',_'OUTLET1')  Supply_Product_SKU003   1.000000000000e+00
    allocation_qty_('SKU003',_'OUTLET1')  Capacity_Channel_OUTLET1   1.000000000000e+00
    allocation_qty_('SKU003',_'OUTLET1')  Link_x_y_Prod_SKU003_Chan_OUTLET1   1.000000000000e+00
    allocation_qty_('SKU003',_'OUTLET1')  OBJ        1.005000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU003',_'STORE1')  Supply_Product_SKU003   1.000000000000e+00
    allocation_qty_('SKU003',_'STORE1')  Capacity_Channel_STORE1   1.000000000000e+00
    allocation_qty_('SKU003',_'STORE1')  Link_x_y_Prod_SKU003_Chan_STORE1   1.000000000000e+00
    allocation_qty_('SKU003',_'STORE1')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU003',_'STORE2')  Supply_Product_SKU003   1.000000000000e+00
    allocation_qty_('SKU003',_'STORE2')  Capacity_Channel_STORE2   1.000000000000e+00
    allocation_qty_('SKU003',_'STORE2')  Link_x_y_Prod_SKU003_Chan_STORE2   1.000000000000e+00
    allocation_qty_('SKU003',_'STORE2')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU004',_'DONATE1')  Supply_Product_SKU004   1.000000000000e+00
    allocation_qty_('SKU004',_'DONATE1')  Capacity_Channel_DONATE1   1.000000000000e+00
    allocation_qty_('SKU004',_'DONATE1')  Link_x_y_Prod_SKU004_Chan_DONATE1   1.000000000000e+00
    allocation_qty_('SKU004',_'DONATE1')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU004',_'OUTLET1')  Supply_Product_SKU004   1.000000000000e+00
    allocation_qty_('SKU004',_'OUTLET1')  Capacity_Channel_OUTLET1   1.000000000000e+00
    allocation_qty_('SKU004',_'OUTLET1')  Link_x_y_Prod_SKU004_Chan_OUTLET1   1.000000000000e+00
    allocation_qty_('SKU004',_'OUTLET1')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU004',_'STORE1')  Supply_Product_SKU004   1.000000000000e+00
    allocation_qty_('SKU004',_'STORE1')  Capacity_Channel_STORE1   1.000000000000e+00
    allocation_qty_('SKU004',_'STORE1')  Link_x_y_Prod_SKU004_Chan_STORE1   1.000000000000e+00
    allocation_qty_('SKU004',_'STORE1')  OBJ        1.000000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    allocation_qty_('SKU004',_'STORE2')  Supply_Product_SKU004   1.000000000000e+00
    allocation_qty_('SKU004',_'STORE2')  Capacity_Channel_STORE2   1.000000000000e+00
    allocation_qty_('SKU004',_'STORE2')  Min_Coverage_Prod_SKU004_Chan_STORE2   1.000000000000e+00
    allocation_qty_('SKU004',_'STORE2')  Link_x_y_Prod_SKU004_Chan_STORE2   1.000000000000e+00
    allocation_qty_('SKU004',_'STORE2')  OBJ        1.009000000000e+03
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU001',_'DONATE1')  Link_x_y_Prod_SKU001_Chan_DONATE1  -7.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU001',_'OUTLET1')  Link_x_y_Prod_SKU001_Chan_OUTLET1  -7.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU001',_'STORE1')  Link_x_y_Prod_SKU001_Chan_STORE1  -7.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU001',_'STORE2')  Link_x_y_Prod_SKU001_Chan_STORE2  -7.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU002',_'DONATE1')  Link_x_y_Prod_SKU002_Chan_DONATE1  -3.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU002',_'OUTLET1')  Link_x_y_Prod_SKU002_Chan_OUTLET1  -3.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU002',_'STORE1')  Link_x_y_Prod_SKU002_Chan_STORE1  -3.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU002',_'STORE2')  Link_x_y_Prod_SKU002_Chan_STORE2  -3.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU003',_'DONATE1')  Link_x_y_Prod_SKU003_Chan_DONATE1  -4.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU003',_'OUTLET1')  Link_x_y_Prod_SKU003_Chan_OUTLET1  -4.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU003',_'STORE1')  Link_x_y_Prod_SKU003_Chan_STORE1  -4.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU003',_'STORE2')  Link_x_y_Prod_SKU003_Chan_STORE2  -4.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU004',_'DONATE1')  Link_x_y_Prod_SKU004_Chan_DONATE1  -6.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU004',_'OUTLET1')  Link_x_y_Prod_SKU004_Chan_OUTLET1  -6.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU004',_'STORE1')  Link_x_y_Prod_SKU004_Chan_STORE1  -6.000000000000e+01
    MARK      'MARKER'                 'INTEND'
    MARK      'MARKER'                 'INTORG'
    is_allocated_('SKU004',_'STORE2')  Link_x_y_Prod_SKU004_Chan_STORE2  -6.000000000000e+01
    MARK      'MARKER'                 'INTEND'
RHS
    RHS       Supply_Product_SKU001   7.000000000000e+01
    RHS       Supply_Product_SKU002   3.000000000000e+01
    RHS       Supply_Product_SKU003   4.000000000000e+01
    RHS       Supply_Product_SKU004   6.000000000000e+01
    RHS       Capacity_Channel_STORE1   1.000000000000e+02
    RHS       Capacity_Channel_OUTLET1   2.000000000000e+02
    RHS       Capacity_Channel_DONATE1   5.000000000000e+01
    RHS       Capacity_Channel_STORE2   8.000000000000e+01
    RHS       Min_Coverage_Prod_SKU001_Chan_STORE1   2.000000000000e+01
    RHS       Min_Coverage_Prod_SKU002_Chan_STORE1   1.000000000000e+01
    RHS       Min_Coverage_Prod_SKU001_Chan_STORE2   1.800000000000e+01
    RHS       Min_Coverage_Prod_SKU004_Chan_STORE2   3.000000000000e+01
    RHS       Donation_Eligibility_Prod_SKU002_Chan_DONATE1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU001_Chan_STORE1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU001_Chan_OUTLET1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU001_Chan_DONATE1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU001_Chan_STORE2   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU002_Chan_STORE1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU002_Chan_OUTLET1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU002_Chan_DONATE1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU002_Chan_STORE2   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU003_Chan_STORE1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU003_Chan_OUTLET1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU003_Chan_DONATE1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU003_Chan_STORE2   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU004_Chan_STORE1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU004_Chan_OUTLET1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU004_Chan_DONATE1   0.000000000000e+00
    RHS       Link_x_y_Prod_SKU004_Chan_STORE2   0.000000000000e+00
BOUNDS
 LO BND       allocation_qty_('SKU001',_'DONATE1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU001',_'OUTLET1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU001',_'STORE1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU001',_'STORE2')   0.000000000000e+00
 LO BND       allocation_qty_('SKU002',_'DONATE1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU002',_'OUTLET1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU002',_'STORE1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU002',_'STORE2')   0.000000000000e+00
 LO BND       allocation_qty_('SKU003',_'DONATE1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU003',_'OUTLET1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU003',_'STORE1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU003',_'STORE2')   0.000000000000e+00
 LO BND       allocation_qty_('SKU004',_'DONATE1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU004',_'OUTLET1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU004',_'STORE1')   0.000000000000e+00
 LO BND       allocation_qty_('SKU004',_'STORE2')   0.000000000000e+00
 BV BND       is_allocated_('SKU001',_'DONATE1')
 BV BND       is_allocated_('SKU001',_'OUTLET1')
 BV BND       is_allocated_('SKU001',_'STORE1')
 BV BND       is_allocated_('SKU001',_'STORE2')
 BV BND       is_allocated_('SKU002',_'DONATE1')
 BV BND       is_allocated_('SKU002',_'OUTLET1')
 BV BND       is_allocated_('SKU002',_'STORE1')
 BV BND       is_allocated_('SKU002',_'STORE2')
 BV BND       is_allocated_('SKU003',_'DONATE1')
 BV BND       is_allocated_('SKU003',_'OUTLET1')
 BV BND       is_allocated_('SKU003',_'STORE1')
 BV BND       is_allocated_('SKU003',_'STORE2')
 BV BND       is_allocated_('SKU004',_'DONATE1')
 BV BND       is_allocated_('SKU004',_'OUTLET1')
 BV BND       is_allocated_('SKU004',_'STORE1')
 BV BND       is_allocated_('SKU004',_'STORE2')
ENDATA
