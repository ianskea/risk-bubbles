
import yfinance as yf
import pandas as pd
import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_breadth_data():
    """
    Fetches daily close data for a basket of top historical crypto assets 
    to calculate Market Breadth (Advance-Decline Line).
    Using a 'Blue Chip' basket that has decent history to avoid new-coin bias.
    """
    # Top assets with likely sufficient history for a robust AD line
    tickers = [
        "BTC-USD", "ETH-USD", "BNB-USD", "XRP-USD", "ADA-USD", "SOL-USD", "DOGE-USD",
        "TRX-USD", "DOT-USD", "LTC-USD", "BCH-USD", "LINK-USD", "XLM-USD", "UNI7083-USD",
        "AVAX-USD", "ATOM-USD", "XMR-USD", "FIL-USD", "HBAR-USD", "VET-USD"
    ]
    
    print("Fetching data for Market Breadth (Top 20 Assets)...")
    try:
        data = yf.download(tickers, period="2y", progress=False, group_by='ticker', auto_adjust=True)
        # Extract just Close prices for all
        close_df = pd.DataFrame()
        
        # Handle yfinance MultiIndex or Flat structure
        if isinstance(data.columns, pd.MultiIndex):
            for t in tickers:
                try:
                    # yfinance often returns MultiIndex (Ticker, PriceType)
                    if t in data:
                        close_df[t] = data[t]['Close']
                    elif (t, 'Close') in data.columns:
                        close_df[t] = data[(t, 'Close')]
                except KeyError:
                    continue
        else:
            # Fallback if structure is different
            pass # TODO: Robust handling for flat structure if needed

        return close_df
    except Exception as e:
        logging.error(f"Error fetching breadth data: {e}")
        return pd.DataFrame()

def calculate_market_breadth(close_df):
    """
    Calculates the Advance-Decline Line.
    Daily Advances: Count of assets with Close > Prev Close
    Daily Declines: Count of assets with Close < Prev Close
    Net: Advances - Declines
    AD Line: Cumulative Sum of Net
    """
    if close_df.empty:
        return 0, "No Data"

    # Calculate daily returns
    returns = close_df.pct_change().dropna()
    
    # +1 for Advance, -1 for Decline (0 for flat)
    advances = (returns > 0).sum(axis=1)
    declines = (returns < 0).sum(axis=1)
    
    net_daily = advances - declines
    ad_line = net_daily.cumsum()
    
    # Analysis: Check trend of AD Line over last 30 days
    recent_trend = ad_line.diff().tail(30).sum()
    
    current_val = ad_line.iloc[-1]
    
    # Interpretation
    status = "NEUTRAL"
    if recent_trend > 50: status = "EXPANDING (Healthy)"
    elif recent_trend < -50: status = "CONTRACTING (Weakness)"
    
    return current_val, status

def fetch_macro_data():
    """
    Fetches BTC, S&P 500, and Gold for correlation analysis.
    """
    tickers = ["BTC-USD", "^GSPC", "GC=F"]
    print("Fetching Macro Data (BTC, SPX, Gold)...")
    try:
        data = yf.download(tickers, period="1y", progress=False, auto_adjust=True)
        
        df = pd.DataFrame()
        # Flatten structure
        # yfinance download with multiple tickers often returns (Price, Ticker) MultiIndex
        # e.g. ('Close', 'BTC-USD'), ('Close', '^GSPC')
        
        if isinstance(data.columns, pd.MultiIndex):
            # Check levels. Usually level 0 is Price, level 1 is Ticker
            # We want 'Close' for each ticker
            try:
                # Access cross-section if possible, or just standard key access
                # Key access data['Close']['BTC-USD'] works if level 0 is Price
                if 'Close' in data.columns.get_level_values(0):
                    closes = data['Close']
                    if 'BTC-USD' in closes.columns: df['BTC'] = closes['BTC-USD']
                    if '^GSPC' in closes.columns:   df['SPX'] = closes['^GSPC']
                    if 'GC=F' in closes.columns:    df['GOLD'] = closes['GC=F']
                else:
                    # Fallback: iterate
                    for col in data.columns:
                        price_type, ticker = col
                        if price_type == 'Close':
                            if ticker == 'BTC-USD': df['BTC'] = data[col]
                            elif ticker == '^GSPC': df['SPX'] = data[col]
                            elif ticker == 'GC=F':  df['GOLD'] = data[col]
            except Exception as e:
                logging.error(f"MultiIndex parsing error: {e}")
        else:
             # Flat index (rare for multi-request)
             pass 

        return df.dropna()
        
        return df.dropna()
    except Exception as e:
        logging.error(f"Error fetching macro data: {e}")
        return pd.DataFrame()

