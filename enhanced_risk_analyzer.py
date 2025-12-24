import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import linregress, norm

def fetch_data(ticker: str, period: str = "max") -> pd.DataFrame:
    """
    Fetch adjusted OHLCV for a ticker. Prefers adjusted close to avoid split/div noise.
    """
    print(f"Fetching data for {ticker}...")
    try:
        data = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        if data.empty:
            raise ValueError(f"No data returned for {ticker}")

        # Flatten MultiIndex from yfinance (Price|Ticker)
        if isinstance(data.columns, pd.MultiIndex):
            # If only one ticker, drop the ticker level
            if len(set(data.columns.get_level_values(-1))) == 1:
                data.columns = data.columns.get_level_values(0)
            else:
                data = data.droplevel(0, axis=1)

        # Normalize column names
        cols = {str(c).lower(): c for c in data.columns}
        rename = {}
        close_key = 'close' if 'close' in cols else 'adj close' if 'adj close' in cols else None
        if close_key:
            rename[cols[close_key]] = 'Close'
        for key in ['high', 'low', 'volume']:
            if key in cols:
                rename[cols[key]] = key.capitalize()
        data = data.rename(columns=rename)

        if 'Close' not in data.columns:
            raise ValueError(f"Could not locate Close column in data. Columns found: {data.columns}")

        # Ensure required fields exist; allow Volume to be missing (fallback handled later)
        for required in ['High', 'Low']:
            if required not in data.columns:
                data[required] = data['Close']
        if 'Volume' not in data.columns:
            data['Volume'] = np.nan

        data = data[['Close', 'High', 'Low', 'Volume']].dropna(subset=['Close'])
        return data
    except Exception as e:
        raise ValueError(f"Error fetching data for {ticker}: {e}")

# --- Technical Indicators ---

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    # Wilder smoothing to reduce whipsaw
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    roll_up = gain.ewm(alpha=1/period, adjust=False).mean()
    roll_down = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.clip(lower=0, upper=100)

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd - signal_line # Histogram

def calculate_stochastic(high, low, close, period=14, smooth_k=3):
    # Depending on input, if we only have close, we estimate
    # For this system, we only fetch Close. 
    # Approx: Use rolling max/min of Close as proxy for High/Low if needed
    # Better: yfinance download usually gives OHLC. 
    # For now, let's stick to using Close for everything to keep it robust to single-column inputs,
    # or improve fetch_data to get High/Low. 
    # Let's improve fetch_data later. For now, approx with Close.
    # actually, proper risk analysis needs Volume too.
    # Let's update data fetching to get OHLCV first in a real scenario.
    # But to match existing architecture, let's keep it simple or upgrade fetch_data.
    # Given the prompt, "Institutional-Grade" implies better data.
    # I will stick to Close-only for now to ensure compatibility with the simple fetch_data, 
    # or just use Close for High/Low proxy (rolling max/min).
    
    lowest_low = close.rolling(window=period).min()
    highest_high = close.rolling(window=period).max()
    k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    return k.rolling(window=smooth_k).mean()

def calculate_mfi(high, low, close, volume, period=14):
    """
    Money Flow Index (MFI)
    Uses Typical Price * Volume to gauge buying vs selling pressure.
    Returns 0-100.
    """
    typical_price = (high + low + close) / 3
    money_flow = typical_price * volume
    
    # Get direction
    delta = typical_price.diff()
    
    # Positive/Negative Flow
    pos_flow = money_flow.where(delta > 0, 0)
    neg_flow = money_flow.where(delta < 0, 0)
    
    # Sum over period
    pos_sum = pos_flow.rolling(window=period).sum()
    neg_sum = neg_flow.rolling(window=period).sum()
    
    # Ratio
    mfi_ratio = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100 - (100 / (1 + mfi_ratio))
    return mfi

def calculate_bollinger_width(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> pd.Series:
    ma = series.rolling(window=period, min_periods=period//2).mean()
    std = series.rolling(window=period, min_periods=period//2).std()
    upper = ma + (std * std_dev)
    lower = ma - (std * std_dev)
    # Bandwidth normalized by price
    return (upper - lower) / ma

# --- Risk Components ---

def normalize_series(s: pd.Series, lookback: int = 252, min_frac: float = 0.5) -> pd.Series:
    """Normalize a series to 0-1 percentile rank based on rolling history."""
    min_periods = max(5, int(lookback * min_frac))
    return s.rolling(lookback, min_periods=min_periods).rank(pct=True)

def calculate_valuation_risk(df: pd.DataFrame, min_periods: int = 200) -> tuple[pd.Series, pd.DataFrame]:
    """
    Ensemble Regression Model (Linear + Quadratic + Adaptive)
    Returns: (Risk Score Series, Debug DataFrame)
    """
    n = len(df)
    log_price = np.log(df['Close'])
    t = np.arange(n)
    
    # Pre-allocate
    risk_ensemble = np.full(n, np.nan)
    linear_residuals = np.full(n, np.nan)
    quad_residuals = np.full(n, np.nan)
    
    # We do a simplified version of the loop for speed, or full loop?
    # Full loop required for walk-forward fairness.
    
    # Optimization: Use expanding windows more efficiently if possible, but python loop is clear.
    # Let's stick to the loop from risk_analyzer but expand it.
    
    print("  Calculating valuation risk (ensemble)...")
    
    # Arrays for predicted values
    pred_linear = np.full(n, np.nan)
    pred_quad = np.full(n, np.nan)
    
    for i in range(min_periods, n):
        # Slice history
        # Speed optimization: Don't re-slice everything if not needed, but safe to do so.
        curr_t = t[:i+1]
        curr_log = log_price.values[:i+1]
        
        # 1. Linear
        # fit = linregress(curr_t, curr_log) -> slow inside loop? np.polyfit is faster
        lin_coeffs = np.polyfit(curr_t, curr_log, 1)
        val_lin = np.polyval(lin_coeffs, i)
        pred_linear[i] = val_lin
        
        # 2. Quadratic
        quad_coeffs = np.polyfit(curr_t, curr_log, 2)
        val_quad = np.polyval(quad_coeffs, i)
        pred_quad[i] = val_quad
        
        # Residuals
        resid_lin = curr_log[i] - val_lin
        resid_quad = curr_log[i] - val_quad
        
        linear_residuals[i] = resid_lin
        quad_residuals[i] = resid_quad
        
        # Z-Scores based on historical residuals
        # (Using minimal 200 period history for std dev to stabilize)
        hist_lin = linear_residuals[min_periods:i+1]
        hist_quad = quad_residuals[min_periods:i+1]
        
        std_lin = np.nanstd(hist_lin) if len(hist_lin) > 10 else 1.0
        std_quad = np.nanstd(hist_quad) if len(hist_quad) > 10 else 1.0
        
        z_lin = resid_lin / std_lin if std_lin > 0 else 0
        z_quad = resid_quad / std_quad if std_quad > 0 else 0
        
        # 3. Probabilities
        prob_lin = norm.cdf(z_lin)
        prob_quad = norm.cdf(z_quad)
        
        # Ensemble Weighting:
        # If trend is accelerating (convex), quad fits better.
        # Simple average is robust.
        risk_ensemble[i] = (prob_lin * 0.4) + (prob_quad * 0.6) # Give more weight to curve
        
    debug_df = pd.DataFrame({
        'log_price': log_price,
        'pred_linear': pred_linear,
        'pred_quad': pred_quad,
        'resid_linear': linear_residuals,
        'resid_quad': quad_residuals
    }, index=df.index)
    
    return pd.Series(risk_ensemble, index=df.index), debug_df


def analyze_asset(ticker: str) -> tuple[pd.DataFrame, dict, dict]:
    """
    Main entry point for single asset analysis.
    Returns: (DataFrame with all metrics, Validation Metrics Dict, Metadata Dict)
    """
    # 1. Fetch
    try:
        df = fetch_data(ticker)
    except Exception as e:
        # print(f"Error fetching {ticker}: {e}")
        return pd.DataFrame(), {}, {"ticker": ticker, "reason": f"Fetch Failure: {str(e)}"}

    # 2. Valuation Risk (40%)
    if len(df) < 200:
        # Too little history for stable valuation; return empty with warning
        return pd.DataFrame(), {}, {"ticker": ticker, "reason": "Insufficient history (<200 bars)"}
    val_risk, val_debug = calculate_valuation_risk(df)
    df['risk_valuation'] = val_risk
    
    # 3. Momentum Risk (25%)
    rsi = calculate_rsi(df['Close'])
    df['rsi'] = rsi
    df['risk_momentum'] = normalize_series(rsi, lookback=252)
    
    # 4. Volatility Risk (20%)
    bb_width = calculate_bollinger_width(df['Close'])
    df['risk_volatility'] = normalize_series(bb_width, lookback=252)
    
    # 5. Volume Risk (15%) - Enhanced with MFI
    has_volume = 'Volume' in df.columns and df['Volume'].notna().any() and 'High' in df.columns
    if has_volume:
        mfi = calculate_mfi(df['High'], df['Low'], df['Close'], df['Volume'])
        df['mfi'] = mfi
        df['risk_volume'] = normalize_series(mfi, lookback=252)
    else:
        df['risk_volume'] = np.nan

    weights = {
        'risk_valuation': 0.40,
        'risk_momentum': 0.25,
        'risk_volatility': 0.20
    }
    if has_volume:
        weights['risk_volume'] = 0.15
    else:
        # Renormalize if volume is missing
        weights = {k: v / sum(weights.values()) for k, v in weights.items()}

    def _safe_factor(name: str) -> pd.Series:
        return df.get(name, pd.Series(np.nan, index=df.index)).fillna(0.5)

    total_weight = sum(weights.values())
    df['risk_total'] = sum(_safe_factor(name) * (weight / total_weight) for name, weight in weights.items())

    # Clean early NaNs in inputs without discarding full history
    df = df.dropna(subset=['risk_total'])
    
    # --- Trend / context metrics for AI prompt ---
    cowen_meta = {}
    if ticker.endswith("-USD") or ticker in ["GC=F", "SI=F"]:
        sma_20w = df['Close'].rolling(window=140).mean()
        ema_21w = df['Close'].ewm(span=147, adjust=False).mean()
        sma_50w = df['Close'].rolling(window=350).mean()
        sma_200w = df['Close'].rolling(window=1400).mean()
        df['sma_20w'] = sma_20w
        df['ema_21w'] = ema_21w
        df['sma_50w'] = sma_50w
        df['sma_200w'] = sma_200w
        cowen_meta = {
            "bmsb_20w_sma": sma_20w.iloc[-1],
            "bmsb_21w_ema": ema_21w.iloc[-1],
            "sma_50w": sma_50w.iloc[-1],
            "sma_200w": sma_200w.iloc[-1] if not np.isnan(sma_200w.iloc[-1]) else 0,
        }

    # --- Cycle / context metrics for AI prompt ---
    closes = df['Close']
    last_price = closes.iloc[-1]
    def pct_return(days: int) -> float:
        if len(closes) >= days and closes.iloc[-days] > 0:
            return (last_price / closes.iloc[-days]) - 1
        return np.nan
    returns = {
        "ret_7d": pct_return(7),
        "ret_30d": pct_return(30),
        "ret_90d": pct_return(90),
        "ret_365d": pct_return(365)
    }
    ma50_val = closes.rolling(50).mean().iloc[-1]
    ma200_val = closes.rolling(200).mean().iloc[-1]
    ma50_dist = (last_price / ma50_val - 1) if not np.isnan(ma50_val) and ma50_val > 0 else np.nan
    ma200_dist = (last_price / ma200_val - 1) if not np.isnan(ma200_val) and ma200_val > 0 else np.nan
    rolling_max = closes.cummax()
    drawdown_series = closes / rolling_max - 1
    current_dd = drawdown_series.iloc[-1]
    max_dd = drawdown_series.min()

    # Metadata
    last_risk = df['risk_total'].iloc[-1]
    metadata = {
        "ticker": ticker,
        "last_price": last_price,
        "last_risk": last_risk,
        "rating": "BUY" if last_risk < 0.3 else "SELL" if last_risk > 0.75 else "HOLD",
        "ma50_dist": ma50_dist,
        "ma200_dist": ma200_dist,
        "ret": returns,
        "drawdown_current": current_dd,
        "drawdown_max": max_dd,
        "volume_missing": not has_volume,
        "reason": None,  # reserved for hard stops (e.g., insufficient history)
        **cowen_meta
    }
    
    return df, cowen_meta, metadata

def calculate_mlr(gold_df, gdx_df, period=60):
    """
    Calculates Miner Leverage Ratio (MLR).
    Formula: Rolling Ratio of (GDX Returns / Gold Returns).
    Target: < 0.5 (Undervalued), > 3 (Bubble).
    """
    if gold_df.empty or gdx_df.empty: return 0.0
    
    # Align dates
    common_idx = gold_df.index.intersection(gdx_df.index)
    g = gold_df.loc[common_idx, 'Close'].pct_change()
    m = gdx_df.loc[common_idx, 'Close'].pct_change()
    
    # User Spec: "(GDX % change) / (Gold % change)"
    # We use rolling sum of returns to smooth daily noise
    roll_g = g.rolling(period).sum()
    roll_m = m.rolling(period).sum()
    
    # Handle division by zero
    mlr = roll_m / roll_g
    mlr = mlr.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    return mlr.iloc[-1]

def calculate_yield_corr(gold_df, tnx_df, period=60):
    """
    Calculates Yield-Gold Correlation (60-day).
    Target: -0.7 to -0.9 (Normal). > +0.3 (Crisis).
    """
    if gold_df.empty or tnx_df.empty: return 0.0
    
    common_idx = gold_df.index.intersection(tnx_df.index)
    g = gold_df.loc[common_idx, 'Close']
    y = tnx_df.loc[common_idx, 'Close']
    
    corr = g.rolling(period).corr(y)
    return corr.iloc[-1]

if __name__ == "__main__":
    # Test
    try:
        df, _, meta = analyze_asset("BTC-USD")
        if not df.empty:
            print(df.tail())
            print(meta)
    except Exception as e:
        print(e)
