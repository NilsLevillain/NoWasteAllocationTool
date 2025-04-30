import unittest
import pandas as pd
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from solver import optimize_allocation
from schemas import OptimizationParameters

class TestSolver(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Reusable sample data for tests
        cls.sample_products = pd.DataFrame({
            'sku': ['SKU001', 'SKU002', 'SKU003', 'SKU004'],
            'donation_eligible': [True, False, True, True],
            'brand': ['BrandA', 'BrandA', 'BrandB', 'BrandC']
        }).set_index('sku')

        cls.sample_channels = pd.DataFrame({
            'id': ['STORE1', 'OUTLET1', 'DONATE1', 'STORE2'],
            'capacity': [100, 200, 50, 80],
            'min_coverage': [0.5, 0.0, 0.0, 0.6], # STORE1=0.5, STORE2=0.6
            'channel_type': ['store', 'outlet', 'donation', 'store']
        }).set_index('id')

        cls.sample_inventory = pd.DataFrame({
            'product_sku': ['SKU001', 'SKU002', 'SKU003', 'SKU004', 'SKU001'],
            'quantity': [50, 30, 40, 60, 20] # SKU001 has 70 total
        })

        cls.sample_demand = {
            ('SKU001', 'STORE1'): 40, ('SKU002', 'STORE1'): 20, # STORE1 demand = 60
            ('SKU003', 'OUTLET1'): 50,
            ('SKU001', 'STORE2'): 30, ('SKU004', 'STORE2'): 50, # STORE2 demand = 80
        }

        cls.sample_revenue = {
            ('SKU001', 'STORE1'): 10, ('SKU002', 'STORE1'): 12,
            ('SKU003', 'OUTLET1'): 5,
            ('SKU001', 'DONATE1'): 0, ('SKU003', 'DONATE1'): 0, ('SKU004', 'DONATE1'): 0,
            ('SKU001', 'STORE2'): 11, ('SKU004', 'STORE2'): 9,
        }

    def test_basic_optimal_allocation(self):
        """Test if the basic allocation runs and finds an optimal solution."""
        params = OptimizationParameters(
            default_min_coverage=None,
            min_skus_per_store=None,
            restricted_brands_for_donation=None
        )
        status, results = optimize_allocation(
            self.sample_products, self.sample_channels, self.sample_inventory,
            self.sample_demand, self.sample_revenue, params
        )
        self.assertEqual(status, "Optimal")
        self.assertTrue(len(results) > 0) # Check that some allocation happened

    def test_restricted_brand_for_donation(self):
        """Test that restricted brands are not allocated to donation channels."""
        params = OptimizationParameters(
            default_min_coverage=None,
            min_skus_per_store=None,
            restricted_brands_for_donation=['BrandA'] # SKU001, SKU002 are BrandA
        )
        status, results = optimize_allocation(
            self.sample_products, self.sample_channels, self.sample_inventory,
            self.sample_demand, self.sample_revenue, params
        )
        self.assertEqual(status, "Optimal")
        for res in results:
            if res['channel_id'] == 'DONATE1':
                self.assertNotIn(res['product_sku'], ['SKU001', 'SKU002'])

    def test_min_skus_per_store(self):
        """Test the minimum number of unique SKUs allocated to store channels."""
        min_skus_required = 2
        params = OptimizationParameters(
            default_min_coverage=None,
            min_skus_per_store=min_skus_required,
            restricted_brands_for_donation=None
        )
        status, results = optimize_allocation(
            self.sample_products, self.sample_channels, self.sample_inventory,
            self.sample_demand, self.sample_revenue, params
        )
        self.assertEqual(status, "Optimal")

        skus_per_store = {}
        for res in results:
            channel_type = self.sample_channels.loc[res['channel_id'], 'channel_type']
            if channel_type == 'store':
                store_id = res['channel_id']
                if store_id not in skus_per_store:
                    skus_per_store[store_id] = set()
                skus_per_store[store_id].add(res['product_sku'])

        for store_id, skus in skus_per_store.items():
             # Check if the store received any allocation at all before asserting min SKUs
             total_qty_for_store = sum(r['quantity'] for r in results if r['channel_id'] == store_id)
             if total_qty_for_store > 0:
                 self.assertGreaterEqual(len(skus), min_skus_required, f"Store {store_id} received less than {min_skus_required} SKUs.")


    def test_default_min_coverage_override(self):
        """Test that default_min_coverage overrides channel-specific values."""
        default_coverage = 0.7 # Higher than STORE1 (0.5) and STORE2 (0.6)
        params = OptimizationParameters(
            default_min_coverage=default_coverage,
            min_skus_per_store=None,
            restricted_brands_for_donation=None
        )
        status, results = optimize_allocation(
            self.sample_products, self.sample_channels, self.sample_inventory,
            self.sample_demand, self.sample_revenue, params
        )
        self.assertEqual(status, "Optimal")

        # Check specific allocations against the higher default coverage
        allocations_dict = {(res['product_sku'], res['channel_id']): res['quantity'] for res in results}

        # Check SKU001 in STORE1 (Demand 40)
        expected_min_qty_s1_sku1 = 40 * default_coverage
        if ('SKU001', 'STORE1') in self.sample_demand:
             allocated_qty = allocations_dict.get(('SKU001', 'STORE1'), 0)
             self.assertGreaterEqual(allocated_qty, expected_min_qty_s1_sku1, "SKU001 in STORE1 doesn't meet default coverage")

        # Check SKU001 in STORE2 (Demand 30)
        expected_min_qty_s2_sku1 = 30 * default_coverage
        if ('SKU001', 'STORE2') in self.sample_demand:
            allocated_qty = allocations_dict.get(('SKU001', 'STORE2'), 0)
            self.assertGreaterEqual(allocated_qty, expected_min_qty_s2_sku1, "SKU001 in STORE2 doesn't meet default coverage")

        # Check SKU004 in STORE2 (Demand 50)
        expected_min_qty_s2_sku4 = 50 * default_coverage
        if ('SKU004', 'STORE2') in self.sample_demand:
            allocated_qty = allocations_dict.get(('SKU004', 'STORE2'), 0)
            self.assertGreaterEqual(allocated_qty, expected_min_qty_s2_sku4, "SKU004 in STORE2 doesn't meet default coverage")

    def test_objective_prioritizes_quantity(self):
        """Test that the objective function prioritizes maximizing quantity (sell-through)."""
        # Scenario:
        # - SKU_A: High revenue (10), low inventory (10)
        # - SKU_B: Low revenue (1), high inventory (100)
        # - CHAN_HIGH_REV: Low capacity (5), accepts both SKUs
        # - CHAN_LOW_REV: High capacity (100), accepts both SKUs
        # Expected: Max quantity objective should fill CHAN_LOW_REV with SKU_B first,
        #           even though SKU_A has higher revenue per unit.
        #           A pure revenue objective might prioritize filling CHAN_HIGH_REV with SKU_A.

        products = pd.DataFrame({
            'sku': ['SKU_A', 'SKU_B'],
            'donation_eligible': [True, True],
            'brand': ['BrandX', 'BrandY']
        }).set_index('sku')

        channels = pd.DataFrame({
            'id': ['CHAN_HIGH_REV', 'CHAN_LOW_REV'],
            'capacity': [5, 100],
            'min_coverage': [0.0, 0.0],
            'channel_type': ['outlet', 'outlet']
        }).set_index('id')

        inventory = pd.DataFrame({
            'product_sku': ['SKU_A', 'SKU_B'],
            'quantity': [10, 100]
        })

        demand = {
            # No specific demand needed for this objective test
        }

        revenue = {
            ('SKU_A', 'CHAN_HIGH_REV'): 10, ('SKU_B', 'CHAN_HIGH_REV'): 1,
            ('SKU_A', 'CHAN_LOW_REV'): 10,  ('SKU_B', 'CHAN_LOW_REV'): 1,
        }

        params = OptimizationParameters(
            default_min_coverage=None,
            min_skus_per_store=None,
            restricted_brands_for_donation=None
        )

        status, results = optimize_allocation(
            products, channels, inventory, demand, revenue, params
        )
        self.assertEqual(status, "Optimal")

        total_allocated_quantity = sum(res['quantity'] for res in results)
        # Expected total quantity: 10 (SKU_A) + 100 (SKU_B) = 110.
        # The allocation should try to move all available inventory.
        # Let's check if it allocates close to the total inventory (110).
        # Capacity constraints: CHAN_HIGH_REV=5, CHAN_LOW_REV=100. Total capacity = 105.
        # So, the max possible allocation is 105 units.
        # The high weight on quantity should push towards this 105 limit.

        # A simple check: ensure the total quantity is greater than just allocating the high-revenue SKU_A.
        self.assertGreater(total_allocated_quantity, 10, "Objective didn't allocate more than just the high-revenue SKU.")
        # A more specific check: ensure it allocates the maximum possible given capacity.
        self.assertEqual(total_allocated_quantity, 105, "Objective didn't maximize total allocated quantity up to capacity.")

        # Verify that SKU_B was allocated significantly, likely filling CHAN_LOW_REV
        sku_b_allocated = sum(res['quantity'] for res in results if res['product_sku'] == 'SKU_B')
        self.assertGreater(sku_b_allocated, 50, "Low-revenue, high-inventory SKU_B was not allocated in large quantity.")


if __name__ == '__main__':
    unittest.main()
