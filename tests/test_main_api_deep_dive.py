import unittest
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime # Import datetime
from main import app # Assuming your Flask app instance is named 'app' in main.py
from backend.models import db, Allocation # Import db and any models needed for mocking
from backend.schemas import CoverageDaysRule, PushNewSKURule, OutletSKUCapacityRule, OutletAssortmentRule # Import schemas for rules

class EanDeepDiveEndpointTestCase(unittest.TestCase):

    def setUp(self):
        """Set up test client and other test variables."""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # Use in-memory SQLite for tests
        self.client = app.test_client()
        
        # Create tables in the in-memory database
        with app.app_context():
            db.create_all()

    def tearDown(self):
        """Clean up after each test."""
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_ean_deep_dive_missing_ean_parameter(self):
        """Test response when EAN parameter is missing."""
        response = self.client.get('/api/ean_deep_dive_data')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data.decode())
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'EAN parameter is required')

    @patch('main.load_products_df') # Mock the utility functions
    @patch('main.load_inventory_df')
    @patch('main.load_existing_stock_dict')
    @patch('main.load_channels_df')
    @patch('main.pd.read_csv') # For sellout_df_full and in_store_inv_df_for_abc
    @patch('main.calculate_abc_classification_and_new_skus')
    @patch('main.load_demand_dict')
    @patch('main.load_optimization_rules')
    @patch('main.Allocation.query') # Mock the database query
    def test_ean_deep_dive_success_basic_data(
            self, mock_allocation_query, mock_load_opt_rules, mock_load_demand,
            mock_calc_abc, mock_pd_read_csv, mock_load_channels, 
            mock_load_existing_stock, mock_load_inv, mock_load_prods):
        """Test successful response with basic mocked data for a valid EAN."""
        
        # --- Mocking Setup ---
        test_ean = "1234567890123"
        test_ean_normalized = "1234567890123" # Assuming this is the normalized form

        # Mock load_products_df
        mock_prods_df = pd.DataFrame({
            'description': ['Test Product Description'], # Changed from 'name'
            'signature': ['TestBrand'], # Changed from 'brand'
            'div': ['TestDiv'],
            'axe': ['TestAxe'],
            'subAxe': ['TestSubAxe'],
            'metier': ['TestMetier'],
            'sku': ['SKU123'],
            'cogs': [10.5] # Added cogs
        }, index=pd.Index([test_ean_normalized], name='ean'))
        mock_load_prods.return_value = mock_prods_df

        # Mock load_inventory_df (for bad stock)
        mock_bad_stock_df = pd.DataFrame({
            'product_ean': [test_ean_normalized, test_ean_normalized],
            'quantity': [100, 50],
            'available_stock': [90, 45], # Added available_stock
            'plant': ['P1', 'P2'],
            'stockOrigin': ['Plant Alpha', 'Plant Beta'],
            'flagExcess6months': [1, 0],
            'flagExcess12months': [0, 1],
            'bad_stock_type': ['Excess 6 months', 'Excess 12 months'] # Added bad_stock_type
        })
        mock_load_inv.return_value = mock_bad_stock_df
        
        # Mock load_channels_df
        mock_channels_df = pd.DataFrame({
            'name': ['Channel A', 'Channel B'],
            'channel_type': ['outlet', 'store'],
            'capacity': [200, 100] # Added capacity
        }, index=pd.Index(['CH_A', 'CH_B'], name='id'))
        mock_load_channels.return_value = mock_channels_df

        # Mock load_existing_stock_dict
        mock_load_existing_stock.return_value = {
            (test_ean_normalized, 'CH_A'): 20,
            (test_ean_normalized, 'CH_B'): 5
        }
        
        # Mock pd.read_csv (used for sellout and in_store_inventory for ABC)
        # Sellout data for the EAN
        mock_sellout_data = pd.DataFrame({
            'barcode': [test_ean, test_ean], # Use original EAN for mock input
            'store_code': ['CH_A', 'CH_A'],
            'total_items_weekly': [10, 15]
        })
        # In-store inventory for ABC
        mock_instore_inv_data = pd.DataFrame({
            'barcode': [test_ean], # Use original EAN for mock input
            'store_code': ['CH_A'],
            'physical_quantity': [30]
        })
        mock_pd_read_csv.side_effect = [mock_sellout_data, mock_instore_inv_data] # Order matters

        # Mock calculate_abc_classification_and_new_skus
        mock_calc_abc.return_value = {
            (test_ean_normalized, 'CH_A'): 'A',
            (test_ean_normalized, 'CH_B'): 'NEW'
        }
        
        # Mock load_demand_dict
        mock_load_demand.return_value = {
            (test_ean_normalized, 'CH_A'): 25, # Sum of 10+15 from mock_sellout_data
            (test_ean_normalized, 'CH_B'): 0
        }

        # Mock load_optimization_rules
        mock_load_opt_rules.side_effect = [
            [CoverageDaysRule(channel_id='CH_A', abc_class='A', coverage_days=7)], # For coverage_rules_list
            [OutletSKUCapacityRule(channel_id='CH_A', division='TestDiv', axe='TestAxe', max_skus=50)], # For outlet_sku_capacity_rules_list
            [OutletAssortmentRule(metier='TestMetier', subaxis='TestSubAxe', brand='TestBrand', max_skus=10)], # For outlet_assortment_rules_list
            [PushNewSKURule(division='TestDiv', subaxis='TestSubAxe', push_quantity=20)] # For push_new_sku_rules_list
        ]
        
        # Mock Allocation.query.filter_by().all()
        mock_alloc_ch_a = MagicMock(spec=Allocation)
        mock_alloc_ch_a.product_ean = test_ean_normalized
        mock_alloc_ch_a.channel_id_string = 'CH_A'
        mock_alloc_ch_a.quantity = 15
        mock_alloc_ch_a.allocation_date = datetime.utcnow()
        mock_allocation_query.filter_by.return_value.all.return_value = [mock_alloc_ch_a]

        # --- API Call ---
        response = self.client.get(f'/api/ean_deep_dive_data?ean={test_ean}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode())

        # --- Assertions ---
        self.assertEqual(data['ean'], test_ean_normalized)
        self.assertEqual(data['product_info']['description'], 'Test Product Description')
        self.assertEqual(data['product_info']['brand'], 'TestBrand') # Check new key
        self.assertEqual(data['product_info']['division'], 'TestDiv') # Check new key
        self.assertEqual(data['product_info']['axe'], 'TestAxe') # Check new key
        self.assertEqual(data['product_info']['sub_axe'], 'TestSubAxe') # Check new key
        self.assertEqual(data['product_info']['metier'], 'TestMetier') # Check new key
        self.assertEqual(data['product_info']['sku'], 'SKU123') # Check new key

        self.assertEqual(data['initial_stock']['bad_stock_to_allocate'], 150) # Sum of 100+50
        self.assertEqual(len(data['initial_stock']['bad_stock_plant_breakdown']), 2)
        self.assertEqual(data['initial_stock']['bad_stock_plant_breakdown'][0]['plant_code'], 'P1')
        self.assertEqual(data['initial_stock']['bad_stock_plant_breakdown'][0]['quantity'], 100)
        self.assertEqual(data['initial_stock']['bad_stock_plant_breakdown'][0]['flag_excess_6m'], 1)
        self.assertEqual(data['initial_stock']['bad_stock_plant_breakdown'][0]['flag_excess_12m'], 0)
        
        self.assertEqual(data['initial_stock']['total_existing_channel_stock'], 25) # Sum of 20+5
        self.assertEqual(len(data['initial_stock']['existing_channel_stock_breakdown']), 2)
        self.assertEqual(data['initial_stock']['existing_channel_stock_breakdown'][0]['channel_id'], 'CH_A')
        self.assertEqual(data['initial_stock']['existing_channel_stock_breakdown'][0]['quantity'], 20)
        
        self.assertEqual(len(data['channel_performance']), 2)
        cp_ch_a = next(item for item in data['channel_performance'] if item["channel_id"] == "CH_A")
        self.assertEqual(cp_ch_a['sellout_qty'], 25)
        self.assertEqual(cp_ch_a['abc_class'], 'A')
        self.assertEqual(cp_ch_a['calculated_demand'], 25) # Check calculated_demand

        cp_ch_b = next(item for item in data['channel_performance'] if item["channel_id"] == "CH_B")
        self.assertEqual(cp_ch_b['sellout_qty'], 0) # No sellout for CH_B
        self.assertEqual(cp_ch_b['abc_class'], 'NEW')
        self.assertEqual(cp_ch_b['calculated_demand'], 0) # Check calculated_demand
        
        self.assertEqual(len(data['applied_rules']), 2) # One per channel (CH_A and CH_B)
        
        # Assertions for applied_rules for CH_A (ABC='A')
        rules_ch_a = next(item for item in data['applied_rules'] if item["channel_id"] == "CH_A")
        self.assertEqual(rules_ch_a['coverage_rule'], 'Class A: 7 days.')
        self.assertEqual(rules_ch_a['push_new_sku_rule'], 'N/A')
        self.assertEqual(rules_ch_a['outlet_sku_capacity_rule'], 'Max 50 SKUs for Div/Axe.')
        self.assertEqual(rules_ch_a['outlet_assortment_rule'], 'Max 10 SKUs for Metier/SubAxe/Brand.')
        self.assertEqual(rules_ch_a['restricted_brand_donation_rule'], 'Brand not restricted.') # TestBrand is not BrandB

        # Assertions for applied_rules for CH_B (ABC='NEW')
        rules_ch_b = next(item for item in data['applied_rules'] if item["channel_id"] == "CH_B")
        self.assertEqual(rules_ch_b['coverage_rule'], 'N/A') # No coverage rule for NEW
        self.assertEqual(rules_ch_b['push_new_sku_rule'], 'Push 20 units.')
        self.assertEqual(rules_ch_b['outlet_sku_capacity_rule'], 'N/A') # CH_B is 'store', not 'outlet'
        self.assertEqual(rules_ch_b['outlet_assortment_rule'], 'N/A') # CH_B is 'store', not 'outlet'
        self.assertEqual(rules_ch_b['restricted_brand_donation_rule'], 'Brand not restricted.') # TestBrand is not BrandB

        self.assertEqual(len(data['final_allocation']), 1)
        self.assertEqual(data['final_allocation'][0]['channel_id'], 'CH_A')
        self.assertEqual(data['final_allocation'][0]['quantity_allocated'], 15)

    # TODO: Add more tests:
    # - EAN found in master but not in other files (sellout, inventory)
    # - EAN not found in master
    # - Test specific rule applications and their text output
    # - Test FileNotFoundError for critical files

if __name__ == '__main__':
    unittest.main()
