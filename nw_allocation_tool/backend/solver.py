import pulp
import pandas as pd
from schemas import OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule, OutletAssortmentRule, PushNewSKURule
from collections import defaultdict

# --- ABC Classification Function ---
def calculate_abc_classification_and_new_skus(
    sellout_df: pd.DataFrame, 
    product_master_df: pd.DataFrame, 
    all_channel_ids: list, # Now specific channel IDs like 'A90', 'B10'
    sellout_ean_col: str,
    sellout_channel_col: str, # This is 'store_code' from sellout.csv
    sellout_qty_col: str
):
    product_channel_abc_map = {}

    sellout_df[sellout_ean_col] = sellout_df[sellout_ean_col].astype(str)
    sellout_df[sellout_channel_col] = sellout_df[sellout_channel_col].astype(str)
    sellout_df[sellout_qty_col] = pd.to_numeric(sellout_df[sellout_qty_col], errors='coerce').fillna(0)
    
    # Pre-aggregate sellout by channel and EAN
    channel_product_sales_agg = sellout_df.groupby([sellout_channel_col, sellout_ean_col])[sellout_qty_col].sum().reset_index()

    for channel_id_from_list in all_channel_ids: # e.g., 'A90', 'B10' from ChannelList.xlsx
        # Filter aggregated sales for the current channel_id from the list
        # sellout_channel_col is the column in sellout_df that matches channel_id_from_list (e.g. 'store_code')
        channel_sales = channel_product_sales_agg[channel_product_sales_agg[sellout_channel_col] == channel_id_from_list].copy()

        if channel_sales.empty:
            for product_ean in product_master_df.index:
                product_channel_abc_map[(product_ean, channel_id_from_list)] = 'NEW'
            continue

        channel_sales = channel_sales.sort_values(by=sellout_qty_col, ascending=False)
        channel_sales['cumulative_sales'] = channel_sales[sellout_qty_col].cumsum()
        total_channel_sales = channel_sales[sellout_qty_col].sum()

        if total_channel_sales == 0:
            for product_ean in product_master_df.index:
                if product_ean in channel_sales[sellout_ean_col].values:
                     product_channel_abc_map[(product_ean, channel_id_from_list)] = 'C'
                else:
                     product_channel_abc_map[(product_ean, channel_id_from_list)] = 'NEW'
            continue
            
        channel_sales['cumulative_percent'] = channel_sales['cumulative_sales'] / total_channel_sales

        for _, row in channel_sales.iterrows():
            ean = row[sellout_ean_col]
            cum_percent = row['cumulative_percent']
            if cum_percent <= 0.2: 
                product_channel_abc_map[(ean, channel_id_from_list)] = 'A'
            elif cum_percent <= 0.8: 
                product_channel_abc_map[(ean, channel_id_from_list)] = 'B'
            else: 
                product_channel_abc_map[(ean, channel_id_from_list)] = 'C'

        sold_eans_in_this_channel = set(channel_sales[sellout_ean_col])
        for product_ean in product_master_df.index:
            if product_ean not in sold_eans_in_this_channel:
                product_channel_abc_map[(product_ean, channel_id_from_list)] = 'NEW'
            
    return product_channel_abc_map

