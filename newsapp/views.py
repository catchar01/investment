import json
import os
import re
import requests
import yfinance as yf
from datetime import datetime, timedelta
from wordcloud import WordCloud
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Avg
from django.db.models.functions import TruncDay
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import NewsArticle, FavouriteStock
from sentiments_stock_data import get_dj_data, get_vix_data, get_sp500_data, get_sp500_volume, get_stock_sectors, get_stock_data
from stock_prediction import predict_stock_prices_with_sentiment
from django.contrib.auth.forms import UserChangeForm, PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages

def generate_wordcloud():
    #Aggregate text data
    all_content = " ".join(article.content for article in NewsArticle.objects.all() if article.content)
    all_content = re.sub(r"[^\w\s]", '', all_content) #remove apostrophes from tokenizing, for wordcloud

    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(all_content)

    static_dir = os.path.join(settings.BASE_DIR, 'newsapp', 'static')
    os.makedirs(static_dir, exist_ok=True)

    wordcloud_image_path = os.path.join(static_dir, 'wordcloud.png')

    wordcloud.to_file(wordcloud_image_path)

def index(request):
    wordcloud_image_url = generate_wordcloud()
    
    dow_jones_data = get_dj_data()
    dow_jones_dates = dow_jones_data.index.strftime('%Y-%m-%d').tolist()
    dow_jones_values = dow_jones_data.tolist()

    ##average sentiment past week
    one_week_ago = datetime.now() - timedelta(days=7)
    average_sentiment = NewsArticle.objects.filter(
        published_at__gte=one_week_ago
    ).aggregate(
        average_sentiment=Avg('sentiment_scores')
    )['average_sentiment'] or 0
    sentiment_type = 'Positive' if average_sentiment > 0 else 'Negative' if average_sentiment < 0 else 'Neutral'

    context = {
        'wordcloud_image_url': wordcloud_image_url,
        'DJDates': mark_safe(json.dumps(dow_jones_dates)),
        'DJVals': mark_safe(json.dumps(dow_jones_values)),
        'avg_sent_pw': average_sentiment,
        'sent_cat_pw': sentiment_type,
    }

    #favourite stocks on homepage
    if request.user.is_authenticated:
        favourite_stocks_query = FavouriteStock.objects.filter(user=request.user)
        favourite_stocks = [stock.stock_name for stock in favourite_stocks_query]

        stock_info = []
        for stock_name in favourite_stocks:
            ticker = yf.Ticker(stock_name)
            ticker_info = ticker.info
            current_price = ticker_info.get('currentPrice')

            sentiment_scores = NewsArticle.objects.filter(
                stock_name=stock_name,
                published_at__gte=one_week_ago
            ).aggregate(average_sentiment=Avg('sentiment_scores'))
            average_sentiment = sentiment_scores['average_sentiment'] or 0
            sent_fave = 'Positive' if average_sentiment > 0 else 'Negative' if average_sentiment < 0 else 'Neutral'
            
            stock_info.append({
                'stock_name': stock_name,
                'price': current_price,
                'sent_fave': sent_fave,
            })

        context['fave_stocks_info'] = stock_info
    else:
        context['fave_stocks_info'] = []

    return render(request, 'index.html', context)

def stocks(request):
    stock_names = NewsArticle.objects.values_list('stock_name', flat=True).distinct()

    query = request.GET.get('query', '')

    if query:
        stock_names = NewsArticle.objects.filter(stock_name__icontains=query).values_list('stock_name', flat=True).distinct()
    else:
        stock_names = NewsArticle.objects.values_list('stock_name', flat=True).distinct()

    if request.user.is_authenticated:
        favourite_stocks = FavouriteStock.objects.filter(user=request.user).values_list('stock_name', flat=True)
        favourite_stocks = sorted(favourite_stocks)
    else:
        favourite_stocks = []
    
    stock_names = sorted(stock_names)
    return render(request, 'stocks.html', {'stock_names': stock_names, 'favourite_stocks': favourite_stocks, 'api_key': settings.FINNHUB_API_KEY})

def stock_articles(request):
    stock_name = request.GET.get('stock_name')
    #newest articles first
    articles = list(NewsArticle.objects.filter(stock_name=stock_name).order_by('-published_at').values('title', 'url', 'published_at','sentiment_scores'))
    return JsonResponse(articles, safe=False)

