# Bad Stock Allocation Optimizer

## Project Overview
The Bad Stock Allocation Optimizer is a web application designed to help L'Oréal's supply chain professionals efficiently allocate bad stock inventory to various second-life channels. The application uses linear programming techniques to optimize the allocation of products, maximizing value recovery while respecting various constraints.

## Business Context
In L'Oréal's supply chain operations, certain products become "bad stock" due to various reasons such as approaching expiration dates, packaging changes, or discontinued lines. Rather than destroying these products, which incurs costs and environmental impact, L'Oréal aims to remonetize them through various second-life channels:

- Outlet stores
- Friends & family sales
- Clearance websites
- NGO donations
- Other alternative channels

Each channel has different capacity constraints and value recovery rates. The challenge is to determine the optimal allocation of each product to these channels to maximize overall sell-through of the products, value recovery, which is also linked to sending the best products in the best channels.

## Key Features
1. **Constraint Modification**: Modify parameters used in constraints in the optimization problem
2. **Optimization Engine**: Uses PuLP to solve the linear programming problem
3. **Result Visualization**: Clear presentation of allocation results with charts and tables ; and also the input bad stock that we have to allocate
4. **Manual Adjustments**: Allow supply chain experts to modify the proposed solution
5. **Excel Export**: Export results for SAP order creation
6. **Scenario Management**: Save and load different allocation scenarios

## Target Users
Supply chain professionals at L'Oréal who:
- Are familiar with Excel-based workflows
- Need to make data-driven decisions about bad stock allocation
- Have expert knowledge that may need to supplement algorithmic solutions