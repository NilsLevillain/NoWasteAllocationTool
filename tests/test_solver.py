import pytest
import pandas as pd
import io
import sys
import os
import numpy as np
import time
import pulp
from unittest.mock import patch, MagicMock
from collections import defaultdict

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.solver import (
    calculate_abc_classification_and_new_skus,
    optimize_allocation,
)
from backend.schemas import (
    OptimizationParameters, CoverageDaysRule, OutletSKUCapacityRule,
    OutletAssortmentRule, PushNewSKURule
)

# =============================================================================
# MODULE-LEVEL FIXTURES (shared across all test classes)
# =============================================================================

@pytest.fixture
def sample_products_df():
    """Create realistic product master data"""
    return pd.DataFrame({
        'brand': ['Loreal', 'Loreal', 'Maybelline', 'Maybelline', 'Garnier', 'Garnier'],
        'division': ['LuxDiv', 'LuxDiv', 'MassDiv', 'MassDiv', 'ActiveDiv', 'ActiveDiv'],
        'axe': ['Skincare', 'Makeup', 'Makeup', 'Skincare', 'Haircare', 'Skincare'],
        'subaxis': ['Anti-Age', 'Foundation', 'Mascara', 'Cleanser', 'Shampoo', 'Moisturizer'],
        'metier': ['Face', 'Face', 'Eyes', 'Face', 'Hair', 'Face']
    }, index=['1001', '1002', '1003', '1004', '1005', '1006'])

# Add this fixture at the module level (with other fixtures)

@pytest.fixture
def competing_products_df():
    """Create products that naturally compete in same outlet capacity groups"""
    return pd.DataFrame({
        'brand': ['Loreal', 'Loreal', 'Maybelline', 'Maybelline', 'Garnier', 'Garnier'],
        'division': ['LuxDiv', 'LuxDiv', 'MassDiv', 'MassDiv', 'ActiveDiv', 'ActiveDiv'],
        'axe': ['Skincare', 'Skincare', 'Makeup', 'Makeup', 'Skincare', 'Skincare'],  # Pairs compete!
        'subaxis': ['Anti-Age', 'Moisturizer', 'Mascara', 'Foundation', 'Cleanser', 'Treatment'],
        'metier': ['Face', 'Face', 'Eyes', 'Face', 'Face', 'Face']
    }, index=['1001', '1002', '1003', '1004', '1005', '1006'])

@pytest.fixture
def sample_channels_df():
    """Create realistic channel data"""
    return pd.DataFrame({
        'channel_type': ['store', 'outlet', 'outlet', 'donation', 'store'],
    }, index=['STORE01', 'OUTLET01', 'OUTLET02', 'DONATION01', 'STORE02'])

@pytest.fixture
def sample_inventory_df():
    """Create realistic inventory data with multiple plants"""
    return pd.DataFrame({
        'product_ean': ['1001', '1001', '1002', '1003', '1004', '1005', '1006'],
        'plant': ['PLANT_FR', 'PLANT_DE', 'PLANT_FR', 'PLANT_DE', 'PLANT_FR', 'PLANT_FR', 'PLANT_DE'],
        'quantity': [100, 50, 200, 150, 80, 0, 120],
        'available_stock': [120, 60, 220, 180, 90, 0, 140]
    })

@pytest.fixture
def sample_demand_dict():
    """Create realistic demand data"""
    return {
        ('1001', 'STORE01'): 70,
        ('1001', 'OUTLET01'): 35,
        ('1002', 'STORE01'): 140,
        ('1002', 'OUTLET02'): 28,
        ('1003', 'STORE02'): 42,
        ('1004', 'DONATION01'): 14,
        ('1005', 'STORE01'): 21,
        ('1006', 'OUTLET01'): 49,
    }

@pytest.fixture
def sample_existing_stock_dict():
    """Create existing stock data"""
    return {
        ('1001', 'STORE01'): 15,
        ('1002', 'STORE01'): 30,
        ('1003', 'STORE02'): 5,
    }

@pytest.fixture
def sample_sellin_ranking_dict():
    """Create sellin ranking data for NEW SKUs"""
    return {
        '1001': 85,
        '1002': 92,
        '1003': 45,
        '1004': 15,
        '1005': 0,
        '1006': 78,
    }

@pytest.fixture
def basic_optimization_parameters():
    """Create basic optimization parameters"""
    return OptimizationParameters(
        seasonality_coefficient=1.0,
        restricted_brands_for_donation=[],
        coverage_days_rules=[
            CoverageDaysRule(channel_id='store', abc_class='A', coverage_days=14),
            CoverageDaysRule(channel_id='store', abc_class='B', coverage_days=10),
            CoverageDaysRule(channel_id='store', abc_class='C', coverage_days=7),
            CoverageDaysRule(channel_id='outlet', abc_class='A', coverage_days=21),
            CoverageDaysRule(channel_id='outlet', abc_class='B', coverage_days=14),
            CoverageDaysRule(channel_id='outlet', abc_class='C', coverage_days=10),
        ],
        outlet_sku_capacity_rules=[
            OutletSKUCapacityRule(channel_id='OUTLET01', division='LuxDiv', axe='Skincare', max_skus=2),
            OutletSKUCapacityRule(channel_id='OUTLET02', division='MassDiv', axe='Makeup', max_skus=1),
        ],
        outlet_assortment_rules=[
            OutletAssortmentRule(metier='Face', subaxis='Foundation', brand='Loreal', max_skus=1),
            OutletAssortmentRule(metier='Eyes', subaxis='Mascara', brand='Maybelline', max_skus=1),
        ],
        push_new_sku_rules=[
            PushNewSKURule(division='LuxDiv', subaxis='Anti-Age', push_quantity=25),
            PushNewSKURule(division='MassDiv', subaxis='Mascara', push_quantity=40),
        ]
    )



# =============================================================================
# SCORING COMPETITION FIXTURE
# =============================================================================

@pytest.fixture
def scoring_competition_products_df():
    """Create 5 SKUs that all compete in same outlet capacity group (same division/axe)"""
    return pd.DataFrame({
        'brand': ['Loreal', 'Loreal', 'Maybelline', 'Garnier', 'Loreal'],
        'division': ['LuxDiv', 'LuxDiv', 'LuxDiv', 'LuxDiv', 'LuxDiv'],  # All same division
        'axe': ['Skincare', 'Skincare', 'Skincare', 'Skincare', 'Skincare'],  # All same axe
        'subaxis': ['Anti-Age', 'Moisturizer', 'Serum', 'Cleanser', 'Treatment'],
        'metier': ['Face', 'Face', 'Face', 'Face', 'Face']
    }, index=['2001', '2002', '2003', '2004', '2005'])

