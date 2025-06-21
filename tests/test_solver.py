import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import io
import sys
import os
import pulp

# Add the parent directory to the Python path so we can import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.solver import (
    calculate_abc_classification_and_new_skus,
    optimize_allocation,
)
from backend.schemas import (
    OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule,
    OutletAssortmentRule, PushNewSKURule
)

class TestSolver(unittest.TestCase):

    def setUp(self):
        # Sample data for testing
        self.products_df = pd.DataFrame({
            'ean_code': ['P1', 'P2', 'P3', 'P4', 'P5'],
            'brand': ['BrandA', 'BrandA', 'BrandB', 'BrandC', 'BrandB'],
            'division': ['DivX', 'DivX', 'DivY', 'DivX', 'DivY'],
            'axe': ['Axe1', 'Axe2', 'Axe1', 'Axe2', 'Axe1'],
            'subaxis': ['Sub1', 'Sub2', 'Sub1', 'Sub1', 'Sub2'],
            'metier': ['MetA', 'MetB', 'MetA', 'MetB', 'MetA']
        }).set_index('ean_code')

        self.channels_df = pd.DataFrame({
            'id': ['C1_store', 'C2_store', 'C3_outlet', 'C4_outlet'],
            'channel_type': ['store', 'store', 'outlet', 'outlet'],
            'capacity': [100, 150, 200, 50]
        }).set_index('id')

        self.inventory_df = pd.DataFrame({
            'product_ean': ['P1', 'P1', 'P2', 'P3', 'P4', 'P5'],
            'plant': ['PlantA', 'PlantB', 'PlantA', 'PlantB', 'PlantA', 'PlantA'],
            'quantity': [60, 40, 80, 120, 50, 0],
            'available_stock': [70, 50, 90, 130, 60, 0]
        })

        self.demand_dict = {
            ('P1', 'C1_store'): 50, ('P1', 'C2_store'): 30,
            ('P2', 'C1_store'): 40, ('P2', 'C4_outlet'): 60,
            ('P3', 'C2_store'): 70, ('P3', 'C3_outlet'): 20,
            ('P4', 'C4_outlet'): 30,
        }

        self.existing_stock_dict = {
            ('P1', 'C1_store'): 10, ('P2', 'C1_store'): 5,
        }

        self.abc_ranking_content = """barcode;store_code;abc_class
P1;C1_store;A
P2;C1_store;B
P3;C2_store;C"""
        self.abc_ranking_df = pd.read_csv(io.StringIO(self.abc_ranking_content), sep=';')

        self.sellin_ranking_dict = {
            'P1': 90,
            'P2': 20,
            'P3': 70,
            'P4': 5,
        }

        self.params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )

    @patch('backend.solver.pd.read_csv')
    def test_calculate_abc_classification_and_new_skus(self, mock_read_csv):
        mock_read_csv.return_value = self.abc_ranking_df
        
        in_store_inventory_df = pd.DataFrame({
            'barcode': ['P1', 'P3'],
            'store_code': ['C1_store', 'C2_store'],
            'physical_quantity': [10, 5]
        })
        
        abc_map = calculate_abc_classification_and_new_skus(
            product_master_df=self.products_df,
            all_channel_ids=self.channels_df.index.tolist(),
            in_store_inventory_df=in_store_inventory_df,
            abc_ranking_file_path='dummy_abc_ranking.csv'
        )
        
        self.assertEqual(abc_map.get(('P1', 'C1_store')), 'A')
        self.assertEqual(abc_map.get(('P2', 'C1_store')), 'B')
        self.assertEqual(abc_map.get(('P3', 'C2_store')), 'C')
        self.assertEqual(abc_map.get(('P4', 'C1_store')), 'NEW')
        self.assertEqual(abc_map.get(('P3', 'C1_store')), 'NEW')

    def test_optimize_allocation_basic(self):
        abc_map = {
            ('P1', 'C1_store'): 'A', ('P1', 'C2_store'): 'A',
            ('P2', 'C1_store'): 'B', ('P2', 'C4_outlet'): 'B',
            ('P3', 'C2_store'): 'C', ('P3', 'C3_outlet'): 'C',
            ('P4', 'C4_outlet'): 'C',
        }

        model, status, results = optimize_allocation(
            self.products_df,
            self.channels_df,
            self.inventory_df,
            self.demand_dict,
            self.params,
            self.existing_stock_dict,
            abc_map,
            self.sellin_ranking_dict
        )

        self.assertIsInstance(model, pulp.LpProblem)
        self.assertEqual(status, 'Optimal')
        self.assertIsInstance(results, list)
        
        # Check that the results are in the correct format
        for item in results:
            self.assertIn('product_sku', item)
            self.assertIn('plant_code', item)
            self.assertIn('channel_id', item)
            self.assertIn('quantity', item)

    def test_optimize_allocation_with_rules(self):
        # Test with some rules to see if they are applied correctly
        self.params.coverage_days_rules = [
            CoverageDaysRule(channel_id='C1_store', abc_class='A', coverage_days=10)
        ]
        self.params.outlet_sku_capacity_rules = [
            OutletSKUCapacityRule(channel_id='C3_outlet', division='DivY', axe='Axe1', max_skus=1)
        ]
        self.params.push_new_sku_rules = [
            PushNewSKURule(division='DivX', subaxis='Sub1', push_quantity=5)
        ]
        
        abc_map = {
            ('P1', 'C1_store'): 'A', ('P1', 'C2_store'): 'A',
            ('P2', 'C1_store'): 'B', ('P2', 'C4_outlet'): 'B',
            ('P3', 'C2_store'): 'C', ('P3', 'C3_outlet'): 'C',
            ('P4', 'C4_outlet'): 'C',
            ('P4', 'C1_store'): 'NEW'
        }

        model, status, results = optimize_allocation(
            self.products_df,
            self.channels_df,
            self.inventory_df,
            self.demand_dict,
            self.params,
            self.existing_stock_dict,
            abc_map,
            self.sellin_ranking_dict
        )

        self.assertIsInstance(model, pulp.LpProblem)
        self.assertEqual(status, 'Optimal')
        self.assertIsInstance(results, list)

if __name__ == '__main__':
    unittest.main()