def optimize_allocation(products_df: pd.DataFrame, channels_df: pd.DataFrame, inventory_df: pd.DataFrame,
                        demand_dict: dict, parameters: OptimizationParameters, existing_stock_dict: dict,
                        product_channel_abc_map: dict):
    products_df.index = products_df.index.astype(str)
    channels_df.index = channels_df.index.astype(str)
    products = products_df.index.tolist()
    channels = channels_df.index.tolist() # These are now 'A90', 'B10' etc.
    inventory_quantity = inventory_df.groupby('product_ean')['quantity'].sum().to_dict()
    coverage_rules_dict = {(r.channel_id, r.abc_class): r.coverage_days for r in parameters.coverage_days_rules}
    outlet_capacity_dict = {(r.channel_id, r.division, r.axe): r.max_skus for r in parameters.outlet_sku_capacity_rules}
    outlet_assortment_dict = {(r.metier, r.subaxis, r.brand): r.max_skus for r in parameters.outlet_assortment_rules}
    push_new_sku_lookup = {(r.division, r.subaxis): r.push_quantity for r in parameters.push_new_sku_rules}
    products_by_outlet_capacity_group = defaultdict(list)
    products_by_outlet_assortment_group = defaultdict(list)
    
    # outlet_channels list might not be strictly necessary if all channels in channels_df are outlets,
    # but good for explicit filtering if other types were to be mixed in channels_df later.
    outlet_channels = channels_df[channels_df['channel_type'] == 'outlet'].index.tolist()


    for p in products:
        division, axe = products_df.loc[p].get('division'), products_df.loc[p].get('axe')
        metier, subaxis, brand = products_df.loc[p].get('metier'), products_df.loc[p].get('subaxis'), products_df.loc[p].get('brand')
        if division and axe: products_by_outlet_capacity_group[(division, axe)].append(p)
        if metier and subaxis and brand: products_by_outlet_assortment_group[(metier, subaxis, brand)].append(p)

    model = pulp.LpProblem("InventoryAllocation", pulp.LpMaximize)
    x = pulp.LpVariable.dicts("allocation_qty", ((p, c) for p in products for c in channels), lowBound=0, cat='Integer')
    y = pulp.LpVariable.dicts("is_allocated", ((p, c) for p in products for c in channels), cat='Binary')
    model += (pulp.lpSum(x[p, c] for p in products for c in channels), "Maximize_Total_Allocation")

    for p in products: model += pulp.lpSum(x[p, c] for c in channels) <= inventory_quantity.get(p, 0), f"Supply_Product_{p}"
    
    for c in channels: # c is now 'A90', 'B10', etc.
        channel_type = channels_df.loc[c, 'channel_type'] # Should be 'outlet' for all
        if channel_type == 'outlet':
            # Outlet SKU Capacity rules (Max SKUs per Division/Axe for this specific outlet c)
            for (division, axe), group_products in products_by_outlet_capacity_group.items():
                max_skus = outlet_capacity_dict.get((c, division, axe)) # Rule should be specific to channel 'c'
                if max_skus is not None and max_skus >= 0:
                    model += pulp.lpSum(y[pg, c] for pg in group_products if pg in products) <= max_skus, f"Outlet_Capacity_SKU_{c}_{division}_{axe}"
        # else: # Logic for other channel types if they were present
            # capacity = pd.to_numeric(channels_df.loc[c, 'capacity'], errors='coerce')
            # if pd.notna(capacity) and capacity >= 0: model += pulp.lpSum(x[pp, c] for pp in products) <= capacity, f"Capacity_Channel_{c}"

    for c in channels: # c is 'A90', 'B10', etc.
        for p in products:
            abc_class = product_channel_abc_map.get((p, c), 'C') # Get ABC for specific product p and channel c
            current_stock_for_pc = existing_stock_dict.get((p, c), 0)
            if abc_class == 'NEW':
                div, sub = products_df.loc[p].get('division'), products_df.loc[p].get('subaxis')
                push_qty = push_new_sku_lookup.get((div, sub), 0) if div and sub else 0
                model += x[p, c] <= push_qty, f"Push_New_SKU_{p}_{c}"
            else: # A, B, C
                cov_days = coverage_rules_dict.get((c, abc_class)) # Coverage rule for specific channel c
                if cov_days is not None and cov_days >= 0:
                    # Demand for specific product p and channel c
                    adj_demand = demand_dict.get((p, c), 0) * parameters.seasonality_coefficient 
                    if adj_demand > 0:
                        allow_alloc = max(0, (adj_demand / 7.0) * cov_days - current_stock_for_pc)
                        model += x[p, c] <= allow_alloc, f"Max_Coverage_Days_{p}_{c}"
                    else: model += x[p, c] <= 0, f"Max_Coverage_Days_Zero_Demand_{p}_{c}"
    
    if parameters.restricted_brands_for_donation: # This logic remains, but donation channels won't be in 'channels_df' for now
        don_chans_from_df = channels_df[channels_df['channel_type'] == 'donation'].index.tolist()
        if don_chans_from_df: # Only proceed if donation channels are actually loaded and part of the current run
            restr_brands = set(parameters.restricted_brands_for_donation)
            for p in products:
                if products_df.loc[p].get('brand') in restr_brands:
                    for dc in don_chans_from_df: 
                        if dc in channels: model += x[p, dc] == 0, f"Restricted_Brand_{products_df.loc[p].get('brand')}_Prod_{p}_Chan_{dc}"
    
    # Outlet Assortment: These rules are per (metier, subaxis, brand) and apply to each outlet channel.
    # The outlet_channels list here should correctly contain 'A90', 'B10' etc. if they are type 'outlet'.
    for c_out in outlet_channels: # c_out will be 'A90', 'B10', etc.
        if c_out not in channels: continue # Should not happen if channels_df is loaded correctly
        for (metier, subaxis, brand), group_products in products_by_outlet_assortment_group.items():
            max_skus = outlet_assortment_dict.get((metier, subaxis, brand)) # Assortment rule is global for the combo
            if max_skus is not None and max_skus >= 0:
                # This constraint applies the global assortment rule to each specific outlet c_out
                model += pulp.lpSum(y[pg, c_out] for pg in group_products if pg in products) <= max_skus, f"Outlet_Assortment_{c_out}_{metier}_{subaxis}_{brand}"

    for p in products:
        M = inventory_quantity.get(p, 0)
        for c in channels:
            if M > 0:
                model += x[p, c] <= M * y[p, c], f"Link_x_y_Prod_{p}_Chan_{c}"
                model += y[p, c] * M >= x[p, c], f"Link_y_x_Prod_{p}_Chan_{c}"
            else:
                model += x[p, c] == 0, f"Force_x_zero_NoInv_Prod_{p}_Chan_{c}"
                model += y[p, c] == 0, f"Force_y_zero_NoInv_Prod_{p}_Chan_{c}"

    model.writeLP("allocation_model.lp")
    status_string = pulp.LpStatus[model.solve()]
    results = [{'product_sku': p, 'channel_id': c, 'quantity': int(round(x[p,c].value()))} 
               for p in products for c in channels if x[p,c].value() is not None and x[p,c].value() > 0.1] if status_string == 'Optimal' else []
    return model, status_string, results

