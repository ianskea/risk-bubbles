import requests
import pandas as pd
import numpy as np

def fetch_coinmetrics_onchain(ticker="btc"):
    """
    Fetches free on-chain data from Coin Metrics Community API.
    Handles 'BTC-USD', 'ETH-USD' etc.
    """
    ticker_upper = ticker.upper()
    if ticker_upper == "BTC-USD" or ticker_upper == "BTC":
        asset = "btc"
    elif ticker_upper == "ETH-USD" or ticker_upper == "ETH":
        asset = "eth"
    else:
        return None
        
    metrics = "PriceUSD,CapRealUSD,SplyCur,CapMVRVCur"
    url = f"https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    
    params = {
        "assets": asset,
        "metrics": metrics,
        "frequency": "1d",
        "page_size": 10000 
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        records = []
        for row in data.get('data', []):
            try:
                records.append({
                    "date": pd.to_datetime(row['time']),
                    "PriceUSD": float(row.get('PriceUSD', 0)),
                    "RealizedCapUSD": float(row.get('CapRealUSD', 0)),
                    "Supply": float(row.get('SplyCur', 0)),
                    "MVRV": float(row.get('CapMVRVCur', 0))
                })
            except (ValueError, TypeError):
                # Skip rows with missing or malformed data for required fields
                continue
            
        if not records:
            return None
            
        df = pd.DataFrame(records).set_index("date")
        
        # Calculate Realized Price
        # Handle zero supply to avoid division by zero
        df['RealizedPrice'] = np.where(df['Supply'] > 0, df['RealizedCapUSD'] / df['Supply'], 0)
        
        return df
    except Exception as e:
        print(f"Error fetching Coin Metrics data for {ticker}: {e}")
        return None

if __name__ == "__main__":
    df = fetch_coinmetrics_onchain("BTC-USD")
    if df is not None:
        latest = df.iloc[-1]
        print(f"BTC Price: ${latest['PriceUSD']:,.2f}")
        print(f"BTC Realized Price: ${latest['RealizedPrice']:,.2f}")
        print(f"MVRV Ratio: {latest['MVRV']:.2f}")
