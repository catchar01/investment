import yfinance as yf
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

end_date = datetime.today().date()
start_date = end_date - timedelta(days=14)

def get_stock_data(stock_symbol):
    start_date = end_date - timedelta(days=240)
    stock_data = yf.download(stock_symbol, start=start_date, end=end_date, progress=False)
    return stock_data

def get_test_stock_data(stock_symbol, test_date):
    #Convert to string for yfinance compatibility
    start_date = test_date.strftime('%Y-%m-%d')
    stock_data = yf.download(stock_symbol, start=start_date, progress=False)
    return stock_data

def get_vix_data():
    vix_data = yf.Ticker("^VIX")
    hist = vix_data.history(start=start_date, end=end_date)
    return hist

def get_sp500_volume():
    sp500_data = yf.Ticker("^GSPC")
    hist = sp500_data.history(start=start_date, end=end_date)
    return hist['Volume']

def get_sp500_data():
    sp500_data = yf.Ticker("^GSPC")
    hist = sp500_data.history(start=start_date, end=end_date)
    return hist['Close']

def get_stock_sectors(stock_names):
    sectors = {}
    for stock_name in stock_names:
        try:
            stock_info = yf.Ticker(stock_name).info
            sector = stock_info.get('sector', 'Unknown')
            sectors[stock_name] = sector
        except Exception as e:
            logger.error(f"Skipping {stock_name} due to error: {e}")
            continue
        
    return sectors

def get_dj_data():
    dj_data = yf.Ticker("^DJI")
    hist = dj_data.history(start=start_date, end=end_date)
    return hist['Close']