@pytest.fixture
def scoring_competition_inventory_df():
    """Inventory for all 5 competing SKUs with adequate stock"""
    return pd.DataFrame({
        'product_ean': ['2001', '2002', '2003', '2004', '2005'],
        'plant': ['PLANT_FR', 'PLANT_FR', 'PLANT_FR', 'PLANT_FR', 'PLANT_FR'],
        'quantity': [100, 100, 100, 100, 100],
        'available_stock': [100, 100, 100, 100, 100]
    })

@pytest.fixture
def scoring_competition_channels_df():
    """Channels including outlets for testing"""
    return pd.DataFrame({
        'channel_type': ['outlet', 'outlet', 'store'],
    }, index=['OUTLET_SCORE', 'OUTLET_MULTI', 'STORE01'])

@pytest.fixture
def scoring_competition_demand_dict():
    """Demand for all SKUs to outlets to enable allocation potential"""
    return {
        ('2001', 'OUTLET_SCORE'): 50, ('2002', 'OUTLET_SCORE'): 50, ('2003', 'OUTLET_SCORE'): 50,
        ('2004', 'OUTLET_SCORE'): 50, ('2005', 'OUTLET_SCORE'): 50,
        ('2001', 'OUTLET_MULTI'): 30, ('2002', 'OUTLET_MULTI'): 30, ('2003', 'OUTLET_MULTI'): 30,
        ('2004', 'OUTLET_MULTI'): 30, ('2005', 'OUTLET_MULTI'): 30,
    }



# =============================================================================
# CRITICAL TEST 1: ABC Classification Logic
# =============================================================================

class TestABCClassification:

    def test_abc_classification_from_ranking_file(self):
        """Test that ABC classification correctly reads from ranking file"""
        
        def mock_read_csv(file_path, sep=';', dtype=None):
            data = {
                'barcode': ['1001', '1002', '1003'],
                'store_code': ['STORE01', 'STORE01', 'STORE02'], 
                'abc_class': ['A', 'B', 'C']
            }
            df = pd.DataFrame(data)
            if dtype:
                for col, col_type in dtype.items():
                    if col in df.columns:
                        df[col] = df[col].astype(col_type)
            return df
        
        products_df = pd.DataFrame({'brand': ['TestBrand', 'TestBrand', 'TestBrand']}, 
                                 index=['1001', '1002', '1003'])
        channels = ['STORE01', 'STORE02']
        in_store_inventory_df = pd.DataFrame(columns=['barcode', 'store_code', 'physical_quantity'])
        
        with patch('backend.solver.pd.read_csv', side_effect=mock_read_csv):
            abc_map = calculate_abc_classification_and_new_skus(
                product_master_df=products_df,
                all_channel_ids=channels,
                in_store_inventory_df=in_store_inventory_df,
                abc_ranking_file_path='dummy.csv'
            )
        
        assert abc_map[('1001', 'STORE01')] == 'A'
        assert abc_map[('1002', 'STORE01')] == 'B'
        assert abc_map[('1003', 'STORE02')] == 'C'

    def test_new_sku_classification_logic(self):
        """Test that NEW SKUs are identified correctly (not in ranking + no stock)"""
        
        def mock_read_csv_empty(file_path, sep=';', dtype=None):
            df = pd.DataFrame(columns=['barcode', 'store_code', 'abc_class'])
            if dtype:
                for col, col_type in dtype.items():
                    if col in df.columns:
                        df[col] = df[col].astype(col_type)
            return df
        
        products_df = pd.DataFrame({'brand': ['TestBrand', 'TestBrand']}, 
                                 index=['1001', '1002'])
        channels = ['STORE01']
        in_store_inventory_df = pd.DataFrame(columns=['barcode', 'store_code', 'physical_quantity'])
        
        with patch('backend.solver.pd.read_csv', side_effect=mock_read_csv_empty):
            abc_map = calculate_abc_classification_and_new_skus(
                product_master_df=products_df,
                all_channel_ids=channels,
                in_store_inventory_df=in_store_inventory_df,
                abc_ranking_file_path='dummy.csv'
            )
        
        assert abc_map[('1001', 'STORE01')] == 'NEW'
        assert abc_map[('1002', 'STORE01')] == 'NEW'

    def test_default_c_classification_with_existing_stock(self):
        """Test that products with existing stock but not in ranking get 'C' classification"""
        
        def mock_read_csv_empty(file_path, sep=';', dtype=None):
            df = pd.DataFrame(columns=['barcode', 'store_code', 'abc_class'])
            if dtype:
                for col, col_type in dtype.items():
                    if col in df.columns:
                        df[col] = df[col].astype(col_type)
            return df
        
        products_df = pd.DataFrame({'brand': ['TestBrand']}, index=['1001'])
        channels = ['STORE01']
        in_store_inventory_df = pd.DataFrame({
            'barcode': ['1001'],
            'store_code': ['STORE01'],
            'physical_quantity': [10]
        })
        
        with patch('backend.solver.pd.read_csv', side_effect=mock_read_csv_empty):
            abc_map = calculate_abc_classification_and_new_skus(
                product_master_df=products_df,
                all_channel_ids=channels,
                in_store_inventory_df=in_store_inventory_df,
                abc_ranking_file_path='dummy.csv'
            )
        
        assert abc_map[('1001', 'STORE01')] == 'C'

# =============================================================================
# CRITICAL TEST 2: Supply Constraints Validation
# =============================================================================