def analyze_correlations(df):
    """
    Calculates 90-day rolling correlation.
    Returns the latest correlation coefficients.
    """
    if df.empty or 'BTC' not in df.columns:
        return {}
    
    # 90-Day Rolling Correlation
    window = 90
    corr_spx = df['BTC'].rolling(window).corr(df['SPX'])
    corr_gold = df['BTC'].rolling(window).corr(df['GOLD'])
    
    latest_spx = corr_spx.iloc[-1]
    latest_gold = corr_gold.iloc[-1]
    
    return {
        "BTC_SPX_90D": latest_spx,
        "BTC_GOLD_90D": latest_gold
    }

def analyze_volatility_compression(btc_series):
    """
    Calculates 180-Day Volatility and checks for compression (low percentile).
    """
    if btc_series is None or len(btc_series) < 180:
        return None, "Insufficient Data"
    
    # Annualized Volatility (Rolling 180D)
    # Vol = Stdev of Log Returns * sqrt(365)
    log_returns = np.log(btc_series / btc_series.shift(1))
    rolling_vol = log_returns.rolling(window=180).std() * np.sqrt(365)
    
    current_vol = rolling_vol.iloc[-1]
    
    # Check percentile over last 2 years (or full series length)
    # We used 1y data in fetch_macro, maybe need longer for robust percentile?
    # Enhanced Main usually fetches longer history for BTC validation.
    # We'll trust the trend.
    
    # Simple compression threshold: < 40% (0.4) is usually low for BTC
    # Or compare to its own history in this series
    min_vol = rolling_vol.min()
    max_vol = rolling_vol.max()
    
    # Percentile rank of current vol
    rank = (rolling_vol < current_vol).mean()
    
    status = "NORMAL"
    if rank < 0.10: status = "EXTREME COMPRESSION (Explosive Move Imminent)"
    elif rank < 0.25: status = "COMPRESSED (Watch for Breakout)"
    elif rank > 0.80: status = "ELEVATED (High Risk)"
    
    return current_vol, status

