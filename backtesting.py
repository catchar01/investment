import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'take2.settings')
import numpy as np
from sklearn.metrics import mean_absolute_error
from sentiments_stock_data import get_test_stock_data
from stock_prediction import predict_stock_prices_with_sentiment, prepare_data_with_sentiments
from datetime import datetime
import pandas as pd
from tabulate import tabulate

def mape(actual, predicted):
    actual, predicted = np.array(actual), np.array(predicted)
    return np.mean(np.abs((actual - predicted) / actual)) * 100

def backtest_single_stock(stock_symbol, test_date, forecast_out=1):
    test_date = datetime.combine(test_date, datetime.min.time())
    
    stock_data = get_test_stock_data(stock_symbol, test_date)
    if stock_data.empty:
        print(f"No stock data available for {stock_symbol} on {test_date.strftime('%Y-%m-%d')}")
        return None

    prediction = predict_stock_prices_with_sentiment(stock_symbol, forecast_out, test_date)
    if not prediction:
        print(f"No valid prediction for {stock_symbol} on {test_date.strftime('%Y-%m-%d')}")
        return None

    actual_price = stock_data['Close'].get(test_date.strftime('%Y-%m-%d'))
    if actual_price is not None:
        mape_value = mape([actual_price], [prediction[0]])
        mae = mean_absolute_error([actual_price], [prediction[0]])

        train, _ = prepare_data_with_sentiments(stock_symbol, forecast_out, test_date)
        corrActual = train[['Sentiment', 'Close']].corr().iloc[0, 1] if not train.empty else None
        corrPred = train[['Sentiment', 'Prediction']].corr().iloc[0, 1] if not train.empty else None

        return (stock_symbol, actual_price, prediction[0], corrActual, corrPred, mape_value, mae)
    
    print(f"Skipping {stock_symbol} on {test_date.strftime('%Y-%m-%d')} due to no valid actual price or empty predictions.")
    return None

def perform_backtests(stocks):
    test_dates = [datetime(2024, 4, 8), datetime(2024, 4, 16)]

    for test_date in test_dates:
        results = []
        for stock_symbol in stocks:
            result = backtest_single_stock(stock_symbol, test_date)
            if result:
                results.append(result)
        
        if results:
            results_df = pd.DataFrame(results, columns=[
                'Stock', 'Actual', 'Predicted', 'CorrActual', 'corrPred', 'MAPE', 'MAE'
            ])
            
            results_df['Composite'] = (
                (results_df['MAPE'] - results_df['MAPE'].min()) / (results_df['MAPE'].max() - results_df['MAPE'].min()) +
                (results_df['MAE'] - results_df['MAE'].min()) / (results_df['MAE'].max() - results_df['MAE'].min())
            ) / 2

            results_sorted = results_df.sort_values(by='Composite')
            print(f"Results for {test_date.strftime('%Y-%m-%d')}:")
            print(tabulate(results_sorted, headers='keys', tablefmt='psql', showindex=False, numalign="right"))
        else:
            print(f"No valid data was found for {test_date.strftime('%Y-%m-%d')}.")

stocks = [
    'AAPL', 'ABBV', 'ABT', 'ACN', 'ADBE', 'AIG', 'AMGN', 'AMT', 'AMZN', 'AVGO',
    'AXP', 'BA', 'BAC', 'BIIB', 'BK', 'BKNG', 'BLK', 'BMY', 'TSLA', 'C',
    'CAT', 'CHTR', 'CL', 'CMCSA', 'COF', 'COST', 'CRM', 'CSCO', 'CVS', 'CVX',
    'DHR', 'DIS', 'DUK', 'EMR', 'EXC', 'F', 'FDX', 'GD', 'GE',
    'GILD', 'GOOG', 'GOOGL', 'GS', 'HD', 'HON', 'IBM', 'INTC', 'JNJ', 'JPM'
]

backtest_results = perform_backtests(stocks)
