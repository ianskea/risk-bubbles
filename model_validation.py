
import pandas as pd
import numpy as np
from scipy.stats import pearsonr, spearmanr


def validate_model(df: pd.DataFrame, risk_col: str = 'risk_total', forward_window: int = 30) -> dict:
    """
    Validates the predictive power of the risk model.
    
    Metrics:
    1. Risk-Return Correlation: Correlation between Risk Score and Future Returns. (Should be negative).
    2. Bucket Analysis: Avg return for High Risk vs Low Risk zones.
    """
    if len(df) < 200:
        return {"score": 0, "reason": "Insufficient Data"}

    # Prep Data
    val_df = df.copy()
    val_df['fwd_return'] = val_df['Close'].shift(-forward_window) / val_df['Close'] - 1
    val_df = val_df.dropna()
    
    if val_df.empty: return {"score": 0}

    # 1. Regime Detection
    # Is this a Trending Asset (Momentum) or Ranging (Mean Reversion)?
    if 'sma_200' not in val_df.columns:
        val_df['sma_200'] = val_df['Close'].rolling(200).mean()
    
    # Fill NaN for SMA calculation to avoid dropping too much data
    val_df['sma_200'] = val_df['sma_200'].bfill()

    trend_strength = (val_df['Close'] > val_df['sma_200']).mean()
    # If Price is above 200 SMA more than 30% of the time, it's Momentum biased
    is_momentum = trend_strength > 0.30
    
    regime_type = "MOMENTUM" if is_momentum else "MEAN_REVERSION"
    
    # 2. Base Metrics
    corr_rank, p_rank = spearmanr(val_df[risk_col], val_df['fwd_return'])
    
    # Buckets
    val_df['regime'] = pd.cut(val_df[risk_col], 
                              bins=[0, 0.3, 0.4, 0.6, 0.75, 1.0], 
                              labels=['Strong Buy', 'Buy', 'Hold', 'Reduce', 'Sell'])
    bucket_perf = val_df.groupby('regime', observed=True)['fwd_return'].mean()
    
    score = 0
    
    # 3. Adaptive Scoring
    if is_momentum:
        # --- MOMENTUM VALIDATION ---
        # A. Upside Capture (Did we stay in during the pump?)
        # Look at Top 20% of Future Returns. Was Risk moderate?
        top_quintile_threshold = val_df['fwd_return'].quantile(0.8)
        top_perf_months = val_df[val_df['fwd_return'] > top_quintile_threshold]
        avg_risk_in_pump = top_perf_months[risk_col].mean()
        
        # If Risk was < 0.5 during pumps, EXCELLENT (+40)
        # If Risk was < 0.6 during pumps, GOOD (+20)
        if avg_risk_in_pump < 0.50: score += 40
        elif avg_risk_in_pump < 0.60: score += 20
        
        # B. Downside Protection (Did we find the top?)
        # Look at Bottom 20% of Future Returns. Was Risk high?
        wost_quintile_threshold = val_df['fwd_return'].quantile(0.2)
        crash_months = val_df[val_df['fwd_return'] < wost_quintile_threshold]
        avg_risk_in_crash = crash_months[risk_col].mean()
        
        # Adjusted Targets: 0.5 is "High" enough for a dampened model
        if avg_risk_in_crash > 0.50: score += 40
        elif avg_risk_in_crash > 0.35: score += 20
        
        # C. Data Hygiene (+20)
        if len(val_df) > 365: score += 20

    else:
        # --- MEAN REVERSION VALIDATION (Original Logic) ---
        # 1. Spread (Buy Low > Sell High) (+40)
        avg_buy = bucket_perf.get('Strong Buy', bucket_perf.get('Buy', -999))
        avg_sell = bucket_perf.get('Sell', bucket_perf.get('Reduce', 999))
        if avg_buy > avg_sell: score += 40
        
        # 2. Win Rate (+20)
        win_rate = val_df.groupby('regime', observed=True)['fwd_return'].apply(lambda x: (x > 0).mean())
        wr_buy = win_rate.get('Strong Buy', win_rate.get('Buy', 0))
        wr_sell = win_rate.get('Sell', win_rate.get('Reduce', 1))
        if wr_buy > wr_sell: score += 20
        
        # 3. Correlation (Negative) (+20)
        if corr_rank < -0.1: score += 20
        
        # 4. Data (+20)
        if len(val_df) > 365: score += 20
        
    return {
        "score": score,
        "regime_type": regime_type,
        "n_samples": len(val_df),
        "correlation": corr_rank,
        "avg_risk_pump": locals().get('avg_risk_in_pump', 0),
        "avg_risk_crash": locals().get('avg_risk_in_crash', 0),
        "avg_return_buy_zone": bucket_perf.get('Strong Buy', bucket_perf.get('Buy', 0)),
        "avg_return_sell_zone": bucket_perf.get('Sell', bucket_perf.get('Reduce', 0)),
        "win_rate_buy": locals().get('wr_buy', 0),
        "win_rate_sell": locals().get('wr_sell', 0)
    }

def generate_validation_report_text(ticker: str, metrics: dict) -> str:
    if metrics.get("error"):
        return f"VALIDATION REPORT: {ticker}\nError: {metrics.get('error')}"

    txt = f"""
VALIDATION REPORT: {ticker}
------------------------------------------------
Model Score:        {metrics.get('score', 0)}/100
Regime:             {metrics.get('regime_type', 'N/A')}
Data Points:        {metrics.get('n_samples', 0)}
Correlation:        {metrics.get('correlation', 0):.3f}
"""

    if metrics.get('regime_type') == 'MOMENTUM':
        txt += f"""
Momentum Metrics:
- Avg Risk in Pump: {metrics.get('avg_risk_pump', 0):.2f} (Target < 0.5)
- Avg Risk in Crash: {metrics.get('avg_risk_crash', 0):.2f} (Target > 0.4)
"""
    else:
        txt += f"""
Mean Reversion Metrics:
- Buy Zone Return:  {metrics.get('avg_return_buy_zone', 0)*100:.1f}%
- Sell Zone Return: {metrics.get('avg_return_sell_zone', 0)*100:.1f}%
- Win Rate Spread:  {(metrics.get('win_rate_buy', 0) - metrics.get('win_rate_sell', 0))*100:.1f}%
"""
        
    txt += "------------------------------------------------"
    return txt