class TestSupplyConstraints:

    def test_supply_constraint_respects_min_stock_available(self, sample_products_df, sample_channels_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict, basic_optimization_parameters):
        """Test that allocation never exceeds min(StockToAllocate, AvailableStock)"""
        
        inventory_df = pd.DataFrame({
            'product_ean': ['1001', '1002'],
            'plant': ['PLANT_FR', 'PLANT_FR'],
            'quantity': [50, 100],      # StockToAllocate
            'available_stock': [80, 90]  # AvailableStock
        })
        
        abc_map = {(ean, ch): 'A' for ean in ['1001', '1002'] for ch in sample_channels_df.index}
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, inventory_df,
            sample_demand_dict, basic_optimization_parameters, 
            sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        allocation_by_ean_plant = defaultdict(int)
        for result in results:
            key = (result['product_sku'], result['plant_code'])
            allocation_by_ean_plant[key] += result['quantity']
        
        assert allocation_by_ean_plant[('1001', 'PLANT_FR')] <= 50
        assert allocation_by_ean_plant[('1002', 'PLANT_FR')] <= 90

    def test_zero_stock_produces_zero_allocation(self, sample_products_df, sample_channels_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict, basic_optimization_parameters):
        """Test that products with zero stock get zero allocation"""
        
        inventory_df = pd.DataFrame({
            'product_ean': ['1001'],
            'plant': ['PLANT_FR'],
            'quantity': [0],
            'available_stock': [0]
        })
        
        abc_map = {('1001', ch): 'A' for ch in sample_channels_df.index}
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, inventory_df,
            sample_demand_dict, basic_optimization_parameters, 
            sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        ean_1001_allocations = [r for r in results if r['product_sku'] == '1001']
        assert len(ean_1001_allocations) == 0

# =============================================================================
# CRITICAL TEST 3: Coverage Days Constraints  
# =============================================================================

class TestCoverageDaysConstraints:

    def test_coverage_days_calculation(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_sellin_ranking_dict):
        """Test that coverage days constraint is calculated correctly"""
        
        demand_dict = {('1001', 'STORE01'): 140}
        existing_stock_dict = {('1001', 'STORE01'): 20}
        
        abc_map = {('1001', 'STORE01'): 'A'}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='store', abc_class='A', coverage_days=14),
            ],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, sample_inventory_df,
            demand_dict, params, existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        ean_1001_to_store01 = sum(r['quantity'] for r in results 
                                 if r['product_sku'] == '1001' and r['channel_id'] == 'STORE01')
        
        assert ean_1001_to_store01 <= 120


# =============================================================================
# COMPREHENSIVE SCORING TEST SUITE
# =============================================================================