def load_product_data(fp, ean_c='EAN', brand_c='Brand', div_c='Division', axe_c='Axe', sub_c='SubAxis', met_c='Metier', abc_c=None):
    df = pd.read_csv(fp)
    rn_map = {ean_c:'ean', brand_c:'brand', div_c:'division', axe_c:'axe', sub_c:'subaxis', met_c:'metier'}
    if abc_c and abc_c in df.columns: rn_map[abc_c] = 'abc_class'
    if ean_c not in df.columns: raise ValueError(f"EAN column '{ean_c}' not found in product master data file: {fp}")
    columns_to_process = list(set([k for k in rn_map.keys() if k in df.columns] + [ean_c]))
    columns_present_in_df = [col for col in columns_to_process if col in df.columns]
    pdf = df[columns_present_in_df].copy()
    pdf.rename(columns=rn_map, inplace=True)
    if 'ean' not in pdf.columns: raise ValueError(f"EAN column '{ean_c}' (expected 'ean') not found after renaming in {fp}.")
    if pdf['ean'].duplicated().any():
        print(f"Warning: Duplicate EANs found in {fp}. Using first occurrence.")
        pdf.drop_duplicates(subset=['ean'], keep='first', inplace=True)
    products_df_indexed = pdf.set_index('ean')
    for col in products_df_indexed.columns:
        products_df_indexed[col] = products_df_indexed[col].fillna('').astype(str)
    return products_df_indexed

