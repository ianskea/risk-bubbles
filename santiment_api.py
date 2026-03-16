
import san
import os
from dotenv import load_dotenv
import pandas as pd
import logging
from datetime import datetime, timedelta

# Load Environment Variables
load_dotenv()
SANTIMENT_API_KEY = os.getenv("SANTIMENT_API_KEY")

if SANTIMENT_API_KEY:
    san.ApiConfig.api_key = SANTIMENT_API_KEY

def get_slug(ticker):
    """
    Maps common tickers to Santiment slugs.
    """
    ticker_clean = ticker.upper().replace("-USD", "").replace(".AX", "")
    mapping = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "ADA": "cardano",
        "BHP": "bhp-billiton",
        "RIO": "rio-tinto",
    }
    return mapping.get(ticker_clean, ticker_clean.lower())

def fetch_santiment_summary(ticker):
    """
    Fetches Santiment metrics for bottom/top assessment.
    Uses a 31-day lag to accommodate Free Tier API restrictions.
    """
    if not SANTIMENT_API_KEY:
        return {"error": "No Santiment API Key"}

    slug = get_slug(ticker)
    
    # metrics to fetch
    # mvrv_usd_365d: < -0.2 (Opp), > 0.5 (Danger)
    # sentiment_balance_total: < -1.5 (FUD/Bottom), > 2.0 (FOMO/Top)
    # whale_transaction_count_100k
    # mean_dollar_invested_age
    # social_volume_total
    
    metrics = [
        "mvrv_usd_365d",
        "sentiment_balance_total",
        "whale_transaction_count_100k_usd_to_inf",
        "mean_dollar_invested_age",
        "social_volume_total"
    ]
    
    # 31-day delay for free tier
    to_date = (datetime.utcnow() - timedelta(days=31)).strftime("%Y-%m-%dT%H:%M:%SZ")
    from_date = (datetime.utcnow() - timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    results = {"slug": slug, "as_of": to_date}
    
    try:
        for metric in metrics:
            try:
                # Use san.get for each metric to avoid get_many bugs
                df = san.get(f"{metric}/{slug}", from_date=from_date, to_date=to_date, interval="1d")
                if df is not None and not df.empty:
                    val = df.iloc[-1].iloc[0] # Get latest value
                    # Ensure it's a standard python type for easy serialization/reporting
                    if hasattr(val, "item"): val = val.item()
                    results[metric] = val
                else:
                    results[metric] = None
            except Exception as e:
                logging.warning(f"Error fetching {metric} for {slug}: {e}")
                results[metric] = None
        
        # Interpretation
        mvrv = results.get("mvrv_usd_365d")
        if mvrv is not None:
            results["mvrv_status"] = "Opportunity" if mvrv < -0.2 else "Bubble" if mvrv > 0.8 else "Neutral"
        
        sent = results.get("sentiment_balance_total")
        if sent is not None:
            results["sentiment_status"] = "Peak FUD (Bottom Signal)" if sent < -1.5 else "Extreme FOMO (Top Signal)" if sent > 2.5 else "Developing"

        return results
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    for t in ["BTC", "ETH"]:
        print(f"\n--- {t} (31d Lag) ---")
        print(fetch_santiment_summary(t))