class TestComprehensiveScoringSystem:
    
    def test_tier_hierarchy_A_beats_best_C_and_NEW(self, scoring_competition_products_df, 
                                                   scoring_competition_channels_df, 
                                                   scoring_competition_inventory_df,
                                                   scoring_competition_demand_dict):
        """Test Tier 1 (A) beats even best possible Tier 2 (C) and Tier 3 (NEW)"""
        
        # ABC classification: 1 A-class vs 1 best C-class vs 1 best NEW
        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'A',     # Score = 2.0
            ('2002', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 99/100) = 1.99  
            ('2003', 'OUTLET_SCORE'): 'NEW',   # Score = 1 + 0.8 * (99/100) = 1.792
        }
        
        # Give C and NEW the best possible sellin ranks
        sellin_ranking_dict = {'2002': 99, '2003': 99}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[], outlet_assortment_rules=[], push_new_sku_rules=[],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=1)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, scoring_competition_channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # A-class (2.0) should win against C-class (1.99) and NEW (1.792)
        assert '2001' in allocated_skus
        assert '2002' not in allocated_skus  
        assert '2003' not in allocated_skus
        assert len(allocated_skus) == 1  # Constraint binding

    def test_tier_hierarchy_B_beats_best_C_and_NEW(self, scoring_competition_products_df, 
                                                   scoring_competition_channels_df, 
                                                   scoring_competition_inventory_df,
                                                   scoring_competition_demand_dict):
        """Test Tier 1 (B) beats even best possible Tier 2 (C) and Tier 3 (NEW)"""
        
        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'B',     # Score = 2.0
            ('2002', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 99/100) = 1.99  
            ('2003', 'OUTLET_SCORE'): 'NEW',   # Score = 1 + 0.8 * (99/100) = 1.792
        }
        
        sellin_ranking_dict = {'2002': 99, '2003': 99}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[], outlet_assortment_rules=[], push_new_sku_rules=[],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=1)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, scoring_competition_channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # B-class (2.0) should win
        assert '2001' in allocated_skus
        assert len(allocated_skus) == 1

    def test_c_class_scoring_with_sellin_rank(self, scoring_competition_products_df, 
                                              scoring_competition_channels_df, 
                                              scoring_competition_inventory_df,
                                              scoring_competition_demand_dict):
        """Test C class scoring: min(1.99, 1 + (sellin_rank / 100.0))"""
        
        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 80/100) = 1.80
            ('2002', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 95/100) = 1.95
            ('2003', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 50/100) = 1.50
        }
        
        sellin_ranking_dict = {'2001': 80, '2002': 95, '2003': 50}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[], outlet_assortment_rules=[], push_new_sku_rules=[],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=2)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, scoring_competition_channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # 2002 (1.95) and 2001 (1.80) should win over 2003 (1.50)
        assert '2002' in allocated_skus
        assert '2001' in allocated_skus  
        assert '2003' not in allocated_skus
        assert len(allocated_skus) == 2

    def test_c_class_score_capped_at_1_99(self, scoring_competition_products_df, 
                                          scoring_competition_channels_df, 
                                          scoring_competition_inventory_df,
                                          scoring_competition_demand_dict):
        """Test that C class score is capped at 1.99 even with high sellin_rank"""
        
        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 150/100) = 1.99 (capped)
            ('2002', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 98/100) = 1.98
        }
        
        # Give 2001 impossible high sellin rank to test capping
        sellin_ranking_dict = {'2001': 150, '2002': 98}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[], outlet_assortment_rules=[], push_new_sku_rules=[],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=1)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, scoring_competition_channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # 2001 (1.99 capped) should beat 2002 (1.98)
        assert '2001' in allocated_skus
        assert '2002' not in allocated_skus

    def test_new_class_scoring_with_sellin_rank(self, scoring_competition_products_df,
                                                scoring_competition_inventory_df,
                                                scoring_competition_demand_dict):
        """Test NEW class scoring: 1 + 0.8 * (sellin_rank / 100.0)"""
        
        channels_df = pd.DataFrame({'channel_type': ['outlet']}, index=['OUTLET_SCORE'])
        
        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'NEW',
            ('2002', 'OUTLET_SCORE'): 'NEW',
            ('2003', 'OUTLET_SCORE'): 'NEW',
        }
        
        sellin_ranking_dict = {'2001': 90, '2002': 60, '2003': 80}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[], outlet_assortment_rules=[], push_new_sku_rules=[
                PushNewSKURule(division='LuxDiv', subaxis='Anti-Age', push_quantity=100),
                PushNewSKURule(division='LuxDiv', subaxis='Moisturizer', push_quantity=100),
                PushNewSKURule(division='LuxDiv', subaxis='Serum', push_quantity=100),
            ],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=2)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # 2001 (1.72) and 2003 (1.64) should beat 2002 (1.48)
        assert '2001' in allocated_skus
        assert '2003' in allocated_skus
        assert '2002' not in allocated_skus
        assert len(allocated_skus) == 2

    def test_sellin_rank_edge_case_zero(self, scoring_competition_products_df,
                                        scoring_competition_inventory_df,
                                        scoring_competition_demand_dict):
        """Test sellin_rank = 0 results in base scores"""
        
        channels_df = pd.DataFrame({'channel_type': ['outlet']}, index=['OUTLET_SCORE'])

        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'C',
            ('2002', 'OUTLET_SCORE'): 'NEW',
            ('2003', 'OUTLET_SCORE'): 'C',
        }
        
        sellin_ranking_dict = {'2001': 0, '2002': 0, '2003': 50}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[], outlet_assortment_rules=[], push_new_sku_rules=[
                PushNewSKURule(division='LuxDiv', subaxis='Moisturizer', push_quantity=100),
            ],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=1)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # 2003 (1.5) should beat 2001 (1.0) and 2002 (1.0)
        assert '2003' in allocated_skus
        assert len(allocated_skus) == 1

    def test_missing_sellin_rank_defaults_to_zero(self, scoring_competition_products_df, 
                                                  scoring_competition_channels_df, 
                                                  scoring_competition_inventory_df,
                                                  scoring_competition_demand_dict):
        """Test missing sellin_rank defaults to 0 behavior"""
        
        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'C',     # Missing sellin_rank → 0 → Score = 1.0
            ('2002', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 60/100) = 1.60
        }
        
        # Intentionally omit 2001 from sellin_ranking_dict
        sellin_ranking_dict = {'2002': 60}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[], outlet_assortment_rules=[], push_new_sku_rules=[],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=1)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, scoring_competition_channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # 2002 (1.60) should beat 2001 (1.0 from missing sellin_rank)
        assert '2002' in allocated_skus
        assert '2001' not in allocated_skus

    def test_mixed_abc_class_full_competition(self, scoring_competition_products_df,
                                              scoring_competition_inventory_df,
                                              scoring_competition_demand_dict):
        """Test all ABC classes competing with strategic sellin ranks"""
        
        channels_df = pd.DataFrame({'channel_type': ['outlet']}, index=['OUTLET_SCORE'])

        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'A',
            ('2002', 'OUTLET_SCORE'): 'B',
            ('2003', 'OUTLET_SCORE'): 'C',
            ('2004', 'OUTLET_SCORE'): 'NEW',
            ('2005', 'OUTLET_SCORE'): 'C',
        }
        
        sellin_ranking_dict = {'2003': 85, '2004': 90, '2005': 75}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[], outlet_assortment_rules=[], push_new_sku_rules=[
                PushNewSKURule(division='LuxDiv', subaxis='Cleanser', push_quantity=100),
            ],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=3)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # Top 3: A (2.0), B (2.0), C (1.85) should beat C (1.75) and NEW (1.72)
        assert '2001' in allocated_skus  # A class
        assert '2002' in allocated_skus  # B class
        assert '2003' in allocated_skus  # C class (higher score)
        assert '2005' not in allocated_skus  # C class (lower score)
        assert '2004' not in allocated_skus  # NEW class
        assert len(allocated_skus) == 3

    def test_score_tie_breaking_behavior(self, scoring_competition_products_df, 
                                         scoring_competition_channels_df, 
                                         scoring_competition_inventory_df,
                                         scoring_competition_demand_dict):
        """Test what happens when scores are exactly equal"""
        
        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 80/100) = 1.80
            ('2002', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 80/100) = 1.80 (tie!)
            ('2003', 'OUTLET_SCORE'): 'C',     # Score = min(1.99, 1 + 70/100) = 1.70
        }
        
        sellin_ranking_dict = {'2001': 80, '2002': 80, '2003': 70}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[], outlet_assortment_rules=[], push_new_sku_rules=[],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=2)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, scoring_competition_channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # With tie scores, solver can pick either 2001 or 2002, but both should beat 2003
        assert '2003' not in allocated_skus  # Definitely loses (1.70)
        assert len(allocated_skus) == 2
        
        # At least one of the tied SKUs should be allocated
        tie_skus_allocated = len({'2001', '2002'} & allocated_skus)
        assert tie_skus_allocated >= 1

    def test_multiple_outlet_channels_independent_scoring(self, scoring_competition_products_df, 
                                                          scoring_competition_channels_df, 
                                                          scoring_competition_inventory_df,
                                                          scoring_competition_demand_dict):
        """Test scoring works independently across different outlet channels"""
        
        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'A', ('2001', 'OUTLET_MULTI'): 'C',  # Different ABC per channel
            ('2002', 'OUTLET_SCORE'): 'C', ('2002', 'OUTLET_MULTI'): 'A',  
            ('2003', 'OUTLET_SCORE'): 'NEW', ('2003', 'OUTLET_MULTI'): 'NEW',
        }
        
        sellin_ranking_dict = {'2002': 95, '2003': 85}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[], outlet_assortment_rules=[], push_new_sku_rules=[
                PushNewSKURule(division='LuxDiv', subaxis='Serum', push_quantity=100),
            ],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=1),
                OutletSKUCapacityRule(channel_id='OUTLET_MULTI', division='LuxDiv', axe='Skincare', max_skus=1),
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, scoring_competition_channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        outlet_score_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        outlet_multi_allocations = [r for r in results if r['channel_id'] == 'OUTLET_MULTI' and r['quantity'] > 0]
        
        outlet_score_skus = {r['product_sku'] for r in outlet_score_allocations}
        outlet_multi_skus = {r['product_sku'] for r in outlet_multi_allocations}
        
        # OUTLET_SCORE: 2001(A=2.0) should beat 2002(C=1.95) and 2003(NEW=1.68)  
        assert '2001' in outlet_score_skus
        
        # OUTLET_MULTI: 2002(A=2.0) should beat 2001(C=1.0) and 2003(NEW=1.68)
        assert '2002' in outlet_multi_skus

    def test_coverage_days_interaction_with_scoring(self, scoring_competition_products_df,
                                                    scoring_competition_inventory_df,
                                                    scoring_competition_demand_dict):
        """Test whether coverage days constraints interfere with scoring priorities"""
        
        channels_df = pd.DataFrame({'channel_type': ['outlet']}, index=['OUTLET_SCORE'])

        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'A',
            ('2002', 'OUTLET_SCORE'): 'C',
        }
        
        sellin_ranking_dict = {'2002': 85}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            outlet_assortment_rules=[], push_new_sku_rules=[],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='outlet', abc_class='A', coverage_days=5),
                CoverageDaysRule(channel_id='outlet', abc_class='C', coverage_days=30),
            ],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=1)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # With the lexicographical objective, the higher-scoring SKU should always be chosen,
        # as long as it can be allocated at least 1 unit.
        # Here, SKU '2001' (Score 2.0) should be chosen over SKU '2002' (Score 1.85).
        assert '2001' in allocated_skus
        assert '2002' not in allocated_skus
        assert len(allocated_skus) == 1

    def test_complex_multi_constraint_scoring_scenario(self, scoring_competition_products_df,
                                                       scoring_competition_inventory_df,
                                                       scoring_competition_demand_dict):
        """Test scoring under multiple interacting constraints"""
        
        channels_df = pd.DataFrame({'channel_type': ['outlet']}, index=['OUTLET_SCORE'])

        abc_map = {
            ('2001', 'OUTLET_SCORE'): 'A',
            ('2002', 'OUTLET_SCORE'): 'B',
            ('2003', 'OUTLET_SCORE'): 'C',
            ('2004', 'OUTLET_SCORE'): 'NEW',
            ('2005', 'OUTLET_SCORE'): 'C',
        }
        
        sellin_ranking_dict = {'2003': 90, '2004': 93, '2005': 80}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0, restricted_brands_for_donation=[], 
            coverage_days_rules=[
                CoverageDaysRule(channel_id='outlet', abc_class='A', coverage_days=15),
                CoverageDaysRule(channel_id='outlet', abc_class='B', coverage_days=12),
                CoverageDaysRule(channel_id='outlet', abc_class='C', coverage_days=8),
            ],
            outlet_assortment_rules=[
                OutletAssortmentRule(metier='Face', subaxis='Anti-Age', brand='Loreal', max_skus=1),
            ],
            push_new_sku_rules=[
                PushNewSKURule(division='LuxDiv', subaxis='Cleanser', push_quantity=25),
            ],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET_SCORE', division='LuxDiv', axe='Skincare', max_skus=3)
            ]
        )
        
        model, status, results = optimize_allocation(
            scoring_competition_products_df, channels_df, 
            scoring_competition_inventory_df, scoring_competition_demand_dict, 
            params, {}, abc_map, sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        outlet_allocations = [r for r in results if r['channel_id'] == 'OUTLET_SCORE' and r['quantity'] > 0]
        allocated_skus = {r['product_sku'] for r in outlet_allocations}
        
        # With the lexicographical objective, the highest scoring feasible SKUs should be prioritized.
        # Top 3 scores: 2001 (A, 2.0), 2002 (B, 2.0), 2003 (C, 1.90)
        # All are feasible. The assortment rule on '2001' does not prevent its selection, just limits others if they were in the same group.
        assert '2001' in allocated_skus
        assert '2002' in allocated_skus
        assert '2003' in allocated_skus
        assert len(allocated_skus) == 3  # Respects outlet capacity constraint



# =============================================================================
# CRITICAL TEST 5: Restricted Brands
# =============================================================================

class TestRestrictedBrands:

    def test_restricted_brands_for_donation(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test that restricted brands cannot go to donation channels"""
        
        abc_map = {('1001', 'DONATION01'): 'A'}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=['Loreal'],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='donation', abc_class='A', coverage_days=30),
            ],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, sample_inventory_df,
            sample_demand_dict, params, sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        loreal_to_donation = [r for r in results 
                            if r['product_sku'] == '1001' and r['channel_id'] == 'DONATION01']
        assert len(loreal_to_donation) == 0

# =============================================================================
# SIMPLE INTEGRATION TEST
# =============================================================================

class TestBasicIntegration:

    def test_optimize_allocation_basic_functionality(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict, basic_optimization_parameters):
        """Test basic functionality of the optimization"""
        
        # Create simple ABC map
        abc_map = {}
        for ean in sample_products_df.index:
            for channel in sample_channels_df.index:
                abc_map[(ean, channel)] = 'A'  # All A class for simplicity
        
        model, status, results = optimize_allocation(
            sample_products_df,
            sample_channels_df,
            sample_inventory_df,
            sample_demand_dict,
            basic_optimization_parameters,
            sample_existing_stock_dict,
            abc_map,
            sample_sellin_ranking_dict
        )
        
        # Basic checks
        assert isinstance(model, pulp.LpProblem)
        assert status == 'Optimal'
        assert isinstance(results, list)
        
        # Check that results have correct format
        for item in results:
            assert 'product_sku' in item
            assert 'plant_code' in item
            assert 'channel_id' in item
            assert 'quantity' in item
            assert isinstance(item['quantity'], int)
            assert item['quantity'] > 0


# =============================================================================
# CRITICAL TEST 6: Outlet Assortment Constraints (MISSING)
# =============================================================================

class TestOutletAssortmentConstraints:

    def test_outlet_assortment_limit_enforced(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test that outlet assortment limits are enforced by metier-subaxis-brand"""
        
        # Create scenario where multiple products in same metier-subaxis-brand group want to go to outlet
        abc_map = {
            ('1001', 'OUTLET01'): 'A',  # Loreal, Face, Foundation 
            ('1002', 'OUTLET01'): 'A',  # Loreal, Face, Foundation (same group)
            # Both want to go to OUTLET01, but assortment rule allows only 1
        }
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='outlet', abc_class='A', coverage_days=30),  # High coverage to allow allocation
            ],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[
                OutletAssortmentRule(metier='Face', subaxis='Foundation', brand='Loreal', max_skus=1),  # Only 1 SKU allowed
            ],
            push_new_sku_rules=[]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, sample_inventory_df,
            sample_demand_dict, params, sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        # Count unique EANs allocated to OUTLET01 in Face-Foundation-Loreal group
        face_foundation_loreal_eans_in_outlet01 = set()
        for result in results:
            if result['channel_id'] == 'OUTLET01' and result['quantity'] > 0:
                ean = result['product_sku']
                if ean in ['1001', '1002']:  # Both are Loreal Face Foundation
                    face_foundation_loreal_eans_in_outlet01.add(ean)
        
        # Should not exceed assortment limit
        assert len(face_foundation_loreal_eans_in_outlet01) <= 1

    def test_outlet_assortment_different_groups_independent(self, sample_products_df, sample_inventory_df, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test that different metier-subaxis-brand groups have independent limits"""
        
        channels_df = pd.DataFrame({'channel_type': ['outlet']}, index=['OUTLET01'])
        
        demand_dict = {
            ('1001', 'OUTLET01'): 35,
            ('1003', 'OUTLET01'): 20, 
        }

        abc_map = {
            ('1001', 'OUTLET01'): 'A',
            ('1003', 'OUTLET01'): 'A',
        }
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='outlet', abc_class='A', coverage_days=30),
            ],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[
                OutletAssortmentRule(metier='Face', subaxis='Foundation', brand='Loreal', max_skus=1),
                OutletAssortmentRule(metier='Eyes', subaxis='Mascara', brand='Maybelline', max_skus=1),
            ],
            push_new_sku_rules=[]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, channels_df, sample_inventory_df,
            demand_dict, params, sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        # Both should be able to allocate since they're in different groups
        allocated_eans = set(r['product_sku'] for r in results if r['channel_id'] == 'OUTLET01' and r['quantity'] > 0)
        
        # Both EANs should be able to allocate since they are in different assortment groups
        assert '1001' in allocated_eans
        assert '1003' in allocated_eans

# =============================================================================
# CRITICAL TEST 7: New SKU Push Constraints (MISSING)
# =============================================================================

class TestNewSKUPushConstraints:

    def test_new_sku_push_quantity_limit_strict(self, sample_products_df, sample_channels_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test that NEW SKUs strictly respect push quantity limits"""
        
        # Create inventory with high stock but low push limit
        inventory_df = pd.DataFrame({
            'product_ean': ['1001'],  # LuxDiv, Anti-Age
            'plant': ['PLANT_FR'],
            'quantity': [100],    # High stock
            'available_stock': [100]
        })
        
        abc_map = {('1001', 'STORE01'): 'NEW'}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[
                PushNewSKURule(division='LuxDiv', subaxis='Anti-Age', push_quantity=15),  # Low limit
            ]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, inventory_df,
            sample_demand_dict, params, sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        # Check that NEW SKU allocation doesn't exceed push limit
        new_sku_allocation = sum(r['quantity'] for r in results 
                               if r['product_sku'] == '1001' and r['channel_id'] == 'STORE01')
        
        assert new_sku_allocation <= 15

    def test_new_sku_zero_push_prevents_allocation(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test that zero push quantity prevents NEW SKU allocation"""
        
        abc_map = {('1001', 'STORE01'): 'NEW'}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[
                PushNewSKURule(division='LuxDiv', subaxis='Anti-Age', push_quantity=0),  # Zero push
            ]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, sample_inventory_df,
            sample_demand_dict, params, sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        # Should have zero allocation for NEW SKU with zero push
        new_sku_allocation = sum(r['quantity'] for r in results 
                               if r['product_sku'] == '1001' and r['channel_id'] == 'STORE01')
        
        assert new_sku_allocation == 0

    def test_new_sku_missing_push_rule_prevents_allocation(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test that missing push rule prevents NEW SKU allocation"""
        
        abc_map = {('1001', 'STORE01'): 'NEW'}  # LuxDiv, Anti-Age
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[
                # No rule for LuxDiv-Anti-Age combination
                PushNewSKURule(division='MassDiv', subaxis='Mascara', push_quantity=40),
            ]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, sample_inventory_df,
            sample_demand_dict, params, sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        # Should have zero allocation for NEW SKU without push rule
        new_sku_allocation = sum(r['quantity'] for r in results 
                               if r['product_sku'] == '1001' and r['channel_id'] == 'STORE01')
        
        assert new_sku_allocation == 0

# =============================================================================
# CRITICAL TEST 8: Multi-Plant Allocation Logic (MISSING)
# =============================================================================

class TestMultiPlantAllocation:

    def test_allocation_across_multiple_plants(self, sample_products_df, sample_channels_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test that allocation correctly handles multiple plants for same EAN"""
        
        # Same EAN at multiple plants
        inventory_df = pd.DataFrame({
            'product_ean': ['1001', '1001', '1001'],  # Same EAN
            'plant': ['PLANT_FR', 'PLANT_DE', 'PLANT_IT'],  # Different plants
            'quantity': [30, 40, 50],
            'available_stock': [30, 40, 50]
        })
        
        # High demand to encourage allocation from multiple plants
        demand_dict = {('1001', 'STORE01'): 200}
        
        abc_map = {('1001', 'STORE01'): 'A'}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='store', abc_class='A', coverage_days=30),  # High coverage
            ],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, inventory_df,
            demand_dict, params, sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        # Check allocation from each plant
        allocation_by_plant = {}
        for result in results:
            if result['product_sku'] == '1001' and result['channel_id'] == 'STORE01':
                allocation_by_plant[result['plant_code']] = result['quantity']
        
        # Verify allocations don't exceed plant capacity
        assert allocation_by_plant.get('PLANT_FR', 0) <= 30
        assert allocation_by_plant.get('PLANT_DE', 0) <= 40
        assert allocation_by_plant.get('PLANT_IT', 0) <= 50
        
        # Total allocation should be sum from all plants
        total_allocation = sum(allocation_by_plant.values())
        assert total_allocation <= 120  # Sum of all plant capacities

    def test_plant_with_zero_stock_excluded(self, sample_products_df, sample_channels_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test that plants with zero stock are excluded from allocation"""
        
        inventory_df = pd.DataFrame({
            'product_ean': ['1001', '1001'],
            'plant': ['PLANT_FR', 'PLANT_DE'],
            'quantity': [50, 0],      # PLANT_DE has zero stock
            'available_stock': [50, 0]
        })
        
        demand_dict = {('1001', 'STORE01'): 100}
        abc_map = {('1001', 'STORE01'): 'A'}
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='store', abc_class='A', coverage_days=30),
            ],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, inventory_df,
            demand_dict, params, sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        # Should have no allocation from PLANT_DE (zero stock)
        plant_de_allocations = [r for r in results 
                              if r['product_sku'] == '1001' and r['plant_code'] == 'PLANT_DE']
        assert len(plant_de_allocations) == 0
        
        # Should have allocation from PLANT_FR only
        plant_fr_allocations = [r for r in results 
                              if r['product_sku'] == '1001' and r['plant_code'] == 'PLANT_FR']
        assert len(plant_fr_allocations) > 0

# =============================================================================
# CRITICAL TEST 9: Constraint Conflict & Infeasibility (MISSING)
# =============================================================================

class TestConstraintConflicts:

    def test_supply_vs_multiple_constraints_interaction(self, sample_products_df, sample_channels_df, sample_sellin_ranking_dict):
        """Test complex interaction between supply, coverage, and capacity constraints"""
        
        # Limited supply
        inventory_df = pd.DataFrame({
            'product_ean': ['1001', '1002'],
            'plant': ['PLANT_FR', 'PLANT_FR'],
            'quantity': [20, 25],    # Limited supply
            'available_stock': [20, 25]
        })
        
        # High demand that would exceed supply
        demand_dict = {
            ('1001', 'OUTLET01'): 100,  # Much higher than supply
            ('1002', 'OUTLET01'): 120,
        }
        
        abc_map = {
            ('1001', 'OUTLET01'): 'A',  # LuxDiv, Skincare
            ('1002', 'OUTLET01'): 'A',  # LuxDiv, Makeup
        }
        
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='outlet', abc_class='A', coverage_days=30),  # Would allow much more
            ],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET01', division='LuxDiv', axe='Skincare', max_skus=1),  # Limits SKUs
            ],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, inventory_df,
            demand_dict, params, {}, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'  # Should still be solvable
        
        # Verify multiple constraints are respected
        allocation_by_ean = defaultdict(int)
        luxdiv_skincare_skus = set()
        
        for result in results:
            if result['channel_id'] == 'OUTLET01':
                ean = result['product_sku']
                allocation_by_ean[ean] += result['quantity']
                
                # Check SKU capacity constraint
                if ean in sample_products_df.index:
                    product_info = sample_products_df.loc[ean]
                    if product_info['division'] == 'LuxDiv' and product_info['axe'] == 'Skincare':
                        luxdiv_skincare_skus.add(ean)
        
        # Supply constraints should be respected
        assert allocation_by_ean['1001'] <= 20
        assert allocation_by_ean['1002'] <= 25
        
        # SKU capacity constraint should be respected
        assert len(luxdiv_skincare_skus) <= 1

    def test_very_restrictive_constraints_scenario(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test behavior with very restrictive constraints that might create infeasibility"""
        
        abc_map = {(ean, ch): 'A' for ean in sample_products_df.index for ch in ['OUTLET01']}
        
        params = OptimizationParameters(
            seasonality_coefficient=0.1,  # Very low seasonality (restrictive)
            restricted_brands_for_donation=[],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='outlet', abc_class='A', coverage_days=1),  # Very low coverage
            ],
            outlet_sku_capacity_rules=[
                OutletSKUCapacityRule(channel_id='OUTLET01', division='LuxDiv', axe='Skincare', max_skus=0),  # Zero SKUs allowed
                OutletSKUCapacityRule(channel_id='OUTLET01', division='MassDiv', axe='Makeup', max_skus=0),
            ],
            outlet_assortment_rules=[
                OutletAssortmentRule(metier='Face', subaxis='Foundation', brand='Loreal', max_skus=0),
            ],
            push_new_sku_rules=[]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, sample_inventory_df,
            sample_demand_dict, params, sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        # Should either be optimal with minimal allocation or infeasible
        assert status in ['Optimal', 'Infeasible']
        
        if status == 'Optimal':
            # If optimal, allocations should be very limited due to restrictive constraints
            total_allocation = sum(r['quantity'] for r in results if r['channel_id'] == 'OUTLET01')
            assert total_allocation <= 50  # Should be quite limited

# =============================================================================
# CRITICAL TEST 10: Edge Cases & Input Validation (MISSING)
# =============================================================================

class TestEdgeCasesAndValidation:

    def test_negative_seasonality_coefficient_validation(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test that negative seasonality coefficient raises validation error"""
        
        abc_map = {('1001', 'STORE01'): 'A'}
        
        # This should raise a validation error
        with pytest.raises(ValueError, match="seasonality_coefficient"):
            params = OptimizationParameters(
                seasonality_coefficient=-0.5,  # Invalid negative value
                restricted_brands_for_donation=[],
                coverage_days_rules=[
                    CoverageDaysRule(channel_id='store', abc_class='A', coverage_days=14),
                ],
                outlet_sku_capacity_rules=[],
                outlet_assortment_rules=[],
                push_new_sku_rules=[]
            )

    def test_zero_seasonality_coefficient(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict):
        """Test handling of zero seasonality coefficient"""
        
        abc_map = {('1001', 'STORE01'): 'A'}
        
        params = OptimizationParameters(
            seasonality_coefficient=0.0,  # Zero seasonality
            restricted_brands_for_donation=[],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='store', abc_class='A', coverage_days=14),
            ],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, sample_inventory_df,
            sample_demand_dict, params, sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        # With zero seasonality, coverage days constraints should be very restrictive
        ean_1001_allocation = sum(r['quantity'] for r in results 
                                if r['product_sku'] == '1001' and r['channel_id'] == 'STORE01')
        
        # Should be limited due to zero seasonality effect
        assert ean_1001_allocation >= 0  # Should not crash, at least

    def test_missing_demand_data(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_existing_stock_dict, sample_sellin_ranking_dict, basic_optimization_parameters):
        """Test handling of missing demand data"""
        
        # Empty demand dictionary
        demand_dict = {}
        abc_map = {('1001', 'STORE01'): 'A'}
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, sample_inventory_df,
            demand_dict, basic_optimization_parameters, 
            sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        # Should still be optimal (allocation driven by scoring, not demand)
        assert status == 'Optimal'
        assert isinstance(results, list)

    def test_empty_inventory(self, sample_products_df, sample_channels_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict, basic_optimization_parameters):
        """Test handling of empty inventory"""
        
        # Empty inventory
        inventory_df = pd.DataFrame(columns=['product_ean', 'plant', 'quantity', 'available_stock'])
        abc_map = {}
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, inventory_df,
            sample_demand_dict, basic_optimization_parameters, 
            sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        # Should be optimal with no results
        assert status == 'Optimal'
        assert len(results) == 0