def load_channel_data_from_channellist(file_path, sheet_name='Feuil1', channel_id_col='channel_id', channel_type_col='channel_type', delimiter=';'):
    """
    Loads channel data from ChannelList.xlsx.
    Expects columns like 'channel_type;channel_id' and splits them if a delimiter is present in header.
    """
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
    except ValueError:
        print(f"Warning: Sheet '{sheet_name}' not found in '{file_path}' for loading channel data. Returning empty DataFrame.")
        return pd.DataFrame(columns=['id', 'channel_type', 'capacity']).set_index('id')

    # Check for delimited header
    header = df.columns[0] # Assuming the relevant columns are the first two
    if delimiter in header and len(df.columns) >= 1: # If first col header contains delimiter
         # Attempt to parse assuming first column is 'channel_type;channel_id'
        if len(df.columns) == 1 and delimiter in df.columns[0]: # Single column with delimited header
            split_cols = df.columns[0].split(delimiter)
            if len(split_cols) == 2:
                # Rename the data columns based on the split header
                df.columns = split_cols
                actual_channel_type_col = split_cols[0].strip().strip('"')
                actual_channel_id_col = split_cols[1].strip().strip('"')
            else: # Could not determine columns from single delimited header
                 raise ValueError(f"Could not parse delimited header '{df.columns[0]}' into two columns in {file_path}")
        elif len(df.columns) >= 2: # Multiple columns, assume first two are the ones, check their headers
            col1_name = str(df.columns[0]).strip().strip('"')
            col2_name = str(df.columns[1]).strip().strip('"')
            if col1_name == channel_type_col and col2_name == channel_id_col:
                 actual_channel_type_col = col1_name
                 actual_channel_id_col = col2_name
            # Try to match based on provided default names if direct match fails
            elif channel_type_col in df.columns and channel_id_col in df.columns:
                actual_channel_type_col = channel_type_col
                actual_channel_id_col = channel_id_col
            else: # Fallback if headers are not exactly 'channel_type' and 'channel_id' but might be the first two
                print(f"Warning: Using first two columns from {file_path} as type and ID due to header mismatch. Expected '{channel_type_col}', '{channel_id_col}'. Got '{df.columns[0]}', '{df.columns[1]}'")
                actual_channel_type_col = df.columns[0]
                actual_channel_id_col = df.columns[1]
        else:
            raise ValueError(f"Insufficient columns in {file_path} sheet {sheet_name} to determine channel type and ID.")

    elif channel_type_col in df.columns and channel_id_col in df.columns: # Standard separate columns
        actual_channel_type_col = channel_type_col
        actual_channel_id_col = channel_id_col
    else:
        raise ValueError(f"Required columns '{channel_type_col}' and '{channel_id_col}' not found in {file_path} sheet {sheet_name}. Found: {df.columns.tolist()}")

    # Ensure columns are stripped of quotes and whitespace for access
    actual_channel_type_col = actual_channel_type_col.strip().strip('"')
    actual_channel_id_col = actual_channel_id_col.strip().strip('"')

    if actual_channel_id_col not in df.columns or actual_channel_type_col not in df.columns:
        raise ValueError(f"After parsing, required columns '{actual_channel_id_col}' or '{actual_channel_type_col}' not found. Parsed from input: type='{channel_type_col}', id='{channel_id_col}'.")

    # Create a list of dictionaries for DataFrame creation
    channel_data_list = []
    for _, row in df.iterrows():
        ch_id = str(row[actual_channel_id_col])
        ch_type = str(row[actual_channel_type_col])
        # For now, all channels from this list are 'outlet' as per user, capacity 0
        channel_data_list.append({
            'id': ch_id,
            'channel_type': 'outlet', # Override with 'outlet' for now
            'capacity': 0 
        })
    
    if not channel_data_list:
        return pd.DataFrame(columns=['id', 'channel_type', 'capacity']).set_index('id')

    channels_df = pd.DataFrame(channel_data_list).set_index('id')
    # channels_df.index = channels_df.index.astype(str) # Already string from ch_id
    # channels_df['channel_type'] = channels_df['channel_type'].astype(str) # Already string
    return channels_df


