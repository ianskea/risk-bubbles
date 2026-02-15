
import requests
import logging

def fetch_crypto_sentiment():
    """
    Fetches the latest Crypto Fear & Greed Index from Alternative.me.
    Returns: (index_value, sentiment_label)
    """
    url = "https://api.alternative.me/fng/"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data and 'data' in data:
            latest = data['data'][0]
            val = int(latest['value'])
            label = latest['value_classification']
            return val, label
    except Exception as e:
        logging.error(f"Error fetching Fear & Greed Index: {e}")
    
    return None, "Unknown"

def get_sentiment_advice(val, label):
    """
    Provides context based on the sentiment index.
    """
    if val is None:
        return "Sentiment data unavailable."
    
    if val <= 20:
        return "🔥 EXTREME FEAR: Historically a high-conviction value zone for accumulation."
    elif val <= 40:
        return "🟠 FEAR: Market is cautious; potential for further downside or consolidation."
    elif val >= 80:
        return "🚀 EXTREME GREED: Risk of correction is high. Expect volatility."
    elif val >= 60:
        return "🟢 GREED: Momentum is positive, but watch for overextension."
    else:
        return "⚪ NEUTRAL: No strong sentiment bias."

if __name__ == "__main__":
    val, label = fetch_crypto_sentiment()
    print(f"Fear & Greed Index: {val} ({label})")
    print(f"Advice: {get_sentiment_advice(val, label)}")