class TestParameterValidation:
    
    def test_negative_coverage_days_validation(self):
        """Test that negative coverage days raise validation error"""
        
        with pytest.raises(ValueError):
            CoverageDaysRule(channel_id='store', abc_class='A', coverage_days=-5)
    
    def test_negative_max_skus_validation(self):
        """Test that negative max SKUs raise validation error"""
        
        with pytest.raises(ValueError):
            OutletSKUCapacityRule(channel_id='OUTLET01', division='Div', axe='Axe', max_skus=-1)
    
    def test_negative_push_quantity_validation(self):
        """Test that negative push quantity raises validation error"""
        
        with pytest.raises(ValueError):
            PushNewSKURule(division='Div', subaxis='SubAxe', push_quantity=-10)
    
    def test_empty_string_parameters_validation(self):
        """Test that empty string parameters raise validation errors"""
        
        with pytest.raises(ValueError):
            CoverageDaysRule(channel_id='', abc_class='A', coverage_days=10)
        
        with pytest.raises(ValueError):
            CoverageDaysRule(channel_id='store', abc_class='', coverage_days=10)
    
    def test_invalid_abc_class_validation(self):
        """Test that invalid ABC classes raise validation errors"""
        
        with pytest.raises(ValueError):
            CoverageDaysRule(channel_id='store', abc_class='X', coverage_days=10)  # Invalid ABC class