def load_inventory_data(fp, ean_c='ean_code', qty_c='StockToAllocate'):
    df = pd.read_csv(fp)
    if ean_c not in df.columns or qty_c not in df.columns: raise ValueError(f"Cols missing in {fp}")
    idf = df[[ean_c, qty_c]].rename(columns={ean_c:'product_ean', qty_c:'quantity'})
    idf['product_ean'] = idf['product_ean'].astype(str)
    idf['quantity'] = pd.to_numeric(idf['quantity'], errors='coerce').fillna(0)
    return idf.groupby('product_ean', as_index=False)['quantity'].sum()

def load_existing_stock_data(inst_fp, intr_fp, iec='barcode', icc='store_code', iqc='physical_quantity',itec='ean_material_code', itcc='store_code', itqc='order_quantity'):
    stock = defaultdict(float)
    df_i = pd.read_csv(inst_fp); df_it = pd.read_csv(intr_fp)
    for df,ec,cc,qc in [(df_i,iec,icc,iqc),(df_it,itec,itcc,itqc)]:
        if not all(c in df.columns for c in [ec,cc,qc]): raise ValueError(f"Cols missing")
        df = df[[ec,cc,qc]].rename(columns={ec:'ean',cc:'channel_id',qc:'quantity'})
        df[['ean','channel_id']] = df[['ean','channel_id']].astype(str)
        df['quantity'] = pd.to_numeric(df['quantity'],errors='coerce').fillna(0)
        for _,r in df.iterrows(): stock[(r['ean'],r['channel_id'])] += r['quantity']
    return dict(stock)

def load_demand_data(fp, ean_c='EAN', chan_c='ChannelID', dem_c='WeeklySalesQty'):
    df = pd.read_csv(fp); d_dict = {}
    if not all(c in df.columns for c in [ean_c,chan_c,dem_c]): raise ValueError(f"Cols missing in {fp}")
    df[[ean_c,chan_c]] = df[[ean_c,chan_c]].astype(str)
    df[dem_c] = pd.to_numeric(df[dem_c],errors='coerce').fillna(0)
    for _,r in df.groupby([ean_c,chan_c])[dem_c].sum().reset_index().iterrows(): d_dict[(r[ean_c],r[chan_c])] = r[dem_c]
    return d_dict

def load_coverage_rules_from_excel(fp, sheet='Feuil1', chan_c='Channel', abc_c='ABC Class', cov_c='Coverage (in days)'):
    df = pd.read_excel(fp, sheet_name=sheet); df.columns = df.columns.map(lambda x: str(x).strip().strip('"')); rules = []
    scc,sac,sccov = chan_c.strip('"'), abc_c.strip('"'), cov_c.strip('"')
    if not all(c in df.columns for c in [scc,sac,sccov]): raise ValueError(f"Cols missing in {fp} sheet {sheet}")
    for _,r in df.iterrows(): rules.append(CoverageDaysRule(channel_id=str(r[scc]),abc_class=str(r[sac]),coverage_days=int(r[sccov])))
    return rules

def load_outlet_sku_capacity_rules_from_excel(fp, sheet='Feuil1', chan_c='Channel', div_c='operational_division', axe_c='operational_axe_label', max_skus_c='Max capacity (in # of SKU)'):
    try: df = pd.read_excel(fp, sheet_name=sheet)
    except ValueError: print(f"Warn: Sheet '{sheet}' not in '{fp}'."); return []
    df.columns = df.columns.map(lambda x: str(x).strip().strip('"'))
    scc, sdc, sac, smsc = chan_c.strip('"'), div_c.strip('"'), axe_c.strip('"'), max_skus_c.strip('"')
    if not all(c in df.columns for c in [scc, sdc, sac, smsc]): 
        print(f"Warn: Cols missing for outlet SKU capacity in {fp} sheet {sheet}. Need: '{scc}', '{sdc}', '{sac}', '{smsc}'. Found: {df.columns.tolist()}. Skip."); return []
    rules = []
    for _, r in df.iterrows():
        try:
            rules.append(OutletSKUCapacityRule(channel_id=str(r[scc]), division=str(r[sdc]), axe=str(r[sac]), max_skus=int(r[smsc])))
        except Exception as e: print(f"Err processing row in outlet SKU capacity: {r}. Err: {e}. Skip.")
    return rules