###log in stuff
def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
@require_POST
@csrf_exempt  #Only for testing. Remove and handle CSRF properly
def toggle_favourite(request):
    try:
        data = json.loads(request.body)
        stock_name = data['stock_name']
    except (KeyError, json.JSONDecodeError) as e:
        return HttpResponseBadRequest('Invalid data')

    user = request.user

    favourite, created = FavouriteStock.objects.get_or_create(user=user, stock_name=stock_name)
    if not created:
        favourite.delete()
        is_favourite = False
    else:
        is_favourite = True

    return JsonResponse({'success': True, 'is_favourite': is_favourite})

@login_required
def profile(request):
    if request.method == 'POST' and 'email' in request.POST:
        user_form = UserChangeForm(request.POST, instance=request.user)
        if user_form.is_valid():
            user_form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('profile')
    else:
        user_form = UserChangeForm(instance=request.user)
    return render(request, 'profile.html', {'user_form': user_form})

@login_required
def is_favourite(request):
    stock_name = request.GET.get('stock_name')
    is_favourite = FavouriteStock.objects.filter(user=request.user, stock_name=stock_name).exists()
    return JsonResponse({'is_favourite': is_favourite})

def stock_predictions(request, stock_symbol):
    predictions= predict_stock_prices_with_sentiment(stock_symbol, forecast_out=1)
    predictions_list = predictions.tolist()
    return JsonResponse({'predictions': predictions_list})