# =============================================================================
# CRITICAL TEST 11: Performance & Scale Testing (MISSING)
# =============================================================================

class TestPerformanceAndScale:

    def test_larger_scale_scenario(self):
        """Test solver performance with larger, more realistic dataset"""
        
        # Create larger dataset
        n_products = 50
        n_channels = 10
        n_plants = 5
        
        # Generate products
        products_df = pd.DataFrame({
            'brand': [f'Brand_{i%5}' for i in range(n_products)],
            'division': [f'Div_{i%3}' for i in range(n_products)],
            'axe': [f'Axe_{i%4}' for i in range(n_products)],
            'subaxis': [f'SubAxis_{i%6}' for i in range(n_products)],
            'metier': [f'Metier_{i%3}' for i in range(n_products)]
        }, index=[f'{1000+i}' for i in range(n_products)])
        
        # Generate channels
        channels_df = pd.DataFrame({
            'channel_type': ['store', 'outlet', 'donation'][i%3] for i in range(n_channels)
        }, index=[f'CH_{i:02d}' for i in range(n_channels)])
        
        # Generate inventory (each product at 2-3 plants)
        inventory_data = []
        for i in range(n_products):
            for j in range(2):  # 2 plants per product
                inventory_data.append({
                    'product_ean': f'{1000+i}',
                    'plant': f'PLANT_{j}',
                    'quantity': np.random.randint(10, 100),
                    'available_stock': np.random.randint(10, 120)
                })
        
        inventory_df = pd.DataFrame(inventory_data)
        
        # Generate demand
        demand_dict = {}
        for i in range(n_products):
            for j in range(n_channels):
                if np.random.random() > 0.7:  # 30% chance of demand
                    demand_dict[(f'{1000+i}', f'CH_{j:02d}')] = np.random.randint(5, 50)
        
        # Generate ABC map
        abc_map = {}
        for i in range(n_products):
            for j in range(n_channels):
                abc_map[(f'{1000+i}', f'CH_{j:02d}')] = np.random.choice(['A', 'B', 'C', 'NEW'])
        
        # Basic parameters
        params = OptimizationParameters(
            seasonality_coefficient=1.0,
            restricted_brands_for_donation=[],
            coverage_days_rules=[
                CoverageDaysRule(channel_id='store', abc_class='A', coverage_days=14),
                CoverageDaysRule(channel_id='outlet', abc_class='A', coverage_days=21),
                CoverageDaysRule(channel_id='donation', abc_class='A', coverage_days=30),
            ],
            outlet_sku_capacity_rules=[],
            outlet_assortment_rules=[],
            push_new_sku_rules=[]
        )
        
        sellin_ranking_dict = {f'{1000+i}': np.random.randint(0, 100) for i in range(n_products)}
        
        # Time the optimization
        start_time = time.time()
        
        model, status, results = optimize_allocation(
            products_df, channels_df, inventory_df,
            demand_dict, params, {}, abc_map, sellin_ranking_dict
        )
        
        end_time = time.time()
        solve_time = end_time - start_time
        
        # Performance assertions
        assert status == 'Optimal'
        assert solve_time < 30.0  # Should solve within 30 seconds
        assert len(results) >= 0  # Should produce some results
        
        print(f"Solved {n_products} products x {n_channels} channels in {solve_time:.2f} seconds")