def load_outlet_assortment_rules_from_excel(fp, sheet='Feuil1', met_c='operational_metier_label', sub_c='operational_sub_axe_label', brand_c='operational_signature_label', max_skus_c='# of SKUs to have in outlet (assortment)'):
    df = pd.read_excel(fp, sheet_name=sheet); df.columns = df.columns.map(lambda x: str(x).strip().strip('"')); rules = []
    smc,ssc,sbc,smsc = met_c.strip('"'), sub_c.strip('"'), brand_c.strip('"'), max_skus_c.strip('"')
    if not all(c in df.columns for c in [smc,ssc,sbc,smsc]): raise ValueError(f"Cols missing in {fp} sheet {sheet}")
    for _,r in df.iterrows(): rules.append(OutletAssortmentRule(metier=str(r[smc]),subaxis=str(r[ssc]),brand=str(r[sbc]),max_skus=int(r[smsc])))
    return rules

def load_push_new_sku_rules_from_excel(fp, sheet='Feuil1', div_c='operational_division', sub_c='operational_sub_axe_label', push_qty_c='Push Quantity if New SKU'):
    df = pd.read_excel(fp, sheet_name=sheet); df.columns = df.columns.map(lambda x: str(x).strip().strip('"')); rules = []
    sdc,ssc,spqc = div_c.strip('"'), sub_c.strip('"'), push_qty_c.strip('"')
    if not all(c in df.columns for c in [sdc,ssc,spqc]): raise ValueError(f"Cols missing in {fp} sheet {sheet}. Need '{sdc}', '{ssc}', '{spqc}'. Found: {df.columns.tolist()}")
    for _,r in df.iterrows(): rules.append(PushNewSKURule(division=str(r[sdc]),subaxis=str(r[ssc]),push_quantity=int(r[spqc])))
    return rules

