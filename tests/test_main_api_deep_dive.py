import unittest
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from main import app # Assuming your Flask app instance is named 'app' in main.py
from backend.models import db, Allocation # Import db and any models needed for mocking

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

        # Mock load_products_df
        mock_prods_df = pd.DataFrame({
            'name': ['Test Product'],
            'brand': ['TestBrand'],
            'div': ['TestDiv'],
            'axe': ['TestAxe'],
            'subAxe': ['TestSubAxe'],
            'metier': ['TestMetier'],
            'sku': ['SKU123']
        }, index=pd.Index([test_ean], name='ean'))
        mock_load_prods.return_value = mock_prods_df

        # Mock load_inventory_df (for bad stock)
        mock_bad_stock_df = pd.DataFrame({
            'product_ean': [test_ean, test_ean],
            'quantity': [100, 50],
            'plant': ['P1', 'P2'],
            'stockOrigin': ['Plant Alpha', 'Plant Beta'],
            'flagExcess6months': [1, 0],
            'flagExcess12months': [0, 1]
        })
        mock_load_inv.return_value = mock_bad_stock_df
        
        # Mock load_channels_df
        mock_channels_df = pd.DataFrame({
            'name': ['Channel A', 'Channel B'],
            'channel_type': ['outlet', 'store']
        }, index=pd.Index(['CH_A', 'CH_B'], name='id'))
        mock_load_channels.return_value = mock_channels_df

        # Mock load_existing_stock_dict
        mock_load_existing_stock.return_value = {
            (test_ean, 'CH_A'): 20,
            (test_ean, 'CH_B'): 5
        }
        
        # Mock pd.read_csv (used for sellout and in_store_inventory for ABC)
        # Sellout data for the EAN
        mock_sellout_data = pd.DataFrame({
            'barcode': [test_ean, test_ean],
            'store_code': ['CH_A', 'CH_A'],
            'total_items_weekly': [10, 15]
        })
        # In-store inventory for ABC
        mock_instore_inv_data = pd.DataFrame({
            'barcode': [test_ean],
            'store_code': ['CH_A'],
            'physical_quantity': [30]
        })
        mock_pd_read_csv.side_effect = [mock_sellout_data, mock_instore_inv_data] # Order matters

        # Mock calculate_abc_classification_and_new_skus
        mock_calc_abc.return_value = {
            (test_ean, 'CH_A'): 'A',
            (test_ean, 'CH_B'): 'NEW'
        }
        
        # Mock load_demand_dict
        mock_load_demand.return_value = {
            (test_ean, 'CH_A'): 25, # Sum of 10+15 from mock_sellout_data
            (test_ean, 'CH_B'): 0
        }

        # Mock load_optimization_rules (return empty lists for simplicity for now)
        mock_load_opt_rules.return_value = [] 
        
        # Mock Allocation.query.filter_by().all()
        mock_alloc_ch_a = MagicMock(spec=Allocation)
        mock_alloc_ch_a.product_ean = test_ean
        mock_alloc_ch_a.channel_id_string = 'CH_A'
        mock_alloc_ch_a.quantity = 15
        mock_alloc_ch_a.allocation_date = datetime.utcnow()
        mock_allocation_query.filter_by.return_value.all.return_value = [mock_alloc_ch_a]

        # --- API Call ---
        response = self.client.get(f'/api/ean_deep_dive_data?ean={test_ean}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode())

        # --- Assertions ---
        self.assertEqual(data['ean'], test_ean)
        self.assertEqual(data['product_info']['description'], 'Test Product')
        self.assertEqual(data['initial_stock']['bad_stock_to_allocate'], 150)
        self.assertEqual(len(data['initial_stock']['bad_stock_plant_breakdown']), 2)
        self.assertEqual(data['initial_stock']['total_existing_channel_stock'], 25)
        
        self.assertEqual(len(data['channel_performance']), 2)
        cp_ch_a = next(item for item in data['channel_performance'] if item["channel_id"] == "CH_A")
        self.assertEqual(cp_ch_a['sellout_qty'], 25)
        self.assertEqual(cp_ch_a['abc_class'], 'A')
        
        self.assertEqual(len(data['applied_rules']), 2) # One per channel
        
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
