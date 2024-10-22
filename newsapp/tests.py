from django.test import TestCase
from django.contrib.auth.models import User
from newsapp.models import FavouriteStock

from django.db.utils import IntegrityError

class FavouriteStockTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('Lucy', 'Lucy@example.com', 'lucypassword123!')

    def test_create_fave_stock(self):
        favourite = FavouriteStock.objects.create(
            user=self.user,
            stock_name="AAPL"
        )

        self.assertEqual(favourite.user.username, 'Lucy')
        self.assertEqual(favourite.stock_name, "AAPL")

        #Test the unique together constraint
        with self.assertRaises(IntegrityError):
            FavouriteStock.objects.create(
                user=self.user,
                stock_name="AAPL"
            )

from sent_scores import sent_score
class SentAnalysisTests(TestCase):
    
    def test_valid_content(self):
        content = "Test that valid content returns a sentiment score within the expected range."
        score, cleaned_content = sent_score(content)
        self.assertIsNotNone(score)
        self.assertTrue(-1 <= score <= 1)
        self.assertNotEqual(cleaned_content, "")

    def test_only_stop_words(self):
        """ Test that content with only stop words returns None for score. """
        content = "and of with to"
        score, cleaned_content = sent_score(content)
        self.assertIsNone(score)
        self.assertEqual(cleaned_content, "")

    def test_empty_content(self):
        """ Test empty content returns None for sent score. """
        content = ""
        score, cleaned_content = sent_score(content)
        self.assertIsNone(score)
        self.assertEqual(cleaned_content, "")

    def test_mixed_content(self):
        """ Test that mixed content handles stop words and calculates score correctly. """
        content = "Profit increases but risk of loss is low."
        score, cleaned_content = sent_score(content)
        self.assertIsNotNone(score)
        self.assertTrue(-1 <= score <= 1)
        self.assertIn("INCREASE", cleaned_content)
        self.assertIn("LOSS", cleaned_content)
        self

from unittest.mock import patch
from django.test import TestCase
from unittest.mock import patch, ANY
import yfinance as yf
from sentiments_stock_data import get_stock_data

##INTEGRATION TEST, WHAT OTHER TYPES?
class YFinanceApiTests(TestCase):
    
    @patch('yfinance.download')
    def test_get_stock_data(self, mock_download):
        mock_response = {
            'Open': [150.00, 152.00, 153.00],
            'High': [155.00, 153.00, 154.00],
            'Low': [149.00, 151.00, 152.00],
            'Close': [153.00, 152.00, 153.00],
            'Volume': [880000, 790000, 900000]
        }
        mock_download.return_value = mock_response

        stock_data = get_stock_data('AAPL')
        
        #Validate response matches mock
        self.assertEqual(stock_data, mock_response)
        mock_download.assert_called_once_with('AAPL', start=ANY, end=ANY, progress=False)