if __name__ == '__main__':
    data_path = 'data'; excel_params_path = f'{data_path}/ExcelParameters'
    product_master_file = f'{data_path}/InputData/masterdata.csv'
    bad_stock_file = f'{data_path}/InputData/bad_stock_inventory.csv'
    in_store_inventory_file = f'{data_path}/InputData/in_store_inventory.csv'
    stock_in_transit_file = f'{data_path}/InputData/stock_in_transit.csv'
    sellout_file = f'{data_path}/InputData/sellout.csv'
    
    # Channel list file
    channel_list_file = f'{excel_params_path}/ChannelList.xlsx' # New file path

    # Parameters files (capacity_channel_file is still used for outlet-specific SKU capacity rules)
    capacity_channel_file = f'{excel_params_path}/CapacityPerChannel.xlsx'
    coverage_rules_file = f'{excel_params_path}/CoverageperABCperChannel.xlsx'
    assortment_rules_file = f'{excel_params_path}/AssortmentperSubaxeperSignature.xlsx'
    push_new_sku_file = f'{excel_params_path}/PushNewSKU.xlsx'

    try:
        print("Loading product data...")
        products_df = load_product_data(product_master_file, ean_c='product_gtin', brand_c='operational_signature_label', div_c='operational_division', axe_c='operational_axe_label', sub_c='operational_sub_axe_label', met_c='operational_metier_label')
        print(f"Loaded {len(products_df)} products.")

        print("Loading channel data from ChannelList.xlsx...")
        channels_df = load_channel_data_from_channellist(
            channel_list_file, 
            sheet_name='Feuil1', 
            channel_id_col='channel_id', # As per user's new file
            channel_type_col='channel_type' # As per user's new file
        )
        print(f"Loaded {len(channels_df)} channels from '{channel_list_file}'.")
        if channels_df.empty: raise ValueError("No channels loaded from ChannelList.xlsx.")

        print("Loading bad stock inventory...")
        inventory_df = load_inventory_data(bad_stock_file, ean_c='ean_code', qty_c='StockToAllocate')
        print(f"Loaded {inventory_df['quantity'].sum()} units of bad stock for {len(inventory_df)} EANs.")

        print("Loading existing stock...")
        existing_stock_dict = load_existing_stock_data(in_store_inventory_file, stock_in_transit_file)
        print(f"Loaded existing stock for {len(existing_stock_dict)} product-channel combinations.")

        print("Loading demand data...")
        demand_dict = load_demand_data(sellout_file, ean_c='barcode', chan_c='store_code', dem_c='total_items_weekly')
        print(f"Loaded demand for {len(demand_dict)} product-channel combinations.")

        print("Loading parameter rules...")
        coverage_rules = load_coverage_rules_from_excel(coverage_rules_file, sheet='Feuil1')
        print(f"Loaded {len(coverage_rules)} coverage rules.")
        
        outlet_sku_capacity_rules = load_outlet_sku_capacity_rules_from_excel(
            capacity_channel_file, sheet='Feuil1', chan_c='Channel', 
            div_c='operational_division', axe_c='operational_axe_label', 
            max_skus_c='Max capacity (in # of SKU)'
        )
        print(f"Loaded {len(outlet_sku_capacity_rules)} outlet SKU capacity rules.")
        
        assortment_rules = load_outlet_assortment_rules_from_excel(assortment_rules_file, sheet='Feuil1')
        print(f"Loaded {len(assortment_rules)} outlet assortment rules.")
        
        push_new_sku_rules = load_push_new_sku_rules_from_excel(push_new_sku_file, sheet='Feuil1') 
        print(f"Loaded {len(push_new_sku_rules)} push new SKU rules.")

        print("Calculating ABC classification...")
        raw_sellout_df = pd.read_csv(sellout_file) 
        
        # Pass all loaded channel IDs to ABC calculation
        all_loaded_channel_ids = channels_df.index.tolist()
        product_channel_abc_map = calculate_abc_classification_and_new_skus(
            raw_sellout_df,
            products_df, 
            all_channel_ids=all_loaded_channel_ids, # Pass the list of specific channel IDs
            sellout_ean_col='barcode', 
            sellout_channel_col='store_code', 
            sellout_qty_col='total_items_weekly'
        )
        print(f"Calculated ABC & NEW status for {len(product_channel_abc_map)} product-channel pairs.")

        seasonality_coefficient = 1.0
        try:
            s_input = input("Enter seasonality coefficient (e.g., 1.0): ")
            seasonality_coefficient = float(s_input)
            if seasonality_coefficient < 0: seasonality_coefficient = 1.0
        except ValueError: print("Invalid seasonality input. Using 1.0.")
        print(f"Using seasonality: {seasonality_coefficient}")

        params = OptimizationParameters(
            seasonality_coefficient=seasonality_coefficient, restricted_brands_for_donation=[],
            coverage_days_rules=coverage_rules, outlet_sku_capacity_rules=outlet_sku_capacity_rules,
            outlet_assortment_rules=assortment_rules, push_new_sku_rules=push_new_sku_rules
        )
        print("Parameters loaded.")

        print("\n--- Running Optimization ---")
        model, status, results = optimize_allocation(products_df, channels_df, inventory_df, demand_dict, params, existing_stock_dict, product_channel_abc_map)
        
        print(f"\nSolver Status: {status}")
        if status == 'Optimal':
            print("Allocation Results:"); results_df = pd.DataFrame(results)
            if not results_df.empty:
                results_df[['product_sku','channel_id']] = results_df[['product_sku','channel_id']].astype(str)
                print(results_df.to_string())
            else: print("No allocation.")
        else: print("Optimization not optimal. Check allocation_model.lp.")

    except FileNotFoundError as e: print(f"FNF Error: {e}")
    except ValueError as e: print(f"Value Error: {e}") 
    except Exception as e: print(f"Unexpected Error: {e}")
