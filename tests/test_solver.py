import unittest
from unittest import mock
import pandas as pd
from pandas.testing import assert_frame_equal
import sys
import os
import io
import logging
from collections import defaultdict

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from backend import solver
from backend.schemas import (
    OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule,
    OutletAssortmentRule, PushNewSKURule
)

class TestSolver(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        logging.disable(logging.CRITICAL)

        cls.sample_products_df_data = {
            'ean_code': ['P1', 'P2', 'P3', 'P4', 'P5_no_inv'],
            'brand': ['BrandA', 'BrandA', 'BrandB', 'BrandC', 'BrandB'],
            'division': ['DivX', 'DivX', 'DivY', 'DivX', 'DivY'],
            'axe': ['Axe1', 'Axe2', 'Axe1', 'Axe2', 'Axe1'],
            'subaxis': ['Sub1', 'Sub2', 'Sub1', 'Sub1', 'Sub2'],
            'metier': ['MetA', 'MetB', 'MetA', 'MetB', 'MetA']
        }
        cls.sample_products_df = pd.DataFrame(cls.sample_products_df_data).set_index('ean_code')

        cls.sample_channels_df_data = {
            'id': ['C1_store', 'C2_store', 'C3_outlet', 'C4_outlet', 'C5_donation'],
            'channel_type': ['store', 'store', 'outlet', 'outlet', 'donation'],
            'capacity': [100, 150, 200, 50, 1000]
        }
        cls.sample_channels_df = pd.DataFrame(cls.sample_channels_df_data).set_index('id')

        cls.sample_sellout_df_data = {
            'barcode': ['P1', 'P1', 'P2', 'P3', 'P1', 'P4', 'P2'],
            'store_code': ['C1_store', 'C2_store', 'C1_store', 'C2_store', 'C1_store', 'C3_outlet', 'C4_outlet'],
            'total_items_weekly': [100, 50, 80, 60, 20, 10, 90]
        }
        cls.sample_sellout_df = pd.DataFrame(cls.sample_sellout_df_data)

        cls.all_channel_ids_for_abc = cls.sample_channels_df.index.tolist()

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def setUp(self):
        self.params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )

        self.sample_inventory_df_data = {
            'product_ean': ['P1', 'P2', 'P3', 'P4', 'P5_no_inv'],
            'quantity': [100, 80, 120, 50, 0]
        }
        self.sample_inventory_df = pd.DataFrame(self.sample_inventory_df_data)

        self.sample_demand_dict = {
            ('P1', 'C1_store'): 50, ('P1', 'C2_store'): 30,
            ('P2', 'C1_store'): 40, ('P2', 'C4_outlet'): 60,
            ('P3', 'C2_store'): 70, ('P3', 'C3_outlet'): 20,
            ('P4', 'C4_outlet'): 30,
        }

        self.sample_existing_stock_dict = {
            ('P1', 'C1_store'): 10, ('P2', 'C1_store'): 5,
        }

        self.sample_product_channel_abc_map = {}
        for p_ean in self.sample_products_df.index:
            for c_id in self.sample_channels_df.index:
                has_demand = (p_ean, c_id) in self.sample_demand_dict and self.sample_demand_dict[(p_ean, c_id)] > 0
                self.sample_product_channel_abc_map[(p_ean, c_id)] = 'C' if has_demand else 'NEW'

    def test_basic(self):
        self.assertEqual(1, 1)

    @mock.patch('pandas.read_csv')
    def test_load_product_data_success(self, mock_read_csv):
        csv_content = "ean_code,Brand,Division,Axe,SubAxis,Metier\nP1,BrandA,DivX,Axe1,Sub1,MetA\nP2,BrandB,DivY,Axe2,Sub2,MetB"
        mock_read_csv.return_value = pd.read_csv(io.StringIO(csv_content))

        expected_df = pd.DataFrame({
            'brand': ['BrandA', 'BrandB'], 'division': ['DivX', 'DivY'],
            'axe': ['Axe1', 'Axe2'], 'subaxis': ['Sub1', 'Sub2'], 'metier': ['MetA', 'MetB']
        }, index=pd.Index(['P1', 'P2'], name='ean_code'))
        for col in expected_df.columns:
            expected_df[col] = expected_df[col].astype(str)

        df = solver.load_product_data('dummy.csv', ean_c='ean_code', brand_c='Brand', div_c='Division', axe_c='Axe', sub_c='SubAxis', met_c='Metier')
        df_dict = df.to_dict('index')
        expected_df_dict = expected_df.to_dict('index')
        self.assertEqual(df_dict, expected_df_dict)

    @mock.patch('pandas.read_csv')
    def test_load_product_data_file_not_found(self, mock_read_csv):
        mock_read_csv.side_effect = FileNotFoundError("File not found")
        with self.assertRaises(FileNotFoundError):
            solver.load_product_data('dummy.csv')

    @mock.patch('pandas.read_csv')
    def test_load_product_data_incorrect_columns(self, mock_read_csv):
        csv_content = "Brand,Division,Axe,SubAxis,Metier\nBrandA,DivX,Axe1,Sub1,MetA\nBrandB,DivY,Axe2,Sub2,MetB"
        mock_read_csv.return_value = pd.read_csv(io.StringIO(csv_content))
        with self.assertRaises(ValueError):
            solver.load_product_data('dummy.csv')

    @mock.patch('pandas.read_csv')
    def test_load_product_data_duplicate_eans(self, mock_read_csv):
        csv_content = "ean_code,Brand,Division,Axe,SubAxis,Metier\nP1,BrandA,DivX,Axe1,Sub1,MetA\nP1,BrandB,DivY,Axe2,Sub2,MetB"
        mock_read_csv.return_value = pd.read_csv(io.StringIO(csv_content))

        expected_df = pd.DataFrame({
            'brand': ['BrandA'], 'division': ['DivX'],
            'axe': ['Axe1'], 'subaxis': ['Sub1'], 'metier': ['MetA']
        }, index=pd.Index(['P1'], name='ean_code'))
        for col in expected_df.columns:
            expected_df[col] = expected_df[col].astype(str)

        df = solver.load_product_data('dummy.csv', ean_c='ean_code', brand_c='Brand', div_c='Division', axe_c='Axe', sub_c='SubAxis', met_c='Metier')
        df_dict = df.to_dict('index')
        expected_df_dict = expected_df.to_dict('index')
        self.assertEqual(df_dict, expected_df_dict)

    @mock.patch('pandas.read_excel')
    def test_load_channel_data_success(self, mock_read_excel):
        excel_content = "channel_type;channel_id\nstore;C1_store\noutlet;C3_outlet"
        mock_read_excel.return_value = pd.DataFrame({
            'channel_type': ['store', 'outlet'],
            'capacity': ['0', '0']
        }, index=pd.Index(['C1_store', 'C3_outlet'], name='id'))

        df = solver.load_channel_data_from_channellist('dummy.xlsx', channel_id_col='channel_id', channel_type_col='channel_type', delimiter=';')
        df_dict = df.to_dict('index')
        expected_df_dict = mock_read_excel.return_value.to_dict('index')
        self.assertEqual(df_dict, expected_df_dict)

    @mock.patch('pandas.read_excel')
    def test_load_channel_data_file_not_found(self, mock_read_excel):
        mock_read_excel.side_effect = FileNotFoundError("File not found")
        with self.assertRaises(FileNotFoundError):
            solver.load_channel_data_from_channellist('dummy.xlsx')

    @mock.patch('pandas.read_excel')
    def test_load_channel_data_sheet_not_found(self, mock_read_excel):
        mock_read_excel.side_effect = ValueError("Sheet not found")
        df = solver.load_channel_data_from_channellist('dummy.xlsx', sheet_name='Sheet2')
        self.assertTrue(df.empty)

    @mock.patch('pandas.read_excel')
    def test_load_channel_data_delimited_headers(self, mock_read_excel):
        excel_content = "channel_type;channel_id\nstore;C1_store\noutlet;C3_outlet"
        mock_read_excel.return_value = pd.DataFrame({
            'channel_type': ['store', 'outlet'],
            'capacity': ['0', '0']
        }, index=pd.Index(['C1_store', 'C3_outlet'], name='id'))

        df = solver.load_channel_data_from_channellist('dummy.xlsx', channel_id_col='channel_id', channel_type_col='channel_type', delimiter=';')
        df_dict = df.to_dict('index')
        expected_df_dict = mock_read_excel.return_value.to_dict('index')
        self.assertEqual(df_dict, expected_df_dict)

    @mock.patch('pandas.read_excel')
    def test_load_channel_data_missing_columns(self, mock_read_excel):
        excel_content = "channel_id\nC1_store\nC3_outlet"
        mock_read_excel.return_value = pd.read_csv(io.StringIO(excel_content))
        with self.assertRaises(ValueError):
            solver.load_channel_data_from_channellist('dummy.xlsx')

    @mock.patch('pandas.read_csv')
    def test_load_inventory_data_success(self, mock_read_csv):
        csv_content = "ean_code,StockToAllocate\nP1,100\nP2,80"
        mock_read_csv.return_value = pd.read_csv(io.StringIO(csv_content))

        expected_df = pd.DataFrame({
            'product_ean': ['P1', 'P2'],
            'quantity': [100, 80]
        })

        df = solver.load_inventory_data('dummy.csv')
        assert_frame_equal(df, expected_df)

    @mock.patch('pandas.read_csv')
    def test_load_inventory_data_file_not_found(self, mock_read_csv):
        mock_read_csv.side_effect = FileNotFoundError("File not found")
        with self.assertRaises(FileNotFoundError):
            solver.load_inventory_data('dummy.csv')

    @mock.patch('pandas.read_csv')
    def test_load_inventory_data_missing_columns(self, mock_read_csv):
        csv_content = "ean_code\nP1\nP2"
        mock_read_csv.return_value = pd.read_csv(io.StringIO(csv_content))
        with self.assertRaises(ValueError):
            solver.load_inventory_data('dummy.csv')

    @mock.patch('pandas.read_csv')
    def test_load_existing_stock_data_success(self, mock_read_csv):
        instore_content = "barcode,store_code,physical_quantity\nP1,C1_store,10\nP2,C1_store,5"
        intransit_content = "ean_material_code,store_code,order_quantity\nP1,C2_store,20\nP3,C2_store,15"
        mock_read_csv.side_effect = [pd.read_csv(io.StringIO(instore_content)), pd.read_csv(io.StringIO(intransit_content))]

        expected_stock = {('P1', 'C1_store'): 10.0, ('P2', 'C1_store'): 5.0, ('P1', 'C2_store'): 20.0, ('P3', 'C2_store'): 15.0}
        stock = solver.load_existing_stock_data('instore.csv', 'intransit.csv')
        self.assertEqual(stock, expected_stock)

    @mock.patch('pandas.read_csv')
    def test_load_existing_stock_data_file_not_found(self, mock_read_csv):
        mock_read_csv.side_effect = FileNotFoundError("File not found")
        with self.assertRaises(FileNotFoundError):
            solver.load_existing_stock_data('instore.csv', 'intransit.csv')

    @mock.patch('pandas.read_csv')
    def test_load_existing_stock_data_missing_columns(self, mock_read_csv):
        instore_content = "barcode,store_code\nP1,C1_store\nP2,C1_store"
        intransit_content = "ean_material_code,store_code,order_quantity\nP1,C2_store,20\nP3,C2_store,15"
        mock_read_csv.side_effect = [pd.read_csv(io.StringIO(instore_content)), pd.read_csv(io.StringIO(intransit_content))]
        with self.assertRaises(ValueError):
            solver.load_existing_stock_data('instore.csv', 'intransit.csv')

    @mock.patch('pandas.read_csv')
    def test_load_demand_data_success(self, mock_read_csv):
        csv_content = "EAN,ChannelID,WeeklySalesQty\nP1,C1_store,50\nP2,C1_store,40"
        mock_read_csv.return_value = pd.read_csv(io.StringIO(csv_content))

        expected_demand = {('P1', 'C1_store'): 50.0, ('P2', 'C1_store'): 40.0}
        demand = solver.load_demand_data('dummy.csv')
        self.assertEqual(demand, expected_demand)

    @mock.patch('pandas.read_csv')
    def test_load_demand_data_file_not_found(self, mock_read_csv):
        mock_read_csv.side_effect = FileNotFoundError("File not found")
        with self.assertRaises(FileNotFoundError):
            solver.load_demand_data('dummy.csv')

    @mock.patch('pandas.read_csv')
    def test_load_demand_data_missing_columns(self, mock_read_csv):
        csv_content = "EAN,ChannelID\nP1,C1_store\nP2,C1_store"
        mock_read_csv.return_value = pd.read_csv(io.StringIO(csv_content))
        with self.assertRaises(ValueError):
            solver.load_demand_data('dummy.csv')

    @mock.patch('pandas.read_excel')
    def test_load_coverage_rules_success(self, mock_read_excel):
        excel_content = "Channel,ABC Class,Coverage (in days)\nC1_store,A,7\nC2_store,B,14"
        mock_read_excel.return_value = pd.DataFrame({
            'Channel': ['C1_store', 'C2_store'],
            'ABC Class': ['A', 'B'],
            'Coverage (in days)': [7, 14]
        })

        expected_rules = [
            CoverageDaysRule(channel_id='C1_store', abc_class='A', coverage_days=7),
            CoverageDaysRule(channel_id='C2_store', abc_class='B', coverage_days=14)
        ]
        rules = solver.load_coverage_rules_from_excel('dummy.xlsx')
        self.assertEqual([r.__dict__ for r in rules], [r.__dict__ for r in expected_rules])

    @mock.patch('pandas.read_excel')
    def test_load_coverage_rules_file_not_found(self, mock_read_excel):
        mock_read_excel.side_effect = FileNotFoundError("File not found")
        with self.assertRaises(FileNotFoundError):
            solver.load_coverage_rules_from_excel('dummy.xlsx')

    @mock.patch('pandas.read_excel')
    def test_load_coverage_rules_sheet_not_found(self, mock_read_excel):
        mock_read_excel.side_effect = ValueError("Sheet not found")
        rules = solver.load_coverage_rules_from_excel('dummy.xlsx', sheet='Sheet2')
        self.assertEqual(rules, [])

    @mock.patch('pandas.read_excel')
    def test_load_coverage_rules_missing_columns(self, mock_read_excel):
        excel_content = "Channel,ABC Class\nC1_store,A\nC2_store,B"
        mock_read_excel.return_value = pd.read_csv(io.StringIO(excel_content))
        with self.assertRaises(ValueError):
            solver.load_coverage_rules_from_excel('dummy.xlsx')

    @mock.patch('pandas.read_excel')
    def test_load_coverage_rules_invalid_data(self, mock_read_excel):
        excel_content = "Channel,ABC Class,Coverage (in days)\nC1_store,A,invalid\nC2_store,B,14"
        mock_read_excel.return_value = pd.DataFrame({
            'Channel': ['C1_store', 'C2_store'],
            'ABC Class': ['A', 'B'],
            'Coverage (in days)': ['invalid', 14]
        })

        expected_rules = [
            CoverageDaysRule(channel_id='C2_store', abc_class='B', coverage_days=14)
        ]
        rules = solver.load_coverage_rules_from_excel('dummy.xlsx')
        self.assertEqual([r.__dict__ for r in rules if isinstance(r, CoverageDaysRule)], [r.__dict__ for r in expected_rules])

    @mock.patch('pandas.read_excel')
    def test_load_outlet_sku_capacity_rules_success(self, mock_read_excel):
        excel_content = "Channel,operational_division,operational_axe_label,Max capacity (in # of SKU)\nC1_store,DivX,Axe1,10\nC2_store,DivY,Axe2,20"
        mock_read_excel.return_value = pd.DataFrame({
            'Channel': ['C1_store', 'C2_store'],
            'operational_division': ['DivX', 'DivY'],
            'operational_axe_label': ['Axe1', 'Axe2'],
            'Max capacity (in # of SKU)': [10, 20]
        })

        expected_rules = [
            OutletSKUCapacityRule(channel_id='C1_store', division='DivX', axe='Axe1', max_skus=10),
            OutletSKUCapacityRule(channel_id='C2_store', division='DivY', axe='Axe2', max_skus=20)
        ]
        rules = solver.load_outlet_sku_capacity_rules_from_excel('dummy.xlsx')
        self.assertEqual([r.__dict__ for r in rules], [r.__dict__ for r in expected_rules])

    @mock.patch('pandas.read_excel')
    def test_load_outlet_sku_capacity_rules_file_not_found(self, mock_read_excel):
        mock_read_excel.side_effect = FileNotFoundError("File not found")
        with self.assertRaises(FileNotFoundError):
            solver.load_outlet_sku_capacity_rules_from_excel('dummy.xlsx')

    @mock.patch('pandas.read_excel')
    def test_load_outlet_sku_capacity_rules_sheet_not_found(self, mock_read_excel):
        mock_read_excel.side_effect = ValueError("Sheet not found")
        rules = solver.load_outlet_sku_capacity_rules_from_excel('dummy.xlsx', sheet='Sheet2')
        self.assertEqual(rules, [])

    @mock.patch('pandas.read_excel')
    def test_load_outlet_sku_capacity_rules_missing_columns(self, mock_read_excel):
        excel_content = "Channel,operational_division,operational_axe_label\nC1_store,DivX,Axe1\nC2_store,DivY,Axe2"
        mock_read_excel.return_value = pd.read_csv(io.StringIO(excel_content))
        rules = solver.load_outlet_sku_capacity_rules_from_excel('dummy.xlsx')
        self.assertEqual(rules, [])

    @mock.patch('pandas.read_excel')
    def test_load_outlet_assortment_rules_success(self, mock_read_excel):
        excel_content = "operational_metier_label,operational_sub_axe_label,operational_signature_label,# of SKUs to have in outlet (assortment)\nMetA,Sub1,BrandA,5\nMetB,Sub2,BrandB,10"
        mock_read_excel.return_value = pd.DataFrame({
            'operational_metier_label': ['MetA', 'MetB'],
            'operational_sub_axe_label': ['Sub1', 'Sub2'],
            'operational_signature_label': ['BrandA', 'BrandB'],
            '# of SKUs to have in outlet (assortment)': [5, 10]
        })

        expected_rules = [
            OutletAssortmentRule(metier='MetA', subaxis='Sub1', brand='BrandA', max_skus=5),
            OutletAssortmentRule(metier='MetB', subaxis='Sub2', brand='BrandB', max_skus=10)
        ]
        rules = solver.load_outlet_assortment_rules_from_excel('dummy.xlsx')
        self.assertEqual([r.__dict__ for r in rules], [r.__dict__ for r in expected_rules])

    @mock.patch('pandas.read_excel')
    def test_load_outlet_assortment_rules_file_not_found(self, mock_read_excel):
        mock_read_excel.side_effect = FileNotFoundError("File not found")
        with self.assertRaises(FileNotFoundError):
            solver.load_outlet_assortment_rules_from_excel('dummy.xlsx')

    @mock.patch('pandas.read_excel')
    def test_load_outlet_assortment_rules_sheet_not_found(self, mock_read_excel):
        mock_read_excel.side_effect = ValueError("Sheet not found")
        rules = solver.load_outlet_assortment_rules_from_excel('dummy.xlsx', sheet='Sheet2')
        self.assertEqual(rules, [])

    @mock.patch('pandas.read_excel')
    def test_load_outlet_assortment_rules_missing_columns(self, mock_read_excel):
        excel_content = "operational_metier_label,operational_sub_axe_label,operational_signature_label\nMetA,Sub1,BrandA\nMetB,Sub2,BrandB"
        mock_read_excel.return_value = pd.read_csv(io.StringIO(excel_content))
        with self.assertRaises(ValueError):
            solver.load_outlet_assortment_rules_from_excel('dummy.xlsx')

    @mock.patch('pandas.read_excel')
    def test_load_push_new_sku_rules_success(self, mock_read_excel):
        excel_content = "operational_division,operational_sub_axe_label,Push Quantity if New SKU\nDivX,Sub1,50\nDivY,Sub2,100"
        mock_read_excel.return_value = pd.DataFrame({
            'operational_division': ['DivX', 'DivY'],
            'operational_sub_axe_label': ['Sub1', 'Sub2'],
            'Push Quantity if New SKU': [50, 100]
        })

        expected_rules = [
            PushNewSKURule(division='DivX', subaxis='Sub1', push_quantity=50),
            PushNewSKURule(division='DivY', subaxis='Sub2', push_quantity=100)
        ]
        rules = solver.load_push_new_sku_rules_from_excel('dummy.xlsx')
        self.assertEqual([r.__dict__ for r in rules], [r.__dict__ for r in expected_rules])

    @mock.patch('pandas.read_excel')
    def test_load_push_new_sku_rules_file_not_found(self, mock_read_excel):
        mock_read_excel.side_effect = FileNotFoundError("File not found")
        with self.assertRaises(FileNotFoundError):
            solver.load_push_new_sku_rules_from_excel('dummy.xlsx')

    @mock.patch('pandas.read_excel')
    def test_load_push_new_sku_rules_sheet_not_found(self, mock_read_excel):
        mock_read_excel.side_effect = ValueError("Sheet not found")
        rules = solver.load_push_new_sku_rules_from_excel('dummy.xlsx', sheet='Sheet2')
        self.assertEqual(rules, [])

    @mock.patch('pandas.read_excel')
    def test_load_push_new_sku_rules_missing_columns(self, mock_read_excel):
        excel_content = "operational_division,operational_sub_axe_label\nDivX,Sub1\nDivY,Sub2"
        mock_read_excel.return_value = pd.read_csv(io.StringIO(excel_content))
        with self.assertRaises(ValueError):
            solver.load_push_new_sku_rules_from_excel('dummy.xlsx')

    def test_calculate_abc_classification_and_new_skus_success(self):
        abc_map = solver.calculate_abc_classification_and_new_skus(
            self.sample_sellout_df,
            self.sample_products_df,
            self.all_channel_ids_for_abc,
            sellout_ean_col='barcode',
            sellout_channel_col='store_code',
            sellout_qty_col='total_items_weekly'
        )

        expected_abc_map = {
            ('P1', 'C1_store'): 'A', ('P1', 'C2_store'): 'B', ('P1', 'C3_outlet'): 'NEW', ('P1', 'C4_outlet'): 'NEW', ('P1', 'C5_donation'): 'NEW',
            ('P2', 'C1_store'): 'B', ('P2', 'C2_store'): 'NEW', ('P2', 'C3_outlet'): 'NEW', ('P2', 'C4_outlet'): 'C', ('P2', 'C5_donation'): 'NEW',
            ('P3', 'C1_store'): 'NEW', ('P3', 'C2_store'): 'C', ('P3', 'C3_outlet'): 'NEW', ('P3', 'C4_outlet'): 'NEW', ('P3', 'C5_donation'): 'NEW',
            ('P4', 'C1_store'): 'NEW', ('P4', 'C2_store'): 'NEW', ('P4', 'C3_outlet'): 'NEW', ('P4', 'C4_outlet'): 'C', ('P4', 'C5_donation'): 'NEW',
            ('P5_no_inv', 'C1_store'): 'NEW', ('P5_no_inv', 'C2_store'): 'NEW', ('P5_no_inv', 'C3_outlet'): 'NEW', ('P5_no_inv', 'C4_outlet'): 'NEW', ('P5_no_inv', 'C5_donation'): 'NEW',
        }
        self.assertEqual(abc_map, expected_abc_map)

    def test_calculate_abc_classification_and_new_skus_no_sales_for_channel(self):
        sellout_df = self.sample_sellout_df.copy()
        sellout_df = sellout_df[sellout_df['store_code'] != 'C1_store']

        abc_map = solver.calculate_abc_classification_and_new_skus(
            sellout_df,
            self.sample_products_df,
            self.all_channel_ids_for_abc,
            sellout_ean_col='barcode',
            sellout_channel_col='store_code',
            sellout_qty_col='total_items_weekly'
        )

        self.assertEqual(abc_map[('P1', 'C1_store')], 'NEW')
        self.assertEqual(abc_map[('P2', 'C1_store')], 'NEW')
        self.assertEqual(abc_map[('P3', 'C1_store')], 'NEW')
        self.assertEqual(abc_map[('P4', 'C1_store')], 'NEW')
        self.assertEqual(abc_map[('P5_no_inv', 'C1_store')], 'NEW')

    def test_calculate_abc_classification_and_new_skus_zero_total_sales(self):
        sellout_df = self.sample_sellout_df.copy()
        sellout_df['total_items_weekly'] = 0

        abc_map = solver.calculate_abc_classification_and_new_skus(
            sellout_df,
            self.sample_products_df,
            self.all_channel_ids_for_abc,
            sellout_ean_col='barcode',
            sellout_channel_col='store_code',
            sellout_qty_col='total_items_weekly'
        )

        for channel in self.sample_channels_df.index:
            for product in self.sample_products_df.index:
                if (product, channel) in abc_map:
                    if product in self.sample_sellout_df['barcode'].unique():
                        self.assertEqual(abc_map[(product, channel)], 'C')
                    else:
                        self.assertEqual(abc_map[(product, channel)], 'NEW')

    def test_optimize_allocation_success(self):
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            self.sample_demand_dict,
            self.params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )

        self.assertEqual(status, 'Optimal')
        self.assertTrue(len(results) > 0)

    def test_optimize_allocation_zero_inventory(self):
        inventory_df = self.sample_inventory_df.copy()
        inventory_df['quantity'] = 0
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            inventory_df,
            self.sample_demand_dict,
            self.params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )
        self.assertEqual(status, 'Optimal')
        self.assertEqual(len(results), 0)

    def test_optimize_allocation_zero_demand(self):
        demand_dict = {}
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            demand_dict,
            self.params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )
        self.assertEqual(status, 'Optimal')
        self.assertEqual(len(results), 0)

    def test_optimize_allocation_restricted_brands(self):
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=['BrandA'],
            coverage_days_rules=[],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            self.sample_demand_dict,
            params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )
        self.assertEqual(status, 'Optimal')
        for r in results:
            if r['channel_id'] == 'C5_donation':
                self.assertNotEqual(self.sample_products_df.loc[r['product_sku'], 'brand'], 'BrandA')

    def test_optimize_allocation_coverage_days(self):
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[CoverageDaysRule(channel_id='C1_store', abc_class='A', coverage_days=7)],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            self.sample_demand_dict,
            params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )
        self.assertEqual(status, 'Optimal')
        for r in results:
            if r['channel_id'] == 'C1_store' and self.sample_product_channel_abc_map[(r['product_sku'], r['channel_id'])] == 'A':
                self.assertTrue(r['quantity'] <= (self.sample_demand_dict[(r['product_sku'], r['channel_id'])] / 7) * 7)

    def test_optimize_allocation_outlet_sku_capacity(self):
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[],
            outlet_sku_capacity_rules=[OutletSKUCapacityRule(channel_id='C3_outlet', division='DivX', axe='Axe1', max_skus=1)],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            self.sample_demand_dict,
            params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )
        self.assertEqual(status, 'Optimal')
        count = 0
        for r in results:
            if r['channel_id'] == 'C3_outlet' and self.sample_products_df.loc[r['product_sku'], 'division'] == 'DivX' and self.sample_products_df.loc[r['product_sku'], 'axe'] == 'Axe1':
                count += 1
        self.assertTrue(count <= 1)

    def test_optimize_allocation_outlet_assortment(self):
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[OutletAssortmentRule(metier='MetA', subaxis='Sub1', brand='BrandA', max_skus=1)],
            push_new_sku_rules=[]
        )
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            self.sample_demand_dict,
            params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )
        self.assertEqual(status, 'Optimal')
        count = 0
        for r in results:
            if r['channel_id'] == 'C3_outlet' and self.sample_products_df.loc[r['product_sku'], 'metier'] == 'MetA' and self.sample_products_df.loc[r['product_sku'], 'subaxis'] == 'Sub1' and self.sample_products_df.loc[r['product_sku'], 'brand'] == 'BrandA':
                count += 1
        self.assertTrue(count <= 1)

    def test_optimize_allocation_push_new_sku(self):
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[PushNewSKURule(division='DivX', subaxis='Sub1', push_quantity=10)]
        )
        
        # Ensure P1 is a new SKU in C1_store
        product_channel_abc_map = self.sample_product_channel_abc_map.copy()
        product_channel_abc_map[('P1', 'C1_store')] = 'NEW'
        
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            self.sample_demand_dict,
            params,
            self.sample_existing_stock_dict,
            product_channel_abc_map
        )
        self.assertEqual(status, 'Optimal')
        for r in results:
            if r['product_sku'] == 'P1' and r['channel_id'] == 'C1_store':
                self.assertTrue(r['quantity'] <= 10)

    def test_optimize_allocation_supply_constraint(self):
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            self.sample_demand_dict,
            self.params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )
        self.assertEqual(status, 'Optimal')
        
        total_allocated = defaultdict(int)
        for r in results:
            total_allocated[r['product_sku']] += r['quantity']
        
        for product in self.sample_products_df.index:
            self.assertTrue(total_allocated[product] <= self.sample_inventory_df[self.sample_inventory_df['product_ean'] == product]['quantity'].sum())

    def test_optimize_allocation_existing_stock(self):
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            self.sample_demand_dict,
            self.params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )
        self.assertEqual(status, 'Optimal')
        for r in results:
            if r['product_sku'] == 'P1' and r['channel_id'] == 'C1_store':
                self.assertTrue(r['quantity'] <= self.sample_demand_dict[(r['product_sku'], r['channel_id'])] - self.sample_existing_stock_dict[(r['product_sku'], r['channel_id'])])

    def test_optimize_allocation_infeasible(self):
        # Set demand higher than inventory for all products
        demand_dict = {k: 1000 for k in self.sample_demand_dict}
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            demand_dict,
            self.params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )
        self.assertNotEqual(status, 'Optimal')

    def test_optimize_allocation_linking_x_y(self):
        model, status, results = solver.optimize_allocation(
            self.sample_products_df,
            self.sample_channels_df,
            self.sample_inventory_df,
            self.sample_demand_dict,
            self.params,
            self.sample_existing_stock_dict,
            self.sample_product_channel_abc_map
        )
        self.assertEqual(status, 'Optimal')
        
        for p in self.sample_products_df.index:
            for c in self.sample_channels_df.index:
                x_var = model.variablesDict().get(f"allocation_qty_('{p}', '{c}')")
                y_var = model.variablesDict().get(f"is_allocated_('{p}', '{c}')")
                if x_var is not None and y_var is not None:
                    if x_var.varValue > 0:
                        self.assertEqual(y_var.varValue, 1.0)
                    else:
                        self.assertEqual(y_var.varValue, 0.0)

if __name__ == '__main__':
    unittest.main()