def get_market_health_summary():
    """
    Master function to run all checks and return the formatted Regime Card.
    """
    # 1. Fetch Data
    breadth_df = fetch_breadth_data()
    breadth_val, breadth_status = calculate_market_breadth(breadth_df)
    
    macro_df = fetch_macro_data()
    corrs = analyze_correlations(macro_df) if not macro_df.empty else {}
    btc_spx = corrs.get('BTC_SPX_90D', 0)
    btc_gold = corrs.get('BTC_GOLD_90D', 0)
    
    btc_series = macro_df['BTC'] if not macro_df.empty and 'BTC' in macro_df else None
    vol_val, vol_status = analyze_volatility_compression(btc_series)
    if vol_val is None: vol_val = 0

    # --- REGIME CARD GENERATION ---
    
    # 1. Header Logic
    regime_label = "Mixed"
    if abs(btc_spx) < 0.3 and abs(btc_gold) < 0.3:
        regime_label = "Crypto-Native"
    elif btc_gold > 0.5:
        regime_label = "Macro-Driven (Defensive)"
    elif btc_spx > 0.5:
        regime_label = "Risk-On (Liquidity)"
        
    is_narrow = "Narrow" in str(breadth_status) or "Weak" in str(breadth_status) or "CONTRACTING" in str(breadth_status)
    if is_narrow:
        if "Risk-On" in regime_label:
            regime_label = "Mixed (Narrow Liquidity)"
        elif regime_label == "Crypto-Native":
            regime_label = "Crypto-Native (Narrow)"
            
    confidence = "Med"
    if breadth_df.empty or macro_df.empty: confidence = "Low (Data Missing)"
    
    stance = "Hold Risk"
    if "COMPRESSION" in str(vol_status):
        stance = "Wait for Breakout"
    elif is_narrow and "Rise" in str(breadth_status):
        stance = "Scale / Risk-controlled"
    elif is_narrow:
        stance = "De-risk / Consolidation"

    header = f"Mode: ⚠️ {regime_label} | Confidence: {confidence} | Stance: {stance}"

    # 2. Breadth Block
    b_badge = "🟡"
    if "EXPANDING" in str(breadth_status): b_badge = "🟢"
    elif is_narrow: b_badge = "🟠"
    
    b_meaning = "Participation is average."
    if is_narrow: b_meaning = "rally held up by fewer names → fragile risk-on"
    elif "EXPANDING" in str(breadth_status): b_meaning = "Broad participation confirms trend strength"
    
    b_do = "Monitor specific sectors."
    if is_narrow: b_do = "avoid broad risk adds; prefer highest-conviction only"
    elif "EXPANDING" in str(breadth_status): b_do = "Scale into strength; look for laggards"
    
    breadth_block = (
        f"Breadth: {b_badge} {str(breadth_status).split('(')[0].strip()}\n"
        f"Meaning: {b_meaning}\n"
        f"Do: {b_do}"
    )

    # 3. Correlations Block
    c_badge = "🟣" 
    c_desc = "Crypto-Native (Decoupled)"
    c_meaning = "crypto driven by crypto flows; macro hedges unreliable"
    c_do = "follow crypto signals; don't assume stock moves predict BTC"
    
    def get_corr_text(val):
        desc = "neutral"
        if abs(val) > 0.5: desc = "strong"
        elif abs(val) > 0.2: desc = "moderate"
        else: desc = "weak"
        
        direction = "positive" if val > 0 else "negative"
        return f"{val:.2f} ({desc} {direction})"

    if btc_spx > 0.5:
        c_badge = "🟢"
        c_desc = "Risk-On Proxy"
        c_meaning = "BTC moving with liquidity conditions"
        c_do = "Monitor S&P 500 levels for confluence"
    elif btc_gold > 0.5:
        c_badge = "🟡"
        c_desc = "Digital Gold Proxy"
        c_meaning = "BTC acting as inflation hedge / defensive"
        c_do = "Monitor Real Yields and DXY"
    elif btc_spx < -0.5:
        c_badge = "🟠"
        c_desc = "Inverse Risk (Hedge?)"
        c_meaning = "BTC moving opposite to equities (Rare)"
        c_do = "Treat as non-correlated diversifier"

    correlations_block = (
        f"Correlations: {c_badge} {c_desc}\n"
        f"BTC↔S&P: {get_corr_text(btc_spx)}\n"
        f"BTC↔Gold: {get_corr_text(btc_gold)}\n"
        f"Meaning: {c_meaning}\n"
        f"Do: {c_do}"
    )

    # 4. Volatility Block
    v_badge = "🟡"
    if "COMPRESSION" in str(vol_status): v_badge = "🔥"
    elif "ELEVATED" in str(vol_status) or "High" in str(vol_status): v_badge = "🟠"
    
    v_label = "Normal"
    if "COMPRESSION" in str(vol_status): v_label = "Squeeze (big move likely)"
    elif "ELEVATED" in str(vol_status): v_label = "Elevated Risk"
    
    v_meaning = "Volatility is within normal bounds"
    v_do = "Standard risk management"
    
    if "COMPRESSION" in str(vol_status):
        v_meaning = "probability of sharp move rising (direction unknown)"
        v_do = "reduce leverage; scale entries; respect stops / max loss"
        
    vol_block = (
        f"Volatility: {v_badge} {v_label} | 180d vol: {vol_val:.1%}\n"
        f"Meaning: {v_meaning}\n"
        f"Do: {v_do}"
    )

    # 5. Footer
    implies = []
    if is_narrow and "COMPRESSION" in str(vol_status):
        implies.append("- Expect sharp move; participation may stay narrow")
    elif is_narrow:
        implies.append("- Rally is fragile; breadth needs to expand")
    
    if "Crypto-Native" in c_desc:
        implies.append("- Macro signals less predictive for BTC/ETH")
        
    implies_text = "What this implies\n" + "\n".join(implies) if implies else "What this implies\n- Standard market conditions"

    todos = []
    if "COMPRESSION" in str(vol_status):
        todos.append("- Avoid leverage; set hard max drawdown")
    if is_narrow:
        todos.append("- Prefer highest conviction; avoid broad adds")
    if not todos:
        todos.append("- Trade standard setup")
        
    todo_text = "What to do now\n" + "\n".join(todos)

    card = f"""
MARKET REGIME (Cowen Model) — Operating mode for the next 1–4 weeks
{header}
==================================================
{breadth_block}
--------------------------------------------------
{correlations_block}
--------------------------------------------------
{vol_block}
==================================================
{implies_text}

{todo_text}
"""
    return card

if __name__ == "__main__":
    print(get_market_health_summary())
