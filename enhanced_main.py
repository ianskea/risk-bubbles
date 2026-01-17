
import os
import time
import logging
from datetime import datetime
# from PIL import Image # For potential future image processing
from openai import OpenAI
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import pandas as pd

from enhanced_risk_analyzer import analyze_asset
from model_validation import validate_model

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

TICKERS = {
    # Crypto
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "Cardano": "ADA-USD",
    
    # Commodities
    "Gold": "GC=F",
    "Silver": "SI=F",
    
    # ASX - Miners / Resources
    "BHP Group": "BHP.AX",
    "Rio Tinto": "RIO.AX",
    "Fortescue": "FMG.AX",
    "Mineral Resources": "MIN.AX",
    "Pilbara Minerals": "PLS.AX",
    "South32": "S32.AX",
    "IGO Ltd": "IGO.AX",
    
    # ASX - Financials / Other
    "Macquarie Group": "MQG.AX",
    "SiteMinder": "SDR.AX",
    
    # ASX - ETFs
    "Global X Semi": "SEMI.AX",
    "Global X FANG+": "FANG.AX",
    "BetaShares Mining Resources": "QRE.AX",
    "Global X Robots": "RBTZ.AX",
    "BetaShares Asia": "ASIA.AX",
    "Vanguard Prop": "VAP.AX",
    "BetaShares NDQ": "NDQ.AX"
}

OUTPUT_DIR = "output"
CHART_DIR = os.path.join(OUTPUT_DIR, "charts")
LOG_DIR = "logs"

def ensure_dirs():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    if not os.path.exists(CHART_DIR): os.makedirs(CHART_DIR)
    if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)

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

def plot_comprehensive_analysis(ticker_name, ticker_symbol, df):
    """
    6-Panel Institutional Chart
    """
    fig = plt.figure(figsize=(15, 12))
    gs = fig.add_gridspec(3, 2)
    
    # 1. Price + Regression Bands (Top Left)
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_title(f"{ticker_name} - Price & Fair Value Models")
    ax1.plot(df.index, df['Close'], label='Price', color='black', lw=1)
    
    # Needs debug info for bands? 
    # enhanced_risk_analyzer returns just Risk Scores in main DF.
    # We might want to expose regression bands in the future.
    # For now, plot Simple Moving Averages as proxy for bands if not in DF?
    # Or purely use price.
    ax1.plot(df.index, df['Close'].rolling(200).mean(), label='200 SMA', color='orange', ls='--')
    ax1.set_yscale('log')
    ax1.legend()
    ax1.grid(True, alpha=0.2)
    
    # 2. Composite Risk (Top Right)
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_title("Composite Risk Score (0-1)")
    ax2.plot(df.index, df['risk_total'], color='blue', lw=1.5)
    ax2.axhline(0.7, color='red', ls='--', alpha=0.5)
    ax2.axhline(0.3, color='green', ls='--', alpha=0.5)
    ax2.fill_between(df.index, 0.7, 1.0, color='red', alpha=0.1)
    ax2.fill_between(df.index, 0.0, 0.3, color='green', alpha=0.1)
    ax2.grid(True, alpha=0.2)
    
    # 3. Valuation Risk (Mid Left)
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_title("Factor: Valuation Risk")
    ax3.plot(df.index, df.get('risk_valuation', df['risk_total']), color='purple', lw=1)
    ax3.grid(True, alpha=0.2)
    
    # 4. Momentum Risk/RSI (Mid Right)
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_title("Factor: Momentum (RSI)")
    ax4.plot(df.index, df.get('rsi', [50]*len(df)), color='orange', lw=1)
    ax4.axhline(70, color='red', ls=':')
    ax4.axhline(30, color='green', ls=':')
    ax4.grid(True, alpha=0.2)
    
    # 5. Volatility Risk (Bot Left)
    ax5 = fig.add_subplot(gs[2, 0])
    ax5.set_title("Factor: Volatility Risk")
    ax5.plot(df.index, df.get('risk_volatility', [0.5]*len(df)), color='gray', lw=1)
    ax5.grid(True, alpha=0.2)
    
    # 6. Returns Distribution? Or Validation?
    # Let's show Recent 1-Year Performance vs Risk
    ax6 = fig.add_subplot(gs[2, 1])
    ax6.text(0.1, 0.5, "Detailed Validation Metrics\nSee Report", fontsize=12)
    ax6.axis('off')

    plt.tight_layout()
    path = os.path.join(CHART_DIR, f"{ticker_symbol}_comprehensive.png")
    try:
        plt.savefig(path)
    except Exception as e:
        logging.error(f"Error generating chart for {ticker_name}: {e}")
    plt.close()
    return path

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
                max_tokens=500,
                timeout=30
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
    
    for name, ticker in TICKERS.items():
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
                "val_metrics": val_metrics
            }
            
            plot_comprehensive_analysis(name, ticker, df)
            
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
    full_report += "="*60 + "\n\n"
    
    # 1. Macro Dashboard
    full_report += cycle_text
    
    # 2. VALIDATED SIGNALS
    full_report += "SECTION 1: ACTIONABLE INSTITUTIONAL SIGNALS (Validation >= 60)\n"
    full_report += "="*60 + "\n"
    
    if not valid_assets:
        full_report += "No assets passed strict validation criteria.\n"
    
    for asset in valid_assets:
        r = asset['risk']
        
        # Signal Logic (v2.0 Asymmetric)
        exit_t = 0.85 if "USD" in asset['ticker'] else 0.80 if "VGS" in asset['ticker'] or "MQG" in asset['ticker'] else 0.75
        signal_str = "🟢 [BUY]" if r < 0.3 else "🔴 [SELL]" if r > exit_t else "🟡 [HOLD]"

        meta = asset['meta']
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
Validation Score: {asset['score']}/100
Context: {context_line}

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
