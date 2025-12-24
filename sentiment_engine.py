import requests
import json
import os
import yfinance as yf
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
# Load Environment Variables
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if DEEPSEEK_API_KEY:
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    except:
        client = None
else:
    client = None


# Sentiment Proxies if no news found for the primary ticker
# KIS Strategy: Map illiquid/quiet tickers to loud, highly-correlated majors
SENTIMENT_PROXIES = {
    # Equities
    "VGS.AX": "SPY",      # Global Shares -> S&P 500
    "VAS.AX": "^AXJO",    # Aus Shares -> ASX 200 Index
    "VAP.AX": "^AXJO",    # Property -> General Aus Sentiment
    "MQG.AX": "^AXJO",    # Macquarie -> General Aus Sentiment
    
    # Commodities
    "GC=F":   "GLD",      # Gold Futures -> SPDR Gold Shares (Very Liquid News)
    
    # Crypto (Usually loud, but good to have backups)
    "BTC-USD": "MSTR",    # Bitcoin -> MicroStrategy (often drives news)
    "ETH-USD": "COIN",    # Ethereum -> Coinbase (proxy for crypto ecosystem)
    "ADA-USD": "COIN"     # Cardano -> Coinbase
}

def search_tavily(query):
    """
    Uses Tavily API to find specifically 'news' context.
    Returns a list of titles.
    """
    if not TAVILY_API_KEY:
        return []

    print(f"  ... Searching Tavily: '{query}'")
    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "news", # or 'basic'
            "include_domains": [],
            "exclude_domains": [],
            "max_results": 5
        }
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        
        titles = []
        if 'results' in data:
            for r in data['results']:
                titles.append(r.get('title', ''))
        return titles
    except Exception as e:
        print(f"  Tavily Error: {e}")
        return []

def get_asset_sentiment(ticker):
    """
    Fetches recent news via yfinance and returns a sentiment score (0 to 1).
    0 = Extreme Fear / Bearish
    1 = Extreme Greed / Bullish
    0.5 = Neutral
    """
    if not client:
        print(f"  Sentiment API unavailable for {ticker}, defaulting to 0.5")
        return 0.5

    try:
        # Ticker might need adjustment for yfinance if it's not standard
        # But investment_planner passes valid YF tickers (e.g. BTC-USD, MQG.AX)
        asset = yf.Ticker(ticker)
        
        # Get news
        news = asset.news
        headlines = []
        if news:
            for n in news[:5]:
                # Handle different yfinance news structures
                if 'title' in n:
                     headlines.append(n['title'])
                elif 'content' in n and 'title' in n['content']:
                     headlines.append(n['content']['title'])
            
        # If no specific news, check proxy
        if not headlines and ticker in SENTIMENT_PROXIES:
            proxy = SENTIMENT_PROXIES[ticker]
            print(f"  No news for {ticker}, checking proxy {proxy}...")
            proxy_asset = yf.Ticker(proxy)
            proxy_news = proxy_asset.news
            if proxy_news:
                for n in proxy_news[:5]:
                    if 'title' in n:
                         headlines.append(n['title'])
                    elif 'content' in n and 'title' in n['content']:
                         headlines.append(n['content']['title'])
        
        # If STILL no news, check Tavily (Tier 3)
        if not headlines and TAVILY_API_KEY:
             date_str = datetime.now().strftime("%B %Y")
             query = f"{ticker} financial news {date_str}"
             tavily_titles = search_tavily(query)
             if tavily_titles:
                 headlines = tavily_titles

        if not headlines:
            print(f"  No news found for {ticker} (or proxy/Tavily), defaulting to 0.5")
            return 0.5
            
        headlines_text = "\n".join(headlines)
        
        if not headlines_text.strip():
             return 0.5

        prompt = (
            f"Analyze the following financial headlines for {ticker} and provide a single sentiment score "
            f"between 0.0 (Extreme Fear/Negative) and 1.0 (Extreme Greed/Positive). "
            f"Respond ONLY with the number (e.g., 0.65).\n\n"
            f"Headlines:\n{headlines_text}"
        )
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=10
        )
        
        content = response.choices[0].message.content.strip()
        
        # Clean up response to get just the float
        # Sometimes models might say "The score is 0.5", so we regex or try parse
        import re
        match = re.search(r"(\d+\.?\d*)", content)
        if match:
            score = float(match.group(1))
            # Clamp between 0 and 1
            return max(0.0, min(1.0, score))
        else:
            return 0.5

    except Exception as e:
        print(f"  Sentiment error for {ticker}: {e}")
        return 0.5

if __name__ == "__main__":
    # Test run
    test_ticker = "BTC-USD"
    print(f"Testing sentiment for {test_ticker}...")
    score = get_asset_sentiment(test_ticker)
    print(f"Score: {score}")
