
from market_health import fetch_macro_data
import pandas as pd

print("Testing fetch_macro_data()...")
df = fetch_macro_data()
print("Result DataFrame:")
print(df)
if df.empty:
    print("DataFrame is empty.")
    # Check yfinance download manually to see structure
    import yfinance as yf
    tickers = ["BTC-USD", "^GSPC", "GC=F"]
    print("Raw yfinance download structure:")
    data = yf.download(tickers, period="1y", progress=False, auto_adjust=True)
    print(data.columns)
    print(data.head())
