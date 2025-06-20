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

        # sample_sellout_df is not used by the new ABC tests directly, but might be useful for other tests or context
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

        self.sample_inventory_df_data = { # This is for optimize_allocation, may need plant_code for new solver
            'product_ean': ['P1', 'P1', 'P2', 'P3', 'P4', 'P5_no_inv'], # P1 in two plants
            'plant': ['PlantA', 'PlantB', 'PlantA', 'PlantB', 'PlantA', 'PlantA'],
            'quantity': [60, 40, 80, 120, 50, 0], # StockToAllocate
            'available_stock': [70, 50, 90, 130, 60, 0] # AvailableStock
        }
        self.sample_inventory_df = pd.DataFrame(self.sample_inventory_df_data)


        self.sample_demand_dict = {
            ('P1', 'C1_store'): 50, ('P1', 'C2_store'): 30,
            ('P2', 'C1_store'): 40, ('P2', 'C4_outlet'): 60,
            ('P3', 'C2_store'): 70, ('P3', 'C3_outlet'): 20,
            ('P4', 'C4_outlet'): 30,
        }

        self.sample_existing_stock_dict = { # EAN-Channel level
            ('P1', 'C1_store'): 10, ('P2', 'C1_store'): 5,
        }
        
        # Sample in-store inventory for ABC tests (EAN-Channel level)
        self.sample_in_store_inventory_df_data = {
            'barcode': ['P1', 'P2', 'P3', 'P4'], 
            'store_code': ['C1_store', 'C1_store', 'C2_store', 'C3_outlet'], 
            'physical_quantity': [10, 0, 5, 2] 
        }
        self.sample_in_store_inventory_df = pd.DataFrame(self.sample_in_store_inventory_df_data)

        self.sample_sellin_ranking_dict = { # Sample sellin rankings for testing objective function
            'P1': 90, # High sellin for P1
            'P2': 20, # Low sellin for P2
            'P3': 70, # Medium sellin for P3
            'P4': 5,  # Very low sellin for P4
        }

    def test_basic(self):
        self.assertEqual(1, 1)

    # --- New ABC Classification Tests using ABC_ranking.csv ---

    @mock.patch('pandas.read_csv')
    def test_calculate_abc_from_ranking_file_basic_lookup(self, mock_read_csv_abc):
        abc_ranking_content = """barcode;store_code;abc_class
P1;C1_store;A
P2;C1_store;B
P3;C1_store;C"""
        mock_read_csv_abc.return_value = pd.read_csv(io.StringIO(abc_ranking_content), sep=';', dtype=str)
        empty_in_store_inv_df = pd.DataFrame(columns=['barcode', 'store_code', 'physical_quantity'])

        abc_map = solver.calculate_abc_classification_and_new_skus(
            product_master_df=self.sample_products_df,
            all_channel_ids=self.all_channel_ids_for_abc,
            in_store_inventory_df=empty_in_store_inv_df,
            abc_ranking_file_path='dummy_abc_ranking.csv'
        )
        
        self.assertEqual(abc_map.get(('P1', 'C1_store')), 'A')
        self.assertEqual(abc_map.get(('P2', 'C1_store')), 'B')
        self.assertEqual(abc_map.get(('P3', 'C1_store')), 'C')
        self.assertEqual(abc_map.get(('P4', 'C1_store')), 'NEW') 
        self.assertEqual(abc_map.get(('P1', 'C2_store')), 'NEW')

    @mock.patch('pandas.read_csv')
    def test_calculate_abc_from_ranking_file_new_sku_logic(self, mock_read_csv_abc):
        abc_ranking_content = "barcode;store_code;abc_class\nP1;C1_store;A"
        mock_read_csv_abc.return_value = pd.read_csv(io.StringIO(abc_ranking_content), sep=';', dtype=str)
        # P2-C1_store is not in self.sample_in_store_inventory_df, so no stock
        
        abc_map = solver.calculate_abc_classification_and_new_skus(
            product_master_df=self.sample_products_df,
            all_channel_ids=['C1_store'],
            in_store_inventory_df=self.sample_in_store_inventory_df, # P1-C1 has stock, P2-C1 has 0 stock
            abc_ranking_file_path='dummy_abc_ranking.csv'
        )
        self.assertEqual(abc_map.get(('P1', 'C1_store')), 'A') # From file
        # P2 is not in ranking file for C1_store. P2-C1_store has 0 stock in sample_in_store_inventory_df. So NEW.
        self.assertEqual(abc_map.get(('P2', 'C1_store')), 'NEW') 

    @mock.patch('pandas.read_csv')
    def test_calculate_abc_from_ranking_file_default_c_with_stock(self, mock_read_csv_abc):
        abc_ranking_content = "barcode;store_code;abc_class\nP1;C1_store;A"
        mock_read_csv_abc.return_value = pd.read_csv(io.StringIO(abc_ranking_content), sep=';', dtype=str)
        
        # P4 in C3_outlet has stock (from self.sample_in_store_inventory_df)
        # P4 is not in abc_ranking_content for C3_outlet
        abc_map = solver.calculate_abc_classification_and_new_skus(
            product_master_df=self.sample_products_df,
            all_channel_ids=['C3_outlet'],
            in_store_inventory_df=self.sample_in_store_inventory_df,
            abc_ranking_file_path='dummy_abc_ranking.csv'
        )
        self.assertEqual(abc_map.get(('P4', 'C3_outlet')), 'C') # Not in file, but has stock

    @mock.patch('pandas.read_csv')
    def test_calculate_abc_from_ranking_file_empty_ranking_file(self, mock_read_csv_abc):
        mock_read_csv_abc.return_value = pd.DataFrame(columns=['barcode', 'store_code', 'abc_class'])
        
        abc_map = solver.calculate_abc_classification_and_new_skus(
            product_master_df=self.sample_products_df,
            all_channel_ids=self.all_channel_ids_for_abc,
            in_store_inventory_df=self.sample_in_store_inventory_df, # Uses the setUp one
            abc_ranking_file_path='dummy_empty_abc_ranking.csv'
        )
        self.assertEqual(abc_map.get(('P1', 'C1_store')), 'C') # Has stock in sample_in_store_inventory_df
        self.assertEqual(abc_map.get(('P2', 'C1_store')), 'NEW') # 0 stock in sample_in_store_inventory_df
        self.assertEqual(abc_map.get(('P3', 'C2_store')), 'C') # Has stock in sample_in_store_inventory_df
        self.assertEqual(abc_map.get(('P4', 'C1_store')), 'NEW') # No stock for P4-C1_store

    @mock.patch('pandas.read_csv')
    def test_calculate_abc_from_ranking_file_non_standard_abc_class_defaults_to_c(self, mock_read_csv_abc):
        abc_ranking_content = "barcode;store_code;abc_class\nP1;C1_store;D" # D is non-standard
        mock_read_csv_abc.return_value = pd.read_csv(io.StringIO(abc_ranking_content), sep=';', dtype=str)
        empty_in_store_inv_df = pd.DataFrame(columns=['barcode', 'store_code', 'physical_quantity'])

        abc_map = solver.calculate_abc_classification_and_new_skus(
            product_master_df=self.sample_products_df,
            all_channel_ids=['C1_store'],
            in_store_inventory_df=empty_in_store_inv_df,
            abc_ranking_file_path='dummy_abc_ranking.csv'
        )
        self.assertEqual(abc_map.get(('P1', 'C1_store')), 'C') # Defaulted from 'D'

    @mock.patch('pandas.read_csv')
    def test_calculate_abc_from_ranking_file_ranking_file_not_found(self, mock_read_csv_abc):
        mock_read_csv_abc.side_effect = FileNotFoundError("File not found")
        
        abc_map = solver.calculate_abc_classification_and_new_skus(
            product_master_df=self.sample_products_df,
            all_channel_ids=['C1_store'],
            in_store_inventory_df=self.sample_in_store_inventory_df, # P1-C1 has stock
            abc_ranking_file_path='non_existent_abc_ranking.csv'
        )
        self.assertEqual(abc_map.get(('P1', 'C1_store')), 'C') 
        self.assertEqual(abc_map.get(('P2', 'C1_store')), 'NEW')

    # --- End of New ABC Classification Tests ---

    # --- Tests for load_product_data (example, assuming it's still in solver or utils) ---
    @mock.patch('backend.solver.pd.read_csv') # Or 'backend.utils.pd.read_csv' if moved
    def test_load_product_data_example(self, mock_read_csv):
        # This is just a placeholder structure if load_product_data is tested here
        pass

    # --- Tests for optimize_allocation ---
    # Note: These tests will now use a mocked ABC map for simplicity,
    # focusing on the optimization logic itself.

    def _get_mock_abc_map_for_opt(self, specific_new_skus=None):
        """ Helper to create a default ABC map for optimization tests. """
        mock_map = {}
        specific_new_skus = specific_new_skus or []
        for p_ean in self.sample_products_df.index:
            for c_id in self.sample_channels_df.index:
                if (p_ean, c_id) in specific_new_skus:
                    mock_map[(p_ean, c_id)] = 'NEW'
                else: # Default to 'C' if demand exists, else 'NEW'
                    has_demand = (p_ean, c_id) in self.sample_demand_dict and self.sample_demand_dict[(p_ean, c_id)] > 0
                    mock_map[(p_ean, c_id)] = 'C' if has_demand else 'NEW'
        return mock_map

    def test_optimize_allocation_success(self):
        mock_abc_map = self._get_mock_abc_map_for_opt()
        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, self.sample_inventory_df,
            self.sample_demand_dict, self.params, self.sample_existing_stock_dict, mock_abc_map,
            self.sample_sellin_ranking_dict # Pass sellin_ranking_dict
        )
        self.assertEqual(status, 'Optimal')
        self.assertTrue(len(results) > 0) # Should have some allocations
        # Verify structure of results, including plant_code
        for r in results:
            self.assertIn('product_sku', r)
            self.assertIn('plant_code', r)
            self.assertIn('channel_id', r)
            self.assertIn('quantity', r)
            self.assertIsInstance(r['quantity'], int)
            self.assertTrue(r['quantity'] >= 0)

    def test_optimize_allocation_zero_inventory(self):
        inventory_df_zero = self.sample_inventory_df.copy()
        inventory_df_zero['quantity'] = 0
        inventory_df_zero['available_stock'] = 0
        mock_abc_map = self._get_mock_abc_map_for_opt()

        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, inventory_df_zero,
            self.sample_demand_dict, self.params, self.sample_existing_stock_dict, mock_abc_map,
            self.sample_sellin_ranking_dict # Pass sellin_ranking_dict
        )
        self.assertEqual(status, 'Optimal')
        self.assertEqual(len(results), 0)

    def test_optimize_allocation_zero_demand_and_no_push(self):
        demand_dict_zero = {}
        # Ensure no 'NEW' SKUs that could be pushed by default rules (if any existed in self.params)
        mock_abc_map_all_c = { (p,c): 'C' for p in self.sample_products_df.index for c in self.sample_channels_df.index}
        
        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, self.sample_inventory_df,
            demand_dict_zero, self.params, self.sample_existing_stock_dict, mock_abc_map_all_c,
            self.sample_sellin_ranking_dict # Pass sellin_ranking_dict
        )
        self.assertEqual(status, 'Optimal')
        self.assertEqual(len(results), 0)

    def test_optimize_allocation_restricted_brands(self):
        params_restricted = self.params.copy(update={'restricted_brands_for_donation': ['BrandA']})
        mock_abc_map = self._get_mock_abc_map_for_opt()
        
        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, self.sample_inventory_df,
            self.sample_demand_dict, params_restricted, self.sample_existing_stock_dict, mock_abc_map,
            self.sample_sellin_ranking_dict # Pass sellin_ranking_dict
        )
        self.assertEqual(status, 'Optimal')
        for r in results:
            if r['channel_id'] == 'C5_donation': # C5_donation is a donation channel
                product_brand = self.sample_products_df.loc[r['product_sku'], 'brand']
                self.assertNotEqual(product_brand, 'BrandA')

    def test_optimize_allocation_coverage_days(self):
        params_coverage = self.params.copy(update={
            'coverage_days_rules': [CoverageDaysRule(channel_id='C1_store', abc_class='A', coverage_days=7)]
        })
        mock_abc_map = self._get_mock_abc_map_for_opt()
        mock_abc_map[('P1', 'C1_store')] = 'A' # Ensure P1 is 'A' in C1_store

        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, self.sample_inventory_df,
            self.sample_demand_dict, params_coverage, self.sample_existing_stock_dict, mock_abc_map,
            self.sample_sellin_ranking_dict # Pass sellin_ranking_dict
        )
        self.assertEqual(status, 'Optimal')
        for r in results:
            if r['product_sku'] == 'P1' and r['channel_id'] == 'C1_store':
                # Demand P1-C1_store = 50. Existing = 10. Max alloc = (50/7)*7 - 10 = 40.
                self.assertTrue(r['quantity'] <= 40)
    
    def test_optimize_allocation_push_new_sku(self):
        params_push = self.params.copy(update={
            'push_new_sku_rules': [PushNewSKURule(division='DivX', subaxis='Sub1', push_quantity=10)]
        })
        # P1 is in DivX, Sub1. Make it 'NEW' for C1_store.
        mock_abc_map = self._get_mock_abc_map_for_opt(specific_new_skus=[('P1', 'C1_store')])
        
        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, self.sample_inventory_df,
            self.sample_demand_dict, params_push, self.sample_existing_stock_dict, mock_abc_map,
            self.sample_sellin_ranking_dict # Pass sellin_ranking_dict
        )
        self.assertEqual(status, 'Optimal')
        p1_c1_allocation = 0
        for r in results:
            if r['product_sku'] == 'P1' and r['channel_id'] == 'C1_store':
                p1_c1_allocation = r['quantity']
                break
        self.assertTrue(p1_c1_allocation <= 10)

    def test_optimize_allocation_new_sku_prioritization_high_sellin(self):
        # P1 is NEW, high sellin (90). P2 is C, low demand (40).
        # P1 (DivX, Sub1), P2 (DivX, Sub2)
        mock_abc_map = {
            ('P1', 'C1_store'): 'NEW',
            ('P2', 'C1_store'): 'C',
            ('P3', 'C1_store'): 'A', # Ensure A/B are still high priority
        }
        # Ensure enough inventory for P1 and P2 to be allocated
        inventory_df_test = pd.DataFrame({
            'product_ean': ['P1', 'P2', 'P3'],
            'plant': ['PlantA', 'PlantA', 'PlantA'],
            'quantity': [100, 100, 100], # Ample stock
            'available_stock': [100, 100, 100]
        })
        demand_dict_test = {
            ('P1', 'C1_store'): 50, # Demand for P1
            ('P2', 'C1_store'): 10, # Low demand for P2
            ('P3', 'C1_store'): 100, # High demand for P3
        }
        sellin_ranking_dict_test = {
            'P1': 90, # High sellin
            'P2': 0,  # Not a NEW SKU, so sellin doesn't apply directly, but for completeness
            'P3': 0,
        }

        # Expected scores (approximate, based on solver.py constants):
        # A_B_CLASS_SCORE = 2.0
        # DEFAULT_ALLOCATION_SCORE = 1.0
        # SELLIN_RANKING_MAX_VALUE = 100
        # C_CLASS_DEMAND_SCALING_FACTOR = 0.001
        # NEW_SKU_RANKING_WEIGHT = 1.0
        # C_CLASS_DEMAND_WEIGHT = 0.5

        # P1 (NEW): 1.0 * (1.0 + (90/100)) = 1.9
        # P2 (C): 0.5 * (1.0 + (10 * 0.001)) = 0.5 * 1.01 = 0.505
        # P3 (A): 2.0

        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, inventory_df_test,
            demand_dict_test, self.params, self.sample_existing_stock_dict, mock_abc_map,
            sellin_ranking_dict_test
        )
        self.assertEqual(status, 'Optimal')
        
        # Extract allocations for P1, P2, P3 to C1_store
        alloc_p1_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P1' and r['channel_id'] == 'C1_store')
        alloc_p2_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P2' and r['channel_id'] == 'C1_store')
        alloc_p3_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P3' and r['channel_id'] == 'C1_store')

        # P3 (A class) should be prioritized highest
        self.assertTrue(alloc_p3_c1 > alloc_p1_c1)
        # P1 (NEW, high sellin) should be prioritized over P2 (C, low demand)
        self.assertTrue(alloc_p1_c1 > alloc_p2_c1)
        logger.debug(f"Test: High Sellin NEW SKU (P1) vs Low Demand C Class (P2) - P1 alloc: {alloc_p1_c1}, P2 alloc: {alloc_p2_c1}, P3 alloc: {alloc_p3_c1}")


    def test_optimize_allocation_c_class_high_demand_prioritization(self):
        # P1 is C, high demand (100). P2 is NEW, low sellin (20).
        mock_abc_map = {
            ('P1', 'C1_store'): 'C',
            ('P2', 'C1_store'): 'NEW',
            ('P3', 'C1_store'): 'B', # Ensure A/B are still high priority
        }
        inventory_df_test = pd.DataFrame({
            'product_ean': ['P1', 'P2', 'P3'],
            'plant': ['PlantA', 'PlantA', 'PlantA'],
            'quantity': [100, 100, 100], # Ample stock
            'available_stock': [100, 100, 100]
        })
        demand_dict_test = {
            ('P1', 'C1_store'): 100, # High demand for P1
            ('P2', 'C1_store'): 50,  # Demand for P2
            ('P3', 'C1_store'): 100, # High demand for P3
        }
        sellin_ranking_dict_test = {
            'P1': 0,
            'P2': 20, # Low sellin
            'P3': 0,
        }

        # Expected scores (approximate):
        # P1 (C): 0.5 * (1.0 + (100 * 0.001)) = 0.5 * 1.1 = 0.55
        # P2 (NEW): 1.0 * (1.0 + (20/100)) = 1.2
        # P3 (B): 2.0

        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, inventory_df_test,
            demand_dict_test, self.params, self.sample_existing_stock_dict, mock_abc_map,
            sellin_ranking_dict_test
        )
        self.assertEqual(status, 'Optimal')

        alloc_p1_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P1' and r['channel_id'] == 'C1_store')
        alloc_p2_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P2' and r['channel_id'] == 'C1_store')
        alloc_p3_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P3' and r['channel_id'] == 'C1_store')

        # P3 (B class) should be prioritized highest
        self.assertTrue(alloc_p3_c1 > alloc_p2_c1)
        # P2 (NEW, low sellin) should be prioritized over P1 (C, high demand)
        # This is where the weights matter. P2 (score 1.2) > P1 (score 0.55)
        self.assertTrue(alloc_p2_c1 > alloc_p1_c1)
        logger.debug(f"Test: Low Sellin NEW SKU (P2) vs High Demand C Class (P1) - P2 alloc: {alloc_p2_c1}, P1 alloc: {alloc_p1_c1}, P3 alloc: {alloc_p3_c1}")


    def test_optimize_allocation_new_sku_no_sellin_ranking(self):
        # P4 is NEW, but no sellin ranking provided (defaults to 0). P1 is C, medium demand.
        mock_abc_map = {
            ('P4', 'C1_store'): 'NEW',
            ('P1', 'C1_store'): 'C',
        }
        inventory_df_test = pd.DataFrame({
            'product_ean': ['P4', 'P1'],
            'plant': ['PlantA', 'PlantA'],
            'quantity': [100, 100], # Ample stock
            'available_stock': [100, 100]
        })
        demand_dict_test = {
            ('P4', 'C1_store'): 50, # Demand for P4
            ('P1', 'C1_store'): 50, # Demand for P1
        }
        sellin_ranking_dict_test = {
            'P1': 0, # Not a NEW SKU
            # P4 is missing from sellin_ranking_dict_test, so its rank will be 0
        }

        # Expected scores (approximate):
        # P4 (NEW, no sellin): 1.0 * (1.0 + (0/100)) = 1.0
        # P1 (C, demand 50): 0.5 * (1.0 + (50 * 0.001)) = 0.5 * 1.05 = 0.525

        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, inventory_df_test,
            demand_dict_test, self.params, self.sample_existing_stock_dict, mock_abc_map,
            sellin_ranking_dict_test
        )
        self.assertEqual(status, 'Optimal')

        alloc_p4_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P4' and r['channel_id'] == 'C1_store')
        alloc_p1_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P1' and r['channel_id'] == 'C1_store')

        # P4 (NEW, no sellin) should still be prioritized over P1 (C, medium demand) due to NEW_SKU_RANKING_WEIGHT
        self.assertTrue(alloc_p4_c1 > alloc_p1_c1)
        logger.debug(f"Test: NEW SKU (P4) with no sellin vs C Class (P1) - P4 alloc: {alloc_p4_c1}, P1 alloc: {alloc_p1_c1}")


    def test_optimize_allocation_a_b_class_prioritization(self):
        # P1 (A), P2 (B), P3 (NEW, high sellin), P4 (C, high demand)
        mock_abc_map = {
            ('P1', 'C1_store'): 'A',
            ('P2', 'C1_store'): 'B',
            ('P3', 'C1_store'): 'NEW',
            ('P4', 'C1_store'): 'C',
        }
        inventory_df_test = pd.DataFrame({
            'product_ean': ['P1', 'P2', 'P3', 'P4'],
            'plant': ['PlantA', 'PlantA', 'PlantA', 'PlantA'],
            'quantity': [100, 100, 100, 100], # Ample stock
            'available_stock': [100, 100, 100, 100]
        })
        demand_dict_test = {
            ('P1', 'C1_store'): 50,
            ('P2', 'C1_store'): 50,
            ('P3', 'C1_store'): 50,
            ('P4', 'C1_store'): 100, # High demand for P4 (C class)
        }
        sellin_ranking_dict_test = {
            'P3': 90, # High sellin for P3 (NEW)
        }

        # Expected scores (approximate):
        # P1 (A): 2.0
        # P2 (B): 2.0
        # P3 (NEW, sellin 90): 1.0 * (1.0 + (90/100)) = 1.9
        # P4 (C, demand 100): 0.5 * (1.0 + (100 * 0.001)) = 0.5 * 1.1 = 0.55

        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, inventory_df_test,
            demand_dict_test, self.params, self.sample_existing_stock_dict, mock_abc_map,
            sellin_ranking_dict_test
        )
        self.assertEqual(status, 'Optimal')

        alloc_p1_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P1' and r['channel_id'] == 'C1_store')
        alloc_p2_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P2' and r['channel_id'] == 'C1_store')
        alloc_p3_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P3' and r['channel_id'] == 'C1_store')
        alloc_p4_c1 = sum(r['quantity'] for r in results if r['product_sku'] == 'P4' and r['channel_id'] == 'C1_store')

        # A and B class should be highest priority
        self.assertTrue(alloc_p1_c1 > alloc_p3_c1)
        self.assertTrue(alloc_p2_c1 > alloc_p3_c1)
        # NEW (high sellin) should be higher than C (high demand)
        self.assertTrue(alloc_p3_c1 > alloc_p4_c1)
        logger.debug(f"Test: A/B Class Prioritization - P1(A) alloc: {alloc_p1_c1}, P2(B) alloc: {alloc_p2_c1}, P3(NEW) alloc: {alloc_p3_c1}, P4(C) alloc: {alloc_p4_c1}")

    def test_optimize_allocation_respects_available_stock_constraint(self):
        # Scenario: StockToAllocate is high, but AvailableStock is low.
        # Allocation should be limited by AvailableStock.
        inventory_df_limited_available = pd.DataFrame({
            'product_ean': ['P1', 'P2'],
            'plant': ['PlantA', 'PlantA'],
            'quantity': [100, 100], # StockToAllocate
            'available_stock': [10, 50] # AvailableStock - P1 is limited by this
        })
        demand_dict_high = {
            ('P1', 'C1_store'): 200, # High demand for P1
            ('P2', 'C1_store'): 200, # High demand for P2
        }
        mock_abc_map = {
            ('P1', 'C1_store'): 'A',
            ('P2', 'C1_store'): 'A',
        }
        sellin_ranking_dict_empty = {}

        model, status, results = solver.optimize_allocation(
            self.sample_products_df, self.sample_channels_df, inventory_df_limited_available,
            demand_dict_high, self.params, self.sample_existing_stock_dict, mock_abc_map,
            sellin_ranking_dict_empty
        )
        self.assertEqual(status, 'Optimal')

        # Check total allocation for P1 from PlantA
        total_alloc_p1_plantA = sum(r['quantity'] for r in results if r['product_sku'] == 'P1' and r['plant_code'] == 'PlantA')
        # Max allocatable for P1-PlantA is min(100, 10) = 10
        self.assertEqual(total_alloc_p1_plantA, 10)

        # Check total allocation for P2 from PlantA
        total_alloc_p2_plantA = sum(r['quantity'] for r in results if r['product_sku'] == 'P2' and r['plant_code'] == 'PlantA')
        # Max allocatable for P2-PlantA is min(100, 50) = 50
        self.assertEqual(total_alloc_p2_plantA, 50)
        logger.debug(f"Test: Available Stock Constraint - P1-PlantA alloc: {total_alloc_p1_plantA}, P2-PlantA alloc: {total_alloc_p2_plantA}")


if __name__ == '__main__':
    unittest.main()
