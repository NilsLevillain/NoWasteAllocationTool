import unittest
from unittest import mock
import pandas as pd
from pandas.testing import assert_frame_equal
import os
import sys
import logging
from io import StringIO

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.utils import (
    load_products_df,
    load_channels_df,
    load_inventory_df,
    load_existing_stock_dict,
    load_demand_dict,
    load_optimization_rules,
    load_sellin_ranking_dict, # New import
    _get_channel_id_from_row
)
from backend.schemas import (
    CoverageDaysRule,
    OutletSKUCapacityRule,
    OutletAssortmentRule,
    PushNewSKURule
)

# Do not disable logging globally, rely on assertLogs to manage context
# logging.disable(logging.CRITICAL) 

class TestUtilsDataLoading(unittest.TestCase):

    def setUp(self):
        # Create dummy data directories if they don't exist
        self.test_data_dir = os.path.join(project_root, 'tests', 'temp_test_data')
        self.excel_params_dir = os.path.join(self.test_data_dir, 'ExcelParameters')
        self.input_data_dir = os.path.join(self.test_data_dir, 'InputData')
        os.makedirs(self.excel_params_dir, exist_ok=True)
        os.makedirs(self.input_data_dir, exist_ok=True)

    def tearDown(self):
        # Clean up dummy data directories and files
        for root, dirs, files in os.walk(self.test_data_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        if os.path.exists(self.test_data_dir):
            os.rmdir(self.test_data_dir)

    # --- Tests for load_products_df ---
    def test_load_products_df_success(self):
        csv_content = "product_gtin;operational_signature_label;operational_division;operational_axe_label;operational_sub_axe_label;operational_metier_label;internal_product_code;product_description;unit_cost\n00000000000001;BrandA;DivX;Axe1;Sub1;MetA;SKU1;Desc1;10.5\nEAN2;BrandB;DivY;Axe2;Sub2;MetB;SKU2;Desc2;20.0"
        file_path = os.path.join(self.input_data_dir, 'products_ok.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)

        expected_data = {
            'ean': ['1', 'EAN2'],
            'signature': ['BrandA', 'BrandB'],
            'div': ['DivX', 'DivY'],
            'axe': ['Axe1', 'Axe2'],
            'subAxe': ['Sub1', 'Sub2'],
            'metier': ['MetA', 'MetB'],
            'sku': ['SKU1', 'SKU2'],
            'description': ['Desc1', 'Desc2'],
            'cogs': [10.5, 20.0]
        }
        expected_df = pd.DataFrame(expected_data).set_index('ean')
        
        result_df = load_products_df(file_path)
        assert_frame_equal(result_df, expected_df, check_dtype=False)

    def test_load_products_df_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_products_df(os.path.join(self.input_data_dir, 'non_existent_products.csv'))

    def test_load_products_df_missing_required_columns(self):
        # Missing operational_division, operational_axe_label, etc.
        csv_content = "product_gtin;operational_signature_label\nEAN1;BrandA"
        file_path = os.path.join(self.input_data_dir, 'products_missing_cols.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)
        with self.assertRaisesRegex(ValueError, "Required column 'operational_division' not found"):
            load_products_df(file_path)

    def test_load_products_df_duplicate_eans(self):
        csv_content = "product_gtin;operational_signature_label;operational_division;operational_axe_label;operational_sub_axe_label;operational_metier_label;internal_product_code;product_description;unit_cost\nEAN1;BrandA;DivX;Axe1;Sub1;MetA;SKU1;Desc1;10.5\nEAN1;BrandX_ignored;DivY;Axe2;Sub2;MetB;SKU2;Desc2;20.0"
        file_path = os.path.join(self.input_data_dir, 'products_dup_ean.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)
        
        expected_data = {
            'ean': ['EAN1'],
            'signature': ['BrandA'],
            'div': ['DivX'],
            'axe': ['Axe1'],
            'subAxe': ['Sub1'],
            'metier': ['MetA'],
            'sku': ['SKU1'],
            'description': ['Desc1'],
            'cogs': [10.5]
        }
        expected_df = pd.DataFrame(expected_data).set_index('ean')
        
        # Capture warnings
        with self.assertLogs(logger='backend.utils', level='WARNING') as cm:
            result_df = load_products_df(file_path)
        self.assertTrue(any("Duplicate EANs found" in message for message in cm.output))
        assert_frame_equal(result_df, expected_df, check_dtype=False)

    def test_load_products_df_empty_file(self):
        file_path = os.path.join(self.input_data_dir, 'products_empty.csv')
        with open(file_path, 'w') as f:
            f.write("product_gtin;operational_signature_label;operational_division;operational_axe_label;operational_sub_axe_label;operational_metier_label;internal_product_code;product_description;unit_cost\n") # Only header
        
        result_df = load_products_df(file_path)
        self.assertTrue(result_df.empty)

    def test_load_products_df_only_header(self):
        csv_content = "product_gtin;operational_signature_label;operational_division;operational_axe_label;operational_sub_axe_label;operational_metier_label;internal_product_code;product_description;unit_cost"
        file_path = os.path.join(self.input_data_dir, 'products_header_only.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)
        
        result_df = load_products_df(file_path)
        self.assertTrue(result_df.empty)

    def test_load_products_df_ean_normalization_and_cogs_conversion(self):
        csv_content = "product_gtin;operational_signature_label;operational_division;operational_axe_label;operational_sub_axe_label;operational_metier_label;internal_product_code;product_description;unit_cost\n00000000000001;BrandA;DivX;Axe1;Sub1;MetA;SKU1;Desc1;10.5\n00000000000002;BrandB;DivY;Axe2;Sub2;MetB;SKU2;Desc2;invalid_cogs\n0;BrandC;DivZ;Axe3;Sub3;MetC;SKU3;Desc3;30"
        file_path = os.path.join(self.input_data_dir, 'products_ean_norm.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)

        expected_data = {
            'ean': ['1', '2', ''], # '0' EAN becomes empty after stripping
            'signature': ['BrandA', 'BrandB', 'BrandC'],
            'div': ['DivX', 'DivY', 'DivZ'],
            'axe': ['Axe1', 'Axe2', 'Axe3'],
            'subAxe': ['Sub1', 'Sub2', 'Sub3'],
            'metier': ['MetA', 'MetB', 'MetC'],
            'sku': ['SKU1', 'SKU2', 'SKU3'],
            'description': ['Desc1', 'Desc2', 'Desc3'],
            'cogs': [10.5, 0.0, 30.0] # invalid_cogs becomes 0.0
        }
        expected_df = pd.DataFrame(expected_data)
        # Filter out rows where EAN became empty after stripping (e.g. if it was just "0" or "00")
        expected_df = expected_df[expected_df['ean'] != ''].set_index('ean')
        
        result_df = load_products_df(file_path)
        assert_frame_equal(result_df, expected_df, check_dtype=False)


    # --- Tests for _get_channel_id_from_row ---
    def test_get_channel_id_from_row_success(self):
        data = {'channel_id_string': 'CH1', 'other_col': 'data'}
        row = pd.Series(data)
        self.assertEqual(_get_channel_id_from_row(row, ['channel_id', 'channel_id_string']), 'CH1')

    def test_get_channel_id_from_row_fallback(self):
        data = {'Channel ID': 'CH2', 'other_col': 'data'}
        row = pd.Series(data)
        self.assertEqual(_get_channel_id_from_row(row, ['channel_id_string', 'Channel ID']), 'CH2')

    def test_get_channel_id_from_row_not_found(self):
        data = {'some_other_id': 'CH3', 'other_col': 'data'}
        row = pd.Series(data)
        with self.assertRaisesRegex(KeyError, "Could not find channel identifier"):
            _get_channel_id_from_row(row, ['channel_id', 'channel_id_string'])

    # --- Tests for load_channels_df ---
    def test_load_channels_df_success_standard_cols(self):
        # Create a dummy Excel file
        excel_file_path = os.path.join(self.excel_params_dir, 'channels_ok.xlsx')
        df_excel = pd.DataFrame({
            'channel_id': ['CH1', 'CH2'],
            'channel_type': ['store', 'outlet'],
            'other_data': ['A', 'B']
        })
        df_excel.to_excel(excel_file_path, sheet_name='Feuil1', index=False)

        expected_data = {
            'id': ['CH1', 'CH2'],
            'channel_type': ['store', 'outlet'], # In utils, it defaults to 'outlet' if not specified, but here we provide it
            'capacity': [0, 0] # Default capacity
        }
        expected_df = pd.DataFrame(expected_data).set_index('id')
        
        # Modify load_channels_df in utils.py to not override channel_type if provided
        # For now, testing current behavior where it might override.
        # The test should reflect the actual implementation.
        # The current implementation of load_channels_df in utils.py uses the provided channel_type.
        
        result_df = load_channels_df(excel_file_path, sheet_name='Feuil1', channel_id_col='channel_id', channel_type_col='channel_type')
        assert_frame_equal(result_df, expected_df, check_dtype=False)

    def test_load_channels_df_success_delimited_header(self):
        excel_file_path = os.path.join(self.excel_params_dir, 'channels_delimited.xlsx')
        # Simulate a single column with delimited header
        # Pandas read_excel will read "type;id" as the actual column name if not handled.
        # The function load_channels_df is designed to split this.
        df_excel = pd.DataFrame({
            'channel_type;channel_id': ['store;CH10', 'outlet;CH11']
        })
        df_excel.to_excel(excel_file_path, sheet_name='Feuil1', index=False)

        expected_data = {
            'id': ['CH10', 'CH11'],
            'channel_type': ['store', 'outlet'],
            'capacity': [0, 0]
        }
        expected_df = pd.DataFrame(expected_data).set_index('id')
        
        result_df = load_channels_df(excel_file_path, sheet_name='Feuil1', delimiter=';')
        assert_frame_equal(result_df, expected_df, check_dtype=False)


    def test_load_channels_df_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_channels_df(os.path.join(self.excel_params_dir, 'non_existent_channels.xlsx'))

    def test_load_channels_df_sheet_not_found(self):
        excel_file_path = os.path.join(self.excel_params_dir, 'channels_no_sheet.xlsx')
        df_excel = pd.DataFrame({'channel_id': ['CH1']}) # Dummy content in default sheet
        df_excel.to_excel(excel_file_path, index=False) # Saved to default sheet "Sheet1"

        # Expecting an empty DataFrame as per function's behavior
        expected_df = pd.DataFrame(columns=['id', 'channel_type', 'capacity']).set_index('id')
        with self.assertLogs(logger='backend.utils', level='WARNING') as cm:
            result_df = load_channels_df(excel_file_path, sheet_name='NonExistentSheet')
        self.assertTrue(any("Sheet 'NonExistentSheet' not found" in message for message in cm.output))
        assert_frame_equal(result_df, expected_df, check_dtype=False)


    def test_load_channels_df_missing_columns(self):
        excel_file_path = os.path.join(self.excel_params_dir, 'channels_missing_cols.xlsx')
        df_excel = pd.DataFrame({'id_only': ['CH1']})
        df_excel.to_excel(excel_file_path, sheet_name='Feuil1', index=False)
        
        with self.assertRaisesRegex(ValueError, "Required columns 'channel_type' and 'channel_id' not found"):
            load_channels_df(excel_file_path, sheet_name='Feuil1', channel_id_col='channel_id', channel_type_col='channel_type')
            
    def test_load_channels_df_empty_file_returns_empty_df(self):
        excel_file_path = os.path.join(self.excel_params_dir, 'channels_empty.xlsx')
        # Create an empty excel file (or one that pandas reads as empty for the sheet)
        pd.DataFrame().to_excel(excel_file_path, sheet_name='Feuil1', index=False)
        
        # The function should return an empty DataFrame with specific columns
        expected_df = pd.DataFrame(columns=['id', 'channel_type', 'capacity']).set_index('id')
        with self.assertLogs(logger='backend.utils', level='WARNING') as cm: # Expect a warning for no data loaded
            result_df = load_channels_df(excel_file_path, sheet_name='Feuil1')
        self.assertTrue(any("No channel data loaded" in message for message in cm.output))
        assert_frame_equal(result_df, expected_df, check_dtype=False)

    # --- Tests for load_inventory_df ---
    def test_load_inventory_df_success(self):
        csv_content = (
            "ean_code;StockToAllocate;AvailableStock;plant;plant_description;FlagExcess6months;FlagExcess12months\n"
            "EAN1;100;90;PL1;Plant A;0;0\n"
            "EAN2;50;45;PL1;Plant A;0;0\n"
            "EAN1;20;15;PL2;Plant B;1;0\n" # EAN1 has multiple entries, different plant
            "EAN3;30;25;PL1;Plant A;1;1\n" # Excess 6 & 12
            "EAN4;40;35;PL2;Plant B;1;0\n" # Excess 6
            "EAN5;60;55;PL1;Plant A;0;1\n" # Excess 12
            "EAN6;70;65;PL2;Plant B;0;0\n" # Obsolete (default)
        )
        file_path = os.path.join(self.input_data_dir, 'inventory_ok.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)

        expected_data = {
            'product_ean': ['EAN1', 'EAN1', 'EAN2', 'EAN3', 'EAN4', 'EAN5', 'EAN6'],
            'plant': ['PL1', 'PL2', 'PL1', 'PL1', 'PL2', 'PL1', 'PL2'],
            'quantity': [100, 20, 50, 30, 40, 60, 70], # Summed by EAN-Plant, not total EAN
            'available_stock': [90, 15, 45, 25, 35, 55, 65],
            'stockOrigin': ['Plant A', 'Plant B', 'Plant A', 'Plant A', 'Plant B', 'Plant A', 'Plant B'],
            'flagExcess6months': [0, 1, 0, 1, 1, 0, 0],
            'flagExcess12months': [0, 0, 0, 1, 0, 1, 0],
            'bad_stock_type': ['Obsolete', 'Excess 6 months', 'Obsolete', 'Excess 6 & 12 months', 'Excess 6 months', 'Excess 12 months', 'Obsolete']
        }
        expected_df = pd.DataFrame(expected_data)
        # Sort by product_ean and plant for consistent comparison
        expected_df = expected_df.sort_values(by=['product_ean', 'plant']).reset_index(drop=True)
        
        result_df = load_inventory_df(file_path)
        result_df = result_df.sort_values(by=['product_ean', 'plant']).reset_index(drop=True)
        assert_frame_equal(result_df, expected_df, check_dtype=False)

    def test_load_inventory_df_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_inventory_df(os.path.join(self.input_data_dir, 'non_existent_inventory.csv'))

    def test_load_inventory_df_missing_required_columns(self):
        csv_content = "ean_code;StockToAllocate\nEAN1;100" # Missing available_stock, plant, flags
        file_path = os.path.join(self.input_data_dir, 'inventory_missing_cols.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)
        with self.assertRaisesRegex(ValueError, "Required columns \\['AvailableStock', 'plant', 'plant_description', 'FlagExcess6months', 'FlagExcess12months'\\] missing"):
            load_inventory_df(file_path)

    def test_load_inventory_df_invalid_quantity_and_flags(self):
        csv_content = (
            "ean_code;StockToAllocate;AvailableStock;plant;plant_description;FlagExcess6months;FlagExcess12months\n"
            "EAN1;100;90;PL1;Plant A;0;0\n"
            "EAN2;fifty;45;PL1;Plant A;invalid;0\n" # Invalid qty, invalid flag
            "EAN3;30;25;PL1;Plant A;1;invalid\n" # Invalid flag
        )
        file_path = os.path.join(self.input_data_dir, 'inventory_invalid_qty.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)

        expected_data = {
            'product_ean': ['EAN1', 'EAN2', 'EAN3'],
            'plant': ['PL1', 'PL1', 'PL1'],
            'quantity': [100, 0, 30], # 'fifty' coerced to 0
            'available_stock': [90, 45, 25],
            'stockOrigin': ['Plant A', 'Plant A', 'Plant A'],
            'flagExcess6months': [0, 0, 1], # 'invalid' coerced to 0
            'flagExcess12months': [0, 0, 0], # 'invalid' coerced to 0
            'bad_stock_type': ['Obsolete', 'Obsolete', 'Excess 6 months'] # Based on coerced flags
        }
        expected_df = pd.DataFrame(expected_data).sort_values(by=['product_ean', 'plant']).reset_index(drop=True)
        
        result_df = load_inventory_df(file_path).sort_values(by=['product_ean', 'plant']).reset_index(drop=True)
        assert_frame_equal(result_df, expected_df, check_dtype=False)

    def test_load_inventory_df_empty_file(self):
        file_path = os.path.join(self.input_data_dir, 'inventory_empty.csv')
        with open(file_path, 'w') as f:
            f.write("ean_code;StockToAllocate;AvailableStock;plant;plant_description;FlagExcess6months;FlagExcess12months\n")

        result_df = load_inventory_df(file_path)
        self.assertTrue(result_df.empty) # Should be empty, not just quantity > 0

    # --- Tests for load_existing_stock_dict ---
    def test_load_existing_stock_dict_success(self):
        instore_content = "barcode;store_code;physical_quantity\nEAN1;CH1;10\nEAN2;CH1;5\nEAN1;CH2;7"
        intransit_content = "ean_material_code;store_code;order_quantity\nEAN1;CH1;3\nEAN3;CH2;12"
        
        instore_file_path = os.path.join(self.input_data_dir, 'instore_stock.csv')
        intransit_file_path = os.path.join(self.input_data_dir, 'intransit_stock.csv')

        with open(instore_file_path, 'w') as f:
            f.write(instore_content)
        with open(intransit_file_path, 'w') as f:
            f.write(intransit_content)

        expected_stock = {
            ('EAN1', 'CH1'): 13.0, # 10 (instore) + 3 (intransit)
            ('EAN2', 'CH1'): 5.0,
            ('EAN1', 'CH2'): 7.0,
            ('EAN3', 'CH2'): 12.0
        }
        result_stock = load_existing_stock_dict(instore_file_path, intransit_file_path)
        self.assertEqual(result_stock, expected_stock)

    def test_load_existing_stock_dict_one_file_not_found(self):
        instore_content = "barcode;store_code;physical_quantity\nEAN1;CH1;10"
        instore_file_path = os.path.join(self.input_data_dir, 'instore_stock_only.csv')
        with open(instore_file_path, 'w') as f:
            f.write(instore_content)
        
        with self.assertRaises(FileNotFoundError):
            load_existing_stock_dict(instore_file_path, os.path.join(self.input_data_dir, 'non_existent_intransit.csv'))
        with self.assertRaises(FileNotFoundError):
            load_existing_stock_dict(os.path.join(self.input_data_dir, 'non_existent_instore.csv'), instore_file_path) # Using instore_file_path as a dummy for intransit

    def test_load_existing_stock_dict_missing_cols_instore(self):
        instore_content = "barcode;physical_quantity\nEAN1;10" # Missing store_code
        intransit_content = "ean_material_code;store_code;order_quantity\nEAN1;CH1;3"
        instore_file_path = os.path.join(self.input_data_dir, 'instore_missing_cols.csv')
        intransit_file_path = os.path.join(self.input_data_dir, 'intransit_ok_for_missing.csv')
        with open(instore_file_path, 'w') as f:
            f.write(instore_content)
        with open(intransit_file_path, 'w') as f:
            f.write(intransit_content)
        
        with self.assertRaisesRegex(ValueError, "Required columns missing"):
            load_existing_stock_dict(instore_file_path, intransit_file_path)

    def test_load_existing_stock_dict_missing_cols_intransit(self):
        instore_content = "barcode;store_code;physical_quantity\nEAN1;CH1;10"
        intransit_content = "ean_material_code;order_quantity\nEAN1;3" # Missing store_code
        instore_file_path = os.path.join(self.input_data_dir, 'instore_ok_for_missing.csv')
        intransit_file_path = os.path.join(self.input_data_dir, 'intransit_missing_cols.csv')
        with open(instore_file_path, 'w') as f:
            f.write(instore_content)
        with open(intransit_file_path, 'w') as f:
            f.write(intransit_content)
        
        with self.assertRaisesRegex(ValueError, "Required columns missing"):
            load_existing_stock_dict(instore_file_path, intransit_file_path)

    def test_load_existing_stock_dict_empty_files(self):
        instore_content = "barcode;store_code;physical_quantity\n"
        intransit_content = "ean_material_code;store_code;order_quantity\n"
        instore_file_path = os.path.join(self.input_data_dir, 'instore_empty.csv')
        intransit_file_path = os.path.join(self.input_data_dir, 'intransit_empty.csv')
        with open(instore_file_path, 'w') as f:
            f.write(instore_content)
        with open(intransit_file_path, 'w') as f:
            f.write(intransit_content)
            
        result_stock = load_existing_stock_dict(instore_file_path, intransit_file_path)
        self.assertEqual(result_stock, {})

    # --- Tests for load_demand_dict ---
    def test_load_demand_dict_success(self):
        csv_content = "barcode;store_code;total_items_weekly\nEAN1;CH1;50\nEAN2;CH1;30\nEAN1;CH1;10" # Duplicate EAN1,CH1
        file_path = os.path.join(self.input_data_dir, 'demand_ok.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)

        expected_demand = {
            ('EAN1', 'CH1'): 60.0, # 50 + 10
            ('EAN2', 'CH1'): 30.0
        }
        result_demand = load_demand_dict(file_path)
        self.assertEqual(result_demand, expected_demand)

    def test_load_demand_dict_file_not_found(self):
        # Function should return empty dict and log warning
        with self.assertLogs(logger='backend.utils', level='WARNING') as cm:
            result_demand = load_demand_dict(os.path.join(self.input_data_dir, 'non_existent_demand.csv'))
        self.assertEqual(result_demand, {})
        self.assertTrue(any("Demand data file not found" in message for message in cm.output))

    def test_load_demand_dict_missing_columns(self):
        csv_content = "barcode;total_items_weekly\nEAN1;50" # Missing store_code
        file_path = os.path.join(self.input_data_dir, 'demand_missing_cols.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)
        with self.assertRaisesRegex(ValueError, "Required columns missing"):
            load_demand_dict(file_path)

    def test_load_demand_dict_invalid_qty(self):
        csv_content = "barcode;store_code;total_items_weekly\nEAN1;CH1;50\nEAN2;CH1;thirty"
        file_path = os.path.join(self.input_data_dir, 'demand_invalid_qty.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)
        expected_demand = {
            ('EAN1', 'CH1'): 50.0,
            ('EAN2', 'CH1'): 0.0 # 'thirty' coerced to 0
        }
        result_demand = load_demand_dict(file_path)
        self.assertEqual(result_demand, expected_demand)

    def test_load_demand_dict_empty_file(self):
        file_path = os.path.join(self.input_data_dir, 'demand_empty.csv')
        with open(file_path, 'w') as f:
            f.write("barcode;store_code;total_items_weekly\n")
        result_demand = load_demand_dict(file_path)
        self.assertEqual(result_demand, {})

    # --- Tests for load_optimization_rules ---
    def test_load_optimization_rules_coverage_days_success(self):
        excel_content = pd.DataFrame({
            'channel_id': ['CH1', 'CH2'],
            'abc_class': ['A', 'B'],
            'coverage_days': [7, 14]
        })
        file_path = os.path.join(self.excel_params_dir, 'coverage_rules.xlsx')
        excel_content.to_excel(file_path, sheet_name='Feuil1', index=False)

        expected_rules = [
            CoverageDaysRule(channel_id='CH1', abc_class='A', coverage_days=7),
            CoverageDaysRule(channel_id='CH2', abc_class='B', coverage_days=14)
        ]
        column_mappings = {'channel_id': 'channel_id', 'abc_class': 'abc_class', 'coverage_days': 'coverage_days'}
        result_rules = load_optimization_rules(file_path, CoverageDaysRule, **column_mappings)
        self.assertEqual([r.model_dump() for r in result_rules], [e.model_dump() for e in expected_rules])

    def test_load_optimization_rules_outlet_sku_capacity_success(self):
        excel_content = pd.DataFrame({
            'Channel': ['Outlet1', 'Outlet2'], # Note: Different column name as per original files
            'operational_division': ['DivX', 'DivY'],
            'operational_axe_label': ['Axe1', 'Axe2'],
            'Max capacity (in # of SKU)': [100, 150] # Note: Different column name
        })
        file_path = os.path.join(self.excel_params_dir, 'capacity_rules.xlsx')
        excel_content.to_excel(file_path, sheet_name='Feuil1', index=False)

        expected_rules = [
            OutletSKUCapacityRule(channel_id='Outlet1', division='DivX', axe='Axe1', max_skus=100),
            OutletSKUCapacityRule(channel_id='Outlet2', division='DivY', axe='Axe2', max_skus=150)
        ]
        column_mappings = {
            'Channel': 'channel_id', 
            'operational_division': 'division', 
            'operational_axe_label': 'axe', 
            'Max capacity (in # of SKU)': 'max_skus'
        }
        result_rules = load_optimization_rules(file_path, OutletSKUCapacityRule, **column_mappings)
        self.assertEqual([r.model_dump() for r in result_rules], [e.model_dump() for e in expected_rules])

    def test_load_optimization_rules_outlet_assortment_success(self):
        excel_content = pd.DataFrame({
            'operational_metier_label': ['Met1', 'Met2'],
            'operational_sub_axe_label': ['SubAxeA', 'SubAxeB'],
            'operational_signature_label': ['BrandX', 'BrandY'],
            'max_skus': [5, 10]
        })
        file_path = os.path.join(self.excel_params_dir, 'assortment_rules.xlsx')
        excel_content.to_excel(file_path, sheet_name='Feuil1', index=False)

        expected_rules = [
            OutletAssortmentRule(metier='Met1', subaxis='SubAxeA', brand='BrandX', max_skus=5),
            OutletAssortmentRule(metier='Met2', subaxis='SubAxeB', brand='BrandY', max_skus=10)
        ]
        column_mappings = {
            'operational_metier_label': 'metier', 
            'operational_sub_axe_label': 'subaxis', 
            'operational_signature_label': 'brand', 
            'max_skus': 'max_skus'
        }
        result_rules = load_optimization_rules(file_path, OutletAssortmentRule, **column_mappings)
        self.assertEqual([r.model_dump() for r in result_rules], [e.model_dump() for e in expected_rules])

    def test_load_optimization_rules_push_new_sku_success(self):
        excel_content = pd.DataFrame({
            'operational_division': ['DivX', 'DivY'],
            'operational_sub_axe_label': ['SubAxeA', 'SubAxeB'],
            'Push Quantity if New SKU': [20, 30]
        })
        file_path = os.path.join(self.excel_params_dir, 'push_rules.xlsx')
        excel_content.to_excel(file_path, sheet_name='Feuil1', index=False)

        expected_rules = [
            PushNewSKURule(division='DivX', subaxis='SubAxeA', push_quantity=20),
            PushNewSKURule(division='DivY', subaxis='SubAxeB', push_quantity=30)
        ]
        column_mappings = {
            'operational_division': 'division', 
            'operational_sub_axe_label': 'subaxis', 
            'Push Quantity if New SKU': 'push_quantity'
        }
        result_rules = load_optimization_rules(file_path, PushNewSKURule, **column_mappings)
        self.assertEqual([r.model_dump() for r in result_rules], [e.model_dump() for e in expected_rules])

    def test_load_optimization_rules_file_not_found(self):
        column_mappings = {'channel_id': 'channel_id', 'abc_class': 'abc_class', 'coverage_days': 'coverage_days'}
        with self.assertRaises(FileNotFoundError):
            load_optimization_rules(os.path.join(self.excel_params_dir, 'non_existent_rules.xlsx'), CoverageDaysRule, **column_mappings)

    def test_load_optimization_rules_sheet_not_found(self):
        file_path = os.path.join(self.excel_params_dir, 'rules_no_sheet.xlsx')
        pd.DataFrame({'channel_id': ['CH1']}).to_excel(file_path, index=False) # Dummy content in default sheet
        
        column_mappings = {'channel_id': 'channel_id', 'abc_class': 'abc_class', 'coverage_days': 'coverage_days'}
        with self.assertLogs(logger='backend.utils', level='WARNING') as cm:
            result_rules = load_optimization_rules(file_path, CoverageDaysRule, sheet_name='NonExistentSheet', **column_mappings)
        self.assertEqual(result_rules, [])
        self.assertTrue(any("Sheet 'NonExistentSheet' not found" in message for message in cm.output))

    def test_load_optimization_rules_missing_columns(self):
        excel_content = pd.DataFrame({'channel_id': ['CH1']}) # Missing abc_class, coverage_days
        file_path = os.path.join(self.excel_params_dir, 'rules_missing_cols.xlsx')
        excel_content.to_excel(file_path, sheet_name='Feuil1', index=False)
        
        column_mappings = {'channel_id': 'channel_id', 'abc_class': 'abc_class', 'coverage_days': 'coverage_days'}
        # Updated regex to match the more specific error message from the latest utils.py
        with self.assertRaisesRegex(ValueError, "Required Excel columns missing.*CoverageDaysRule: \\['abc_class', 'coverage_days'\\]"):
            load_optimization_rules(file_path, CoverageDaysRule, **column_mappings)

    def test_load_optimization_rules_invalid_data_type(self):
        excel_content = pd.DataFrame({
            'channel_id': ['CH1'], 'abc_class': ['A'], 'coverage_days': ['seven'] # Invalid int
        })
        file_path = os.path.join(self.excel_params_dir, 'rules_invalid_type.xlsx')
        excel_content.to_excel(file_path, sheet_name='Feuil1', index=False)
        
        column_mappings = {'channel_id': 'channel_id', 'abc_class': 'abc_class', 'coverage_days': 'coverage_days'}
        # The function's pd.to_numeric with errors='coerce' and fillna(0) will convert 'seven' to 0
        # Pydantic will then validate. If 'seven' was critical and should error, the loader needs adjustment.
        # Current behavior: 'seven' -> 0 due to pd.to_numeric(..., errors='coerce') and subsequent logic.
        # Pydantic model CoverageDaysRule expects coverage_days to be an int.
        # So, CoverageDaysRule(channel_id='CH1', abc_class='A', coverage_days=0) should be created.
        
        expected_rules = [CoverageDaysRule(channel_id='CH1', abc_class='A', coverage_days=0)]
        
        # Check that the rule is correctly parsed and an INFO log for successful loading is present.
        # Also ensure no ERROR log for this specific row processing is generated.
        with self.assertLogs(logger='backend.utils', level='INFO') as cm_info:
            result_rules = load_optimization_rules(file_path, CoverageDaysRule, **column_mappings)
        
        self.assertEqual([r.model_dump() for r in result_rules], [e.model_dump() for e in expected_rules])
        self.assertTrue(any(f"Loaded {len(expected_rules)} CoverageDaysRule rules" in log_record.getMessage() for log_record in cm_info.records))

        # To ensure no error was logged for this specific processing, we can check the full log output.
        # This is a bit more involved if other errors could legitimately occur.
        # For this test, we expect no "Error processing row" for this specific input.
        # A simple way is to check that the number of error logs didn't increase unexpectedly,
        # or specifically check that the "Error processing row" message for this row isn't there.
        # For now, confirming the successful load and INFO log is the primary goal.
        # The test_load_optimization_rules_row_processing_error will confirm error logging path.

    def test_load_optimization_rules_row_processing_error(self):
        # Create data that will cause a Pydantic validation error after initial processing
        # e.g. make a required field for the Pydantic model effectively null after coercion
        # Or provide a type that Pydantic cannot handle even after our string/int coercion.
        # Let's assume 'abc_class' in CoverageDaysRule must be one of 'A', 'B', 'C', 'NEW'.
        # Providing 'Z' should cause a Pydantic ValidationError if such a constraint exists.
        # If not, this test might still not capture an error if Pydantic simply accepts any string.
        # This test checks that an invalid 'abc_class' causes a Pydantic ValidationError,
        # which should be caught and logged as an error by load_optimization_rules.
        excel_content = pd.DataFrame({
            'channel_id': ['CH_ERR'], 
            'abc_class': ['Z_INVALID_ABC'], # This value should cause a Pydantic validation error
            'coverage_days': [7]
        })
        file_path = os.path.join(self.excel_params_dir, 'rules_row_processing_error.xlsx') # Renamed file for clarity
        excel_content.to_excel(file_path, sheet_name='Feuil1', index=False)
        
        column_mappings = {'channel_id': 'channel_id', 'abc_class': 'abc_class', 'coverage_days': 'coverage_days'}
        
        # Expect an ERROR log for the faulty row, and an empty list of rules.
        with self.assertLogs(logger='backend.utils', level='ERROR') as cm:
            result_rules = load_optimization_rules(file_path, CoverageDaysRule, **column_mappings)
        
        self.assertEqual(result_rules, []) # Rule for this row should be skipped
        self.assertTrue(any("Error processing row" in log_record.getMessage() for log_record in cm.records), 
                        "Expected 'Error processing row' log not found.")
        # Check if the Pydantic validation error message (or part of it) is in the log
        self.assertTrue(any("Z_INVALID_ABC" in log_record.getMessage() and "literal_error" in log_record.getMessage().lower() 
                            for log_record in cm.records), 
                        "Error log should mention the problematic data 'Z_INVALID_ABC' and Pydantic literal error.")

    def test_load_optimization_rules_empty_file(self):
        file_path = os.path.join(self.excel_params_dir, 'rules_empty.xlsx')
        pd.DataFrame({ # Only headers
            'channel_id': pd.Series(dtype='str'), 
            'abc_class': pd.Series(dtype='str'), 
            'coverage_days': pd.Series(dtype='int')
        }).to_excel(file_path, sheet_name='Feuil1', index=False)
        
        column_mappings = {'channel_id': 'channel_id', 'abc_class': 'abc_class', 'coverage_days': 'coverage_days'}
        result_rules = load_optimization_rules(file_path, CoverageDaysRule, **column_mappings)
        self.assertEqual(result_rules, [])

    # --- Tests for load_sellin_ranking_dict ---
    def test_load_sellin_ranking_dict_success(self):
        csv_content = "ean_product;division;ranking\nEAN1;DivA;90\nEAN2;DivB;80\nEAN1;DivA;95" # EAN1 has duplicate, take max
        file_path = os.path.join(self.input_data_dir, 'sellin_ok.csv')
        with open(file_path, 'w') as f:
            f.write(csv_content)

        expected_ranking = {
            'EAN1': 95, # Max of 90, 95
            'EAN2': 80
        }
        result_ranking = load_sellin_ranking_dict(file_path)
        self.assertEqual(result_ranking, expected_ranking)
