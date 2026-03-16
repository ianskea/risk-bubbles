
import san
import os
from dotenv import load_dotenv

load_dotenv()
SANTIMENT_API_KEY = os.getenv("SANTIMENT_API_KEY")
if SANTIMENT_API_KEY:
    san.ApiConfig.api_key = SANTIMENT_API_KEY

try:
    print("Testing san.get('mvrv_usd_365d', slug='bitcoin')...")
    # Free tier: Data is roughly 30 days delayed. 
    # Try fetching 40 days ago to 31 days ago.
    df = san.get("mvrv_usd_365d/bitcoin", from_date="utc_now-45d", to_date="utc_now-31d", interval="1d")
    print(df.tail(1))
except Exception as e:
    print(f"san.get failed: {e}")

try:
    print("\nTesting san.get_many(['mvrv_usd_365d'], slug='bitcoin')...")
    df = san.get_many(["mvrv_usd_365d"], slug="bitcoin", from_date="utc_now-7d", to_date="utc_now", interval="1d")
    print(df.tail(1))
except Exception as e:
    print(f"san.get_many failed: {e}")
