
import os
import time
import logging
from datetime import datetime
# from PIL import Image # For potential future image processing
from openai import OpenAI
from dotenv import load_dotenv
import pandas as pd

from enhanced_risk_analyzer import analyze_asset
from sector_config import SECTOR_INTELLIGENCE, BTC_ON_CHAIN_FLOORS, LAST_UPDATED
from charting import plot_comprehensive_analysis
from model_validation import validate_model
from sentiment_analyzer import fetch_crypto_sentiment, get_sentiment_advice
from santiment_api import fetch_santiment_summary

# Load Environment Variables
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if DEEPSEEK_API_KEY:
    try:
        client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    except:
        client = None
else:
    client = None

OUTPUT_DIR = "output"
CHART_DIR = os.path.join(OUTPUT_DIR, "charts")
LOG_DIR = "logs"

def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CHART_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

def setup_logging():
    log_file = os.path.join(LOG_DIR, "institutional_analysis.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logging.info("Logging initialized.")

def generate_ai_analysis(ticker, price, risk, metrics, meta):
    if not client:
        return "AI Analysis not available (No API Key)"

    def fmt_pct(val):
        return "N/A" if val is None or pd.isna(val) else f"{val*100:.1f}%"
        
    ret = meta.get("ret", {})
    ma50 = fmt_pct(meta.get("ma50_dist"))
    ma200 = fmt_pct(meta.get("ma200_dist"))
    dd_cur = fmt_pct(meta.get("drawdown_current"))
    dd_max = fmt_pct(meta.get("drawdown_max"))
    ret_30 = fmt_pct(ret.get("ret_30d"))
    ret_90 = fmt_pct(ret.get("ret_90d"))
    ret_365 = fmt_pct(ret.get("ret_365d"))
        
    # Optimized Prompt
    prompt = f"""
    Provide a professional Institutional Risk Assessment for {ticker}.
    Current Price: ${price:.2f}
    Composite Risk Score: {risk:.2f} (0.0 = Buy/Value, 1.0 = Sell/Bubble)
    Gone Home Status: {meta.get('gone_home', 'N/A')}
    Sector Context: {meta.get('sector_context', 'General Asset')}
    
    Interpretation Rules (v2.0 Asymmetric):
    - Value Zone (< 0.30): Institutional Accumulation (Buy).
    - Danger Zone: Redlines vary by asset:
        - Crypto (BTC/ETH): > 0.85
        - Broad Market (VGS/MQG): > 0.80
        - Satellite/Miners: > 0.75
    - If risk is below Danger Zone but high, reduce to Moonbag.
    
    Context:
    - Performance: 30d {ret_30}, 90d {ret_90}, 365d {ret_365}
    - Trend: Distance to 50D MA {ma50}, 200D MA {ma200}
    - Drawdown: Current {dd_cur}, Max {dd_max}
    - Model Validation Score: {metrics.get('score', 0)}/100
    - On-Chain Floors: {meta.get('on_chain_floors', 'N/A')}
    - Santiment Intelligence (31d Lag): {meta.get('santiment_summary', 'N/A')}

    Structure your response clearly:
    1. **Institutional Action Bias**: (Must align with Interpretation Rules above)
    2. **Key Risk Drivers**: Analysis of valuation, momentum, and volatility.
    3. **Structural Context**: Note if price is above/below key moving averages and the significance of the current drawdown.

    Ensure the response is complete, objective, and does not cut off.
    """
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # logging.info(f"AI Request for {ticker} (Attempt {attempt+1}/{max_retries})...")
            print(f"  > AI Request for {ticker} (Attempt {attempt+1}/{max_retries})...")
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                timeout=45
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            # logging.warning(f"AI Failure {ticker}: {e}")
            print(f"  > AI Error ({ticker}): {e}. Retrying...")
            time.sleep(2 * (attempt + 1)) # Backoff
            
    return "AI Analysis Failed after retries."

def analyze_market_cycle():
    """
    Context-only macro snapshot (non-blocking).
    """
    print("Analyzing Capital Cascade Model...")
    from enhanced_risk_analyzer import analyze_asset
    
    cycle_report = "RISK-BUBBLE ANALYSIS: CAPITAL CASCADE DASHBOARD (CONTEXT ONLY)\n" + "="*50 + "\n"
    
    try:
        def safe_asset(t):
            try:
                df, _, meta = analyze_asset(t)
                if meta.get("reason") or df.empty:
                    return pd.DataFrame(), {"last_price": 0, "last_risk": 0}
                return df, meta
            except Exception:
                return pd.DataFrame(), {"last_price": 0, "last_risk": 0}

        # Core assets (best effort)
        btc_df, btc_meta = safe_asset("BTC-USD")
        eth_df, eth_meta = safe_asset("ETH-USD")
        gold_df, gold_meta = safe_asset("GC=F")
        silver_df, silver_meta = safe_asset("SI=F")

        def get_signal(ticker_symbol, r):
            # Asymmetric Logic
            exit_t = 0.85 if "USD" in ticker_symbol else 0.80 if "VGS" in ticker_symbol or "MQG" in ticker_symbol else 0.75
            buy_t = 0.30
            
            if r < buy_t: return "🟢 [BUY]"
            if r > exit_t: return "🔴 [SELL]"
            return "🟡 [HOLD]"

        # Ratios for color
        gsr = gold_meta['last_price'] / silver_meta['last_price'] if silver_meta['last_price'] else 0
        eth_btc = eth_meta['last_price'] / btc_meta['last_price'] if btc_meta['last_price'] else 0

        cycle_report += "ASSET STATUS (CONTEXT):\n"
        cycle_report += f"- BTC:    ${btc_meta['last_price']:.0f} | Risk: {round(btc_meta['last_risk'],2):.2f} {get_signal('BTC-USD', round(btc_meta['last_risk'],2))}\n"
        cycle_report += f"- ETH:    ${eth_meta['last_price']:.0f} | Risk: {round(eth_meta['last_risk'],2):.2f} {get_signal('ETH-USD', round(eth_meta['last_risk'],2))}\n"
        cycle_report += f"- GOLD:   ${gold_meta['last_price']:.1f} | Risk: {round(gold_meta['last_risk'],2):.2f} {get_signal('GC=F', round(gold_meta['last_risk'],2))}\n"
        cycle_report += f"- SILVER: ${silver_meta['last_price']:.1f} | Risk: {round(silver_meta['last_risk'],2):.2f} {get_signal('SI=F', round(silver_meta['last_risk'],2))}\n\n"
        
        cycle_report += "KEY METRICS (COLOR ONLY):\n"
        cycle_report += f"- Gold/Silver Ratio: {gsr:.2f}\n"
        cycle_report += f"- ETH/BTC Ratio:     {eth_btc:.4f}\n"

        # Sentiment Integration
        fng_val, fng_label = fetch_crypto_sentiment()
        fng_advice = get_sentiment_advice(fng_val, fng_label)
        cycle_report += f"\nSENTIMENT (FEAR & GREED):\n"
        cycle_report += f"- Index: {fng_val if fng_val else 'N/A'} ({fng_label})\n"
        cycle_report += f"- Takeaway: {fng_advice}\n"

    except Exception as e:
        cycle_report += f"Error calculating cycle metrics: {e}\n"
        import traceback
        traceback.print_exc()
    
    cycle_report += "="*50 + "\n\n"
    
    context = {
        "gsr": locals().get('gsr', 0),
        "eth_btc": locals().get('eth_btc', 0),
    }
    return cycle_report, context

def main():
    ensure_dirs()
    setup_logging()
    print("Starting Institutional Analysis Run...")
    logging.info("Starting Institutional Analysis Run...")
    
    report_path = os.path.join(OUTPUT_DIR, "institutional_analysis_report.txt")
    
    # --- MACRO CYCLE (Context Only) ---
    try:
        cycle_text, macro_context = analyze_market_cycle()
        cycle_text = "MACRO DASHBOARD (CONTEXT ONLY)\n" + "-"*60 + "\n" + cycle_text
        
        # [NEW] MARKET HEALTH ADDITION
        print("Analyzing Market Health (Cowen Model)...")
        from market_health import get_market_health_summary
        health_text = get_market_health_summary()
        cycle_text += "\n" + health_text
        
    except Exception as e:
        cycle_text = f"MACRO DASHBOARD (CONTEXT ONLY)\n{'-'*60}\nUnavailable: {e}\n"
        macro_context = {}
    
    valid_assets = []
    invalid_assets = []
    
    print("\n--- Processing Assets ---")
    
    for sector_name, sector_data in SECTOR_INTELLIGENCE.items():
        print(f"\n--- Processing Sector: {sector_name} ---")
        exit_t = sector_data.get("danger_zone_threshold", 0.8)
        fetch_santiment = sector_data.get("fetch_santiment", False)
        
        for name, ticker in sector_data["assets"].items():
            print(f"Analyzing {name} ({ticker})...")
            try:
                df, _, meta = analyze_asset(ticker)
                if meta.get("reason"):
                    invalid_assets.append({
                        "name": name,
                        "ticker": ticker,
                        "reason": meta["reason"]
                    })
                    continue
                if df.empty:
                    invalid_assets.append({
                        "name": name,
                        "ticker": ticker,
                        "reason": "No data returned"
                    })
                    continue
                
                # Run Validation
                val_metrics = validate_model(df)
                score = val_metrics.get('score', 0)
                if val_metrics.get("error"):
                    invalid_assets.append({
                        "name": name,
                        "ticker": ticker,
                        "reason": val_metrics["error"]
                    })
                    continue
                
                # --- INSTITUTIONAL HARD GATE ---
                # Score < 60: FAIL. NO SIGNAL.
                # Score >= 60: PASS. Actionable.
                
                is_valid = score >= 60

                # Common Data
                asset_data = {
                    "name": name,
                    "ticker": ticker,
                    "price": round(meta['last_price'], 2),
                    "risk": round(meta['last_risk'], 2),
                    "score": score,
                    "meta": meta,
                    "val_metrics": val_metrics,
                    "sector": sector_name,
                    "exit_threshold": exit_t
                }
                
                # Inject Sector Context
                asset_data["meta"]["sector_context"] = sector_data.get("sector_context", "General Asset")
                
                # Inject On-Chain Floors for BTC
                if ticker == "BTC-USD":
                    asset_data["meta"]["on_chain_floors"] = BTC_ON_CHAIN_FLOORS
                
                # Inject Santiment Data
                if fetch_santiment:
                    print(f"  > Fetching Santiment Intelligence for {name}...")
                    santiment_data = fetch_santiment_summary(name)
                    asset_data["meta"]["santiment_summary"] = santiment_data
                    
                plot_comprehensive_analysis(name, ticker, df, CHART_DIR)
                
                if is_valid:
                    # Generate AI Insight only for valid
                    asset_data["ai_text"] = generate_ai_analysis(name, meta['last_price'], meta['last_risk'], val_metrics, meta)
                    valid_assets.append(asset_data)
                else:
                    asset_data["reason"] = "Validation Failure (<60)"
                    invalid_assets.append(asset_data)
                
                time.sleep(1) # Rate limit
            

            except Exception as e:
                print(f"Error {name}: {e}")
                import traceback
                traceback.print_exc()

    # --- REPORT CONSTRUCTION ---
    full_report = f"INSTITUTIONAL RISK REPORT - {datetime.now().strftime('%Y-%m-%d')}\n"
    full_report += "="*60 + "\n"
    
    # Check for stale sector configuration
    try:
        last_updated_date = datetime.strptime(LAST_UPDATED, "%Y-%m-%d")
        if (datetime.now() - last_updated_date).days > 30:
            staleness_warning = "\n⚠️  WARNING: Sector Intelligence is over 30 days old. Review sector_config.py.\n"
            print(staleness_warning)
            full_report += staleness_warning
    except ValueError:
        pass
        
    full_report += "\n"
    
    # 1. Macro Dashboard
    full_report += cycle_text
    
    # 2. VALIDATED SIGNALS
    full_report += "SECTION 1: ACTIONABLE INSTITUTIONAL SIGNALS (Validation >= 60)\n"
    full_report += "="*60 + "\n"
    
    if not valid_assets:
        full_report += "No assets passed strict validation criteria.\n"
    
    for asset in valid_assets:
        r = asset['risk']
        meta = asset['meta']
        price = asset['price']
        sma_20d = meta.get('sma_20d', 0)
        
        # Signal Logic (v2.1 Momentum Stop)
        exit_t = asset.get('exit_threshold', 0.8)
        
        if r < 0.3:
            signal_str = "🟢 [BUY]"
        elif r > exit_t:
            if price > sma_20d:
                signal_str = "🔥 [RIDE BUBBLE]"
            else:
                signal_str = "🔴 [SELL (Trend Broken)]"
        else:
            signal_str = "🟡 [HOLD]"
        ma_context = []
        if meta.get("ma50_dist") is not None and not pd.isna(meta.get("ma50_dist")):
            ma_context.append(f"MA50 dist: {meta['ma50_dist']*100:.1f}%")
        if meta.get("ma200_dist") is not None and not pd.isna(meta.get("ma200_dist")):
            ma_context.append(f"MA200 dist: {meta['ma200_dist']*100:.1f}%")
        dd_context = []
        if meta.get("drawdown_current") is not None and not pd.isna(meta.get("drawdown_current")):
            max_dd_val = meta.get('drawdown_max', 0)
            max_dd_text = f"{max_dd_val*100:.1f}%" if not pd.isna(max_dd_val) else "N/A"
            dd_context.append(f"Drawdown now: {meta['drawdown_current']*100:.1f}% (max {max_dd_text})")
        context_line = "; ".join(ma_context + dd_context) if (ma_context or dd_context) else "N/A"
        section = f"""
ASSET: {asset['name']} ({asset['ticker']})
Price: ${asset['price']:.2f}
RISK SCORE: {r:.2f}  {signal_str}
Gone Home Status: {meta.get('gone_home', 'N/A')}
Validation Score: {asset['score']}/100
"""
        # [NEW] On-Chain Context for BTC
        if asset['ticker'] == "BTC-USD":
            floors = meta.get("on_chain_floors", {})
            floor_text = " | ".join([f"{k}: ${v:,}" for k, v in floors.items()])
            section += f"On-Chain Floors: {floor_text}\n"
            
        # [NEW] Santiment Context
        sant_sum = meta.get("santiment_summary", {})
        if sant_sum and "error" not in sant_sum:
            mvrv_val = sant_sum.get('mvrv_usd_365d')
            mvrv_str = f"{float(mvrv_val):.2f}" if mvrv_val is not None else "N/A"
            section += f"Santiment (31d Lag): MVRV {mvrv_str} ({sant_sum.get('mvrv_status', 'N/A')}) | Sentiment: {sant_sum.get('sentiment_status', 'N/A')}\n"
            
        section += f"Context: {context_line}\n"

        section += f"""
AI INSIGHT:
{asset['ai_text']}
--------------------------------------------------
"""
        full_report += section

    # 3. FAILED MODELS
    full_report += "\nSECTION 2: MODEL FAILURE / NO SIGNAL\n"
    full_report += "These assets were not actioned due to validation/history/volume gates.\n"
    full_report += "="*60 + "\n"
    full_report += f"{'ASSET':<20} | {'REASON'}\n"
    full_report += "-"*60 + "\n"
    
    for asset in invalid_assets:
        reason = asset.get("reason", "Validation < 60")
        full_report += f"{asset.get('name','N/A'):<20} | {reason}\n"
        
    # Save
    with open(report_path, "w") as f:
        f.write(full_report)
        
    print(f"\nDone. Report saved to {report_path}")

if __name__ == "__main__":
    main()