# =============================================================================
# CRITICAL TEST 12: Result Validation (MISSING)
# =============================================================================

class TestResultValidation:

    def test_allocation_mathematical_consistency(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict, basic_optimization_parameters):
        """Test that allocation results are mathematically consistent"""
        
        abc_map = {(ean, ch): 'A' for ean in sample_products_df.index for ch in sample_channels_df.index}
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, sample_inventory_df,
            sample_demand_dict, basic_optimization_parameters, 
            sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        # Validate result format
        for result in results:
            assert isinstance(result['product_sku'], str)
            assert isinstance(result['plant_code'], str)
            assert isinstance(result['channel_id'], str)
            assert isinstance(result['quantity'], int)
            assert result['quantity'] > 0
        
        # Validate supply constraints are respected
        allocation_by_ean_plant = defaultdict(int)
        for result in results:
            key = (result['product_sku'], result['plant_code'])
            allocation_by_ean_plant[key] += result['quantity']
        
        # Check against inventory constraints
        inventory_lookup = {}
        for _, row in sample_inventory_df.iterrows():
            key = (row['product_ean'], row['plant'])
            max_allocatable = min(row['quantity'], row['available_stock'])
            inventory_lookup[key] = max_allocatable
        
        for (ean, plant), allocated_qty in allocation_by_ean_plant.items():
            max_allowed = inventory_lookup.get((ean, plant), 0)
            assert allocated_qty <= max_allowed, f"Allocation {allocated_qty} exceeds limit {max_allowed} for {ean} at {plant}"

    def test_no_negative_allocations(self, sample_products_df, sample_channels_df, sample_inventory_df, sample_demand_dict, sample_existing_stock_dict, sample_sellin_ranking_dict, basic_optimization_parameters):
        """Test that no negative allocations are produced"""
        
        abc_map = {(ean, ch): 'C' for ean in sample_products_df.index for ch in sample_channels_df.index}
        
        model, status, results = optimize_allocation(
            sample_products_df, sample_channels_df, sample_inventory_df,
            sample_demand_dict, basic_optimization_parameters, 
            sample_existing_stock_dict, abc_map, sample_sellin_ranking_dict
        )
        
        assert status == 'Optimal'
        
        # All quantities should be positive
        for result in results:
            assert result['quantity'] >= 0
            assert result['quantity'] == int(result['quantity'])  # Should be integer







if __name__ == '__main__':
    pytest.main([__file__, '-v'])
