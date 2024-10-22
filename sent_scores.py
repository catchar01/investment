import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'take2.settings')
import csv
from nltk.corpus import stopwords
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import CountVectorizer

import re
import nltk
nltk.download('stopwords')
nltk.download('punkt')

current_script_path = os.path.abspath(__file__)
current_script_dir = os.path.dirname(current_script_path)
CSV_FILE_PATH = os.path.join(current_script_dir, 'Loughran-McDonald_MasterDictionary_1993-2023.csv')

stop_words = set(stopwords.words('english'))
#custom list of financial stopwords
finance_stop_words = {'company', 'companies', 'said', 'us', 'financial', 'business', 'year', 'one', 'stock'}
stop_words.update(finance_stop_words)

#removing stopwords that I want to analyse
to_keep = {'increase', 'decrease', 'loss', 'gain'}
stop_words = stop_words - to_keep

def load_lm(file_path):
    sentiment_dict = {}
    with open(file_path, mode='r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            word = row["Word"].upper()
            sentiment_dict[word] = {
                "Negative": 1 if int(row["Negative"]) > 0 else 0,
                "Positive": 1 if int(row["Positive"]) > 0 else 0,
                "Uncertainty": 1 if int(row["Uncertainty"]) > 0 else 0,
                "Litigious": 1 if int(row["Litigious"]) > 0 else 0,
                "StrongModal": 1 if int(row["Strong_Modal"]) > 0 else 0,
                "WeakModal": 1 if int(row["Weak_Modal"]) > 0 else 0,
                "Constraining": 1 if int(row["Constraining"]) > 0 else 0,
            }
    return sentiment_dict

def clean_text(text):
    text = text.lower()
    text = re.sub(r'<.*?>', '', text)
    text = re.sub(r'http\S+|www\.\S+', '', text)
    text = re.sub(r'[\d]', '', text)  #Remove numbers
    text = re.sub(r"[^\w\s]", '', text)  #Removes all punctuation 
    text = re.sub(r'\s+', ' ', text).strip()
    text = ' '.join([word for word in text.split() if word not in stop_words])
    return text

sentiment_dict = load_lm(CSV_FILE_PATH)
analyser = SentimentIntensityAnalyzer()

def sent_score(text):
    cleaned_content = clean_text(text).upper()

    if not cleaned_content:
        return None, cleaned_content
    
    weights = {
        "Negative": -1,
        "Positive": 1,
        "Uncertainty": -0.3,
        "Litigious": -0.2,
        "StrongModal": 0.4,
        "WeakModal": 0.1,
        "Constraining": -0.3
    }
    
    words = cleaned_content.split()
    vectorizer = CountVectorizer(ngram_range=(1, 2), stop_words='english')
    bigrams = vectorizer.get_feature_names_out()
    all_features = words + list(bigrams)

    vader_score = analyser.polarity_scores(text)['compound']
    lm_score_adjustments = 0
    for feature in all_features:
        if feature in sentiment_dict:
            for category, presence in sentiment_dict[feature].items():
                if presence:
                    lm_score_adjustments += weights[category]

    max_positive = max(abs(weight) for weight in weights.values() if weight > 0)
    max_negative = max(abs(weight) for weight in weights.values() if weight < 0)
    max_lm_adjustment = max(max_positive, max_negative) * len(all_features)
    normalized_lm_score = lm_score_adjustments / max_lm_adjustment

    combined_score = 0.5 * vader_score + 0.5 * normalized_lm_score
    return combined_score, cleaned_content
