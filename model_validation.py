
import pandas as pd
import numpy as np
from scipy.stats import pearsonr, spearmanr


def validate_model(df: pd.DataFrame, risk_col: str = 'risk_total', forward_window: int = 30) -> dict:
    """
    Validates the predictive power of the risk model.
    
    Metrics:
    1. Risk-Return Correlation: Correlation between Risk Score and Future Returns. (Should be negative).
    2. Bucket Analysis: Avg return for High Risk vs Low Risk zones.
    3. Calibration: If Risk=0.8, is price in 80th percentile of history?
    """
    # Create Analysis Setup
    val_df = df.copy()
    
    # Calculate Forward Returns (e.g., 30 days)
    # We want to know: If Risk is HIGH at t, is Return(t+30) LOW?
    val_df['fwd_return'] = val_df['Close'].shift(-forward_window) / val_df['Close'] - 1
    val_df.dropna(inplace=True)
    
    if len(val_df) < 100:
        return {"error": "Insufficient data for validation (<100 samples)"}
    
    # 1. Correlation
    # We expect Meaningful Negative Correlation (Higher Risk -> Lower Future Return)
    corr_pearson, p_pearson = pearsonr(val_df[risk_col], val_df['fwd_return'])
    corr_rank, p_rank = spearmanr(val_df[risk_col], val_df['fwd_return'])
    
    # 2. Bucket Analysis
    # Define Regimes
    val_df['regime'] = pd.cut(val_df[risk_col], 
                              bins=[0, 0.3, 0.4, 0.6, 0.75, 1.0], 
                              labels=['Strong Buy', 'Buy', 'Hold', 'Reduce', 'Sell'])
    
    bucket_perf = val_df.groupby('regime', observed=True)['fwd_return'].mean()
    win_rate = val_df.groupby('regime', observed=True)['fwd_return'].apply(lambda x: (x > 0).mean())
    
    # 3. Simple Backtest (Signal-based)
    # Strategy: Long when Risk < 0.4, Cash when Risk > 0.75?
    # Simplified: Compare Top Decile vs Bottom Decile returns
    top_decile_ret = val_df[val_df[risk_col] > 0.9]['fwd_return'].mean()
    bottom_decile_ret = val_df[val_df[risk_col] < 0.1]['fwd_return'].mean()
    
    # Score the Model (0-100)
    # Criteria:
    # - Correlation < -0.1 (+30 pts)
    # - Low Risk Return > High Risk Return (+30 pts)
    # - Significant p-value (+20 pts)
    # - Data quality (+20 pts)
    
    score = 0
    if corr_rank < -0.1: score += 30
    if corr_rank < -0.3: score += 10 # Bonus
    if bottom_decile_ret > top_decile_ret: score += 30
    if p_rank < 0.05: score += 20
    if len(val_df) > 365: score += 10
    
    report = {
        "score": score,
        "n_samples": len(val_df),
        "correlation": corr_rank,
        "p_value": p_rank,
        "avg_return_buy_zone": bucket_perf.get('Strong Buy', 0.0),
        "avg_return_sell_zone": bucket_perf.get('Sell', 0.0),
        "spread": bottom_decile_ret - top_decile_ret,
        "win_rate_buy": win_rate.get('Strong Buy', 0.0),
        "win_rate_sell": win_rate.get('Sell', 0.0) # Actually win rate for sell zone means "did it go up?" (hopefully low)
    }
    
    return report

def generate_validation_report_text(ticker: str, metrics: dict) -> str:
    return f"""
VALIDATION REPORT: {ticker}
------------------------------------------------
Model Score:        {metrics.get('score', 0)}/100
Data Points:        {metrics.get('n_samples', 0)}

Predictive Power:
- Rank Correlation: {metrics.get('correlation', 0):.3f} (Ideal: < -0.2)
- Significance (p): {metrics.get('p_value', 1.0):.4f} (Ideal: < 0.05)

Performance Spread (30-day fwd):
- Strong Buy Zone:  {metrics.get('avg_return_buy_zone', 0)*100:.1f}% avg return
- Sell Zone:        {metrics.get('avg_return_sell_zone', 0)*100:.1f}% avg return
- Opportunity Spread: {metrics.get('spread', 0)*100:.1f}% 

Win Rates (Prob. of Positive Return):
- Buy Zone:         {metrics.get('win_rate_buy', 0)*100:.0f}%
- Sell Zone:        {metrics.get('win_rate_sell', 0)*100:.0f}% (Lower is better for avoiding crash)
------------------------------------------------
"""