def stock_data_api(request, stock_symbol):
    if not stock_symbol or stock_symbol.upper() == 'UNDEFINED':
        return HttpResponseBadRequest('Invalid stock symbol')

    try:
        data = get_stock_data(stock_symbol)
        formatted_data = data.reset_index().to_dict('records')
        return JsonResponse(formatted_data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
@login_required
def profile(request):
    if request.method == 'POST':
        password_form = PasswordChangeForm(data=request.POST, user=request.user)
    else:
        password_form = PasswordChangeForm(user=request.user)
    
    context = {'password_form': password_form}
    return render(request, 'profile.html', context)

def sentiments_view(request):
    start_date = datetime.now() - timedelta(days=14)
    
    #Agg avg sentiment scores by day
    scores = NewsArticle.objects.exclude(
        sentiment_scores=0
    ).filter(
        sentiment_scores__isnull=False,
        published_at__gte=start_date
    ).annotate(
        day=TruncDay('published_at')
    ).values('day').annotate(
        average_score=Avg('sentiment_scores')
    ).order_by('day')
    
    full_scores = {day.strftime("%Y-%m-%d"): 0 for day in [start_date + timedelta(days=x) for x in range((datetime.now() - start_date).days + 1)]}
    for score in scores:
        if score['average_score'] is not None:
            full_scores[score['day'].strftime("%Y-%m-%d")] = score['average_score']

    vix_data = get_vix_data()
    vix_dates = vix_data.index.strftime('%Y-%m-%d').tolist()
    vix_values = vix_data['Close'].tolist()

    sp500_volume_data = get_sp500_volume()
    volume_dates = sp500_volume_data.index.strftime('%Y-%m-%d').tolist()
    volume_values = sp500_volume_data.tolist()
    sp500_data = get_sp500_data()

    ##############top and bottom moving stocks
    #Calculate avg sent score for each stock and day
    scores = NewsArticle.objects.filter(
        published_at__gte=start_date
    ).annotate(
        day=TruncDay('published_at')
    ).values('stock_name', 'day').annotate(
        average_score=Avg('sentiment_scores')
    ).order_by('stock_name', 'day')

    stock_changes = {}
    for score in scores:
        if score['stock_name'] not in stock_changes:
            stock_changes[score['stock_name']] = {'first': score['average_score'], 'last': score['average_score']}
        else:
            stock_changes[score['stock_name']]['last'] = score['average_score']

    stock_sentiment_changes = {stock: data['last'] - data['first'] for stock, data in stock_changes.items()}
    #sort by change in sentiment score
    top_stocks = sorted(stock_sentiment_changes.items(), key=lambda x: x[1], reverse=True)[:5]
    bot_stocks = sorted(stock_sentiment_changes.items(), key=lambda x: x[1])[:5]

    top_topics = generate_top_sentiment_topics()

    stock_names = list(NewsArticle.objects.values_list('stock_name', flat=True).distinct())

    #get sector of stocks
    stock_sectors = get_stock_sectors(stock_names)
    sector_sentiments = {sector: [] for sector in set(stock_sectors.values())}

    #sentiment scores by sector
    for article in NewsArticle.objects.filter(sentiment_scores__isnull=False):
        sector = stock_sectors.get(article.stock_name, 'Unknown')
        sector_sentiments[sector].append(article.sentiment_scores)

    sector_average_sentiments = {
        sector: sum(sentiments) / len(sentiments) if sentiments else 0
        for sector, sentiments in sector_sentiments.items()
    }

    sector_daily_sentiments = {}
    articles = NewsArticle.objects.exclude(
        sentiment_scores=0
    ).filter(
        sentiment_scores__isnull=False,
        published_at__gte=start_date
    ).annotate(
        day=TruncDay('published_at')
    )

    for article in articles:
        sector = stock_sectors.get(article.stock_name, 'Unknown')
        day = article.day.strftime("%Y-%m-%d")
        if sector not in sector_daily_sentiments:
            sector_daily_sentiments[sector] = {}
        if day not in sector_daily_sentiments[sector]:
            sector_daily_sentiments[sector][day] = [article.sentiment_scores]
        else:
            sector_daily_sentiments[sector][day].append(article.sentiment_scores)

    #average daily sentiment for each sector
    sector_daily_average_sentiments = {
        sector: {day: sum(scores) / len(scores) for day, scores in days.items()}
        for sector, days in sector_daily_sentiments.items()
    }

    #check each day is represented
    for sector in sector_daily_average_sentiments:
        for day in [start_date + timedelta(days=x) for x in range((datetime.now() - start_date).days + 1)]:
            day_str = day.strftime("%Y-%m-%d")
            if day_str not in sector_daily_average_sentiments[sector]:
                sector_daily_average_sentiments[sector][day_str] = 0

    for sector in sector_daily_average_sentiments:
        sector_daily_average_sentiments[sector] = dict(sorted(sector_daily_average_sentiments[sector].items()))

    return render(request, 'sentiments.html', {
        'sent_dates': list(full_scores.keys()),
        'sent_scores': list(full_scores.values()),
        'vix_dates': vix_dates,
        'vix_values': vix_values,
        'volume_dates': volume_dates,
        'volume_values': volume_values,
        'sp500_dates': mark_safe(json.dumps(sp500_data.index.strftime('%Y-%m-%d').tolist())),
        'sp500_values': mark_safe(json.dumps(sp500_data.tolist())),
        'top_stocks': top_stocks,
        'bot_stocks': bot_stocks,
        'top_topics': top_topics,
        'sect_sent_bar': json.dumps(sector_average_sentiments, cls=DjangoJSONEncoder),
        'sect_sent_line': json.dumps(sector_daily_average_sentiments, cls=DjangoJSONEncoder),
    })

def get_sentiment_scores(request, stock_symbol):
    two_weeks_ago = datetime.now() - timedelta(days=14)
    scores = NewsArticle.objects.filter(
        stock_name=stock_symbol, 
        published_at__gte=two_weeks_ago
    ).annotate(
        day=TruncDay('published_at')
    ).values('day').annotate(
        average_score=Avg('sentiment_scores')
    ).order_by('day')

    full_scores = {day.strftime("%Y-%m-%d"): 0 for day in [two_weeks_ago + timedelta(days=x) for x in range(15)]}
    for score in scores:
        full_scores[score['day'].strftime("%Y-%m-%d")] = score['average_score'] or 0

    return JsonResponse({
        'dates': list(full_scores.keys()),
        'scores': list(full_scores.values()),
    })

def generate_top_sentiment_topics():
    word_sentiments = {}
    
    for article in NewsArticle.objects.all():
        if article.content and article.sentiment_scores:
            clean_content = re.sub(r"[^\w\s]", '', article.content).lower()
            sentiment = 'positive' if article.sentiment_scores > 0 else 'negative'
            
            for word in clean_content.split():
                if word not in word_sentiments:
                    word_sentiments[word] = {'positive': 0, 'negative': 0, 'count': 0}
                word_sentiments[word][sentiment] += 1
                word_sentiments[word]['count'] += 1
    
    most_frequent_topics = sorted(word_sentiments.items(), key=lambda x: x[1]['count'], reverse=True)[:10]
    
    top_topics_sentiment = {
        word: ('positive' if data['positive'] > data['negative'] else 'negative')
        for word, data in most_frequent_topics
    }
    
    return top_topics_sentiment

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(data=request.POST, user=request.user)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password was successfully updated!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the error.')
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'change_password.html', {'form': form})