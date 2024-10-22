import os
import django

if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'take2.settings')
    django.setup()

import finnhub
import requests
from bs4 import BeautifulSoup
from sent_scores import sent_score
from datetime import datetime, timedelta
from newsapp.models import NewsArticle
from django.utils import timezone

#flexible content finder
def find_main_content(soup):
    for selector in [
        'article',
        ('div', {'class': 'article-body'}),
        ('div', {'class': 'post-content'}),
        'main',
        ('div', {'role': 'main'}),
    ]:
        if isinstance(selector, tuple):
            content = soup.find(*selector)
        else:
            content = soup.find(selector)
        if content:
            return content
    return None

FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)

stocks = list(NewsArticle.objects.order_by('stock_name').values_list('stock_name', flat=True).distinct())

end_date = datetime.now().date()
start_date = end_date - timedelta(days=1)

#fetch and save articles
def fetch_and_save_articles():
    for day in (start_date + timedelta(n) for n in range((end_date - start_date).days + 1)):
        for stock in stocks:
            news_items = finnhub_client.company_news(stock, _from=day.strftime('%Y-%m-%d'), to=(day + timedelta(days=1)).strftime('%Y-%m-%d'))
            
            for item in news_items:
                title = item.get('headline')
                unix_timestamp = item.get('datetime')
                url = item.get('url')

                if not title or not unix_timestamp or not url:
                    continue #Skip if essential information missing

                #Convert timestamp to datetime
                published_at = timezone.make_aware(datetime.fromtimestamp(unix_timestamp))

                #Check duplicates
                if NewsArticle.objects.filter(stock_name=stock, title=title, published_at=published_at).exists():
                    print("exists"+str(day))
                    continue

                response = requests.get(url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    main_content = find_main_content(soup)
                    if main_content:
                        paragraphs = main_content.find_all('p')
                        content = ' '.join(paragraph.text.strip() for paragraph in paragraphs)
                        sentiment_score, cleaned_content = sent_score(content) #assign sent score
                        if sentiment_score is None:
                            continue

                        #Create and save article
                        NewsArticle.objects.create(
                            stock_name=stock,
                            title=title,
                            published_at=published_at,
                            url=url,
                            content=cleaned_content,
                            sentiment_scores=sentiment_score
                        )
                        print(f"Saved article for {stock} on {day}")

fetch_and_save_articles()