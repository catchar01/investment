import os
import django
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sentiments_stock_data import get_stock_data
from collections import defaultdict
from datetime import datetime
import numpy as np

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'take2.settings')

from newsapp.models import NewsArticle

def prepare_data_with_sentiments(stock_symbol, forecast_out=1, split_date=None):
    if split_date is None:
        split_date = pd.Timestamp(datetime.now()).tz_localize('UTC')
    elif isinstance(split_date, datetime) and split_date.tzinfo is None:
        split_date = pd.Timestamp(split_date).tz_localize('UTC')

    stock_data = get_stock_data(stock_symbol) ##Load historical data for symbol
    articles = NewsArticle.objects.all() ##Fetch all news articles
    daily_scores_by_stock = defaultdict(lambda: defaultdict(list)) ##Define nested dict to store sent scores, grouped by stock symbol and date.
    
    for article in articles: ##Iterates over each article. Gets pub date and appends sent score to right date and symbol.
        date_str = article.published_at.date().strftime('%Y-%m-%d')
        daily_scores_by_stock[stock_symbol][date_str].append(article.sentiment_scores)
    
    daily_avg_scores_by_stock = {} ##gets average sentiment score for each date by averaging all sentiment scores collected on that date.
    for stock, dates in daily_scores_by_stock.items():
        daily_avg_scores_by_stock[stock] = {
            date: sum(scores) / len(scores) for date, scores in dates.items() if scores
        }

    articles = NewsArticle.objects.filter(published_at__lte=split_date) ##Filters articles published on or before the split date.
    if stock_symbol in daily_avg_scores_by_stock: ##Creates a DataFrame from the average sentiment scores and merges it with the stock data on the date index.
        sentiment_scores = pd.DataFrame(list(daily_avg_scores_by_stock[stock_symbol].items()), columns=['Date', 'Sentiment'])
        sentiment_scores['Date'] = pd.to_datetime(sentiment_scores['Date'])
        sentiment_scores.set_index('Date', inplace=True)
        sentiment_scores.index = sentiment_scores.index.tz_localize('UTC', ambiguous='infer')
        sentiment_scores = sentiment_scores[sentiment_scores.index <= split_date]  ##So sentiment scores do not include future data

    stock_data.index = pd.to_datetime(stock_data.index).tz_localize('UTC', ambiguous='infer')

    combined_data = pd.merge(stock_data, sentiment_scores, how='left', left_index=True, right_index=True)
    combined_data['Sentiment'] = combined_data['Sentiment'].fillna(0)
    scaling_factor = 10
    combined_data['Sentiment'] = combined_data['Sentiment'] * scaling_factor ##Scales sentiment scores to have a comparable impact to other numerical features in the dataset.
    combined_data['Prediction'] = combined_data['Close'].shift(-forecast_out) ##Creates a target variable column by shifting the close price backward by the forecast_out days.

    train = combined_data[combined_data.index < split_date]

    return train

def predict_stock_prices_with_sentiment(stock_symbol, forecast_out=1, split_date=None):
    train = prepare_data_with_sentiments(stock_symbol, forecast_out, split_date)

    if train.empty:
        print("Training data is empty. Exiting prediction.")
        return None

    features = ['Volume', 'Open', 'High', 'Low', 'Sentiment'] #specifies features for training
    X_train = train[features] ##extract feature data x from training set
    y_train = train['Close'].shift(-forecast_out) ##extract target variable y from training set

    mask = y_train.notna() ##only rows with non null target variables used
    X_train = X_train[mask] ##fill in missing vals in features with mean of each column
    y_train = y_train[mask]

    X_train.fillna(X_train.mean(), inplace=True)

    #Feature scaling
    scaler = StandardScaler() ##Scales the features to normalise the data, improving the training process.
    X_train_scaled = scaler.fit_transform(X_train) ##This method first calculates the mean and standard deviation of each feature in the dataset X_train. 
    #It then scales the features by subtracting the mean and dividing by the standard deviation. This results in features with a mean of 0 and a standard deviation of 1.

    #Model training
    model = LinearRegression()
    model.fit(X_train_scaled, y_train) ##Trains the linear regression model using the scaled features and target variable.
    #fit(): This method fits the linear model to the scaled training data (X_train_scaled) and the target data (y_train). 
    ##It calculates the optimal weights (coefficients) for all the input features that minimize the residual sum of squares between the observed and predicted values in the dataset.

    #Prepare last days data for prediction
    X_last_days = train.tail(forecast_out)[features] ##Prepares the feature data for the last few days specified by forecast_out.
    X_last_days.fillna(X_last_days.mean(), inplace=True)
    X_last_days_scaled = scaler.transform(X_last_days)

    predictions = model.predict(X_last_days_scaled) ##Predicts future stock prices using the trained model.
    ##This method uses the trained linear regression model to make predictions on new, scaled data (X_last_days_scaled).
    predictions = np.round(predictions, 2)

    return predictions

if __name__ == '__main__':
    predict_stock_prices_with_sentiment('MSFT', forecast_out=1)