import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import linregress, norm

def fetch_data(ticker: str, period: str = "max") -> pd.DataFrame:
    """
    Fetches historical market data for a given ticker.
    """
    print(f"Fetching data for {ticker}...")
    data = yf.download(ticker, period=period, progress=False, auto_adjust=False)
    print(f"Columns: {data.columns}")
    if data.empty:
        raise ValueError(f"No data found for ticker {ticker}")
    
    # Flatten yfinance MultiIndex if present
    if isinstance(data.columns, pd.MultiIndex):
        # Check if 'Close' is a level
        if 'Close' in data.columns.get_level_values(0):
            data = data.xs('Close', axis=1, level=0, drop_level=True)
    
    # If we have a single column DataFrame (e.g. just the ticker name), rename it to Close
    # This happens if we did the .xs above on a single ticker
    if len(data.columns) == 1:
        data = data.rename(columns={data.columns[0]: 'Close'})
        
    # Validation
    if 'Close' not in data.columns:
        # Last ditch effort: if 'Close' is part of a flat index (e.g. 'Close_BTC') - unlikely with modern yfinance but possible
        # Or if the user passed multiple tickers, we might have multiple columns.
        # For this specific tool, we assume 1 ticker.
        # Let's try to find a column that contains "Close"
        close_cols = [c for c in data.columns if 'Close' in str(c)]
        if close_cols:
             data = data.rename(columns={close_cols[0]: 'Close'})
             data = data[['Close']]

    if 'Close' not in data.columns:
         raise ValueError(f"Could not locate 'Close' column in data. Columns found: {data.columns}")

    data = data[['Close']].dropna()
    return data

def calculate_log_regression_risk(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates a Risk Metric provided a DataFrame with a 'Close' column.
    
    Methodology:
    1. Log-transform the Price.
    2. Fit a Linear Regression to (Time, LogPrice).
    3. Calculate the Z-Score of the current LogPrice vs the Predicted LogPrice.
    4. Normalize Z-Score to 0-1 using the Cumulative Distribution Function (CDF).
       - Risk 0.5 = Fair Value (on trend).
       - Risk > 0.8 = High Risk (Bubble).
       - Risk < 0.2 = Low Risk (Opportunity).
    """
    if 'Close' not in df.columns:
         # If data is a Series, convert to DF
         if isinstance(df, pd.Series):
             df = df.to_frame(name='Close')
         else:
             raise ValueError("DataFrame must contain a 'Close' column")

    # Working copy
    calc_df = df.copy()
    
    # 1. Prepare data
    # Use integer index for time
    calc_df['t'] = np.arange(len(calc_df))
    calc_df['log_price'] = np.log(calc_df['Close'])
    
    # Pre-allocate arrays for speed
    n = len(calc_df)
    log_predicted = np.full(n, np.nan)
    residuals = np.full(n, np.nan)
    z_scores = np.full(n, np.nan)
    risk_metric = np.full(n, np.nan)
    
    # Warm-up period (e.g., 200 days) to allow regression to stabilize
    # Before this, we can't reliably calculate "Fair Value"
    min_periods = 200
    
    print("  Calculating expanding window regression (this may take a moment)...")
    
    # Loop for Expanding Window (Walk-Forward)
    for i in range(min_periods, n):
        # Slice data known at time i
        current_t = calc_df['t'].values[:i+1]
        current_log = calc_df['log_price'].values[:i+1]
        
        # Fit Quadratic (2nd Degree) to account for diminishing returns
        # This uses ONLY history available at day i
        coeffs = np.polyfit(current_t, current_log, 2)
        
        # Predict "Fair Value" for TODAY (day i) only
        pred_now = np.polyval(coeffs, i)
        log_predicted[i] = pred_now
        
        # Calculate Deviation
        resid_now = current_log[i] - pred_now
        residuals[i] = resid_now
        
        # Calculate Risk Score based on HISTORICAL deviations
        # We compare today's residual to the standard deviation of ALL past residuals
        # This tells us: "How weird is today's move compared to normal volatility?"
        # Using a rolling window for volatility could be another option, but "all time" is robust.
        past_residuals = residuals[min_periods:i+1]
        std_dev_hist = np.std(past_residuals) if len(past_residuals) > 1 else 1.0
        
        if std_dev_hist > 0:
            z = resid_now / std_dev_hist
        else:
            z = 0
            
        z_scores[i] = z
        risk_metric[i] = norm.cdf(z)
        
    # Store results back to DataFrame
    calc_df['log_predicted'] = log_predicted
    calc_df['predicted_price'] = np.exp(calc_df['log_predicted'])
    calc_df['residual'] = residuals
    calc_df['z_score'] = z_scores
    calc_df['risk'] = risk_metric
    
    # Generate Bands for visualization
    # We use the FINAL standard deviation to draw the bands for context, 
    # but the risk score itself was calculated point-in-time.
    # To differentiate: The chart bands show "Where is it now?", Risk shows "How scary was it then?"
    # Let's use the dynamic std dev for dynamic bands? No, might be too messy.
    # Let's use a rolling std dev for the bands to make them "breathing"
    final_std = np.nanstd(residuals)
    calc_df['top_band_log'] = calc_df['log_predicted'] + 2 * final_std
    calc_df['bottom_band_log'] = calc_df['log_predicted'] - 2 * final_std
    
    calc_df['top_band'] = np.exp(calc_df['top_band_log'])
    calc_df['bottom_band'] = np.exp(calc_df['bottom_band_log'])
    
    return calc_df

if __name__ == "__main__":
    # Quick Test
    try:
        btc_data = fetch_data("BTC-USD")
        risk_data = calculate_log_regression_risk(btc_data)
        print(risk_data[['Close', 'risk']].tail())
    except Exception as e:
        print(e)
