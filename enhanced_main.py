
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
    
    Interpretation Rules for Composite Risk Score:
    - Less than 0.30: Accumulate/Buy/Value Opportunity.
    - 0.30 to 0.70: Hold/Neutral/Caution.
    - Greater than 0.70: Scale Out/Reduce/Sell/Bubble Risk.
    
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
    Analyzes Capital Cascade Model (Crypto, Metals, Macro, China, Social).
    Generates Composite Risk Score and Dashboard.
    """
    print("Analyzing Capital Cascade Model...")
    from enhanced_risk_analyzer import fetch_data, analyze_asset, calculate_mlr, calculate_yield_corr
    
    cycle_report = "RISK-BUBBLE ANALYSIS: CAPITAL CASCADE DASHBOARD\n" + "="*50 + "\n"
    
    try:
        # -- 1. FETCH DATA & ANALYZE CORE ASSETS --
        # Crypto
        btc_df, _, btc_meta = analyze_asset("BTC-USD")
        eth_df, _, eth_meta = analyze_asset("ETH-USD")
        
        # Metals
        gold_df, _, gold_meta = analyze_asset("GC=F")
        silver_df, _, silver_meta = analyze_asset("SI=F")
        gdx_df, _, gdx_meta = analyze_asset("GDX")
        
        # Macro
        tnx_df = fetch_data("^TNX") # 10 Year Yield
        
        # -- 2. CALCULATE METRICS --
        # Ratios
        gsr = gold_meta['last_price'] / silver_meta['last_price'] if silver_meta['last_price'] else 0
        eth_btc = eth_meta['last_price'] / btc_meta['last_price'] if btc_meta['last_price'] else 0
        mlr = calculate_mlr(gold_df, gdx_df)
        yield_corr = calculate_yield_corr(gold_df, tnx_df)
        
        # BTC Dominance Proxy (ETH/BTC)
        # Low ETH/BTC = High BTC.D (Bear/Early Bull). High ETH/BTC = Low BTC.D (Alt Season).
        
        # -- 3. COMPONENT RISK SCORES (0-1) --
        # Crypto Risk: Avg of BTC & ETH Risk (proxy for market)
        crypto_risk = (btc_meta['last_risk'] + eth_meta['last_risk']) / 2
        
        # Metals Risk: Avg of Gold & Silver Risk
        metals_risk = (gold_meta['last_risk'] + silver_meta['last_risk']) / 2
        
        # Macro Risk: Based on Yield Corr & MLR Divergence
        # If Corr > 0.3 (Broken) -> High Risk. If MLR < 0.5 (Cheap) -> Low Risk?
        # User formula implies Macro is input. Let's map Yield Corr to 0-1.
        # Corr -1 (Good) -> 0. Corr +1 (Bad) -> 1.
        # Adjusted: (Corr + 1) / 2?
        macro_risk = (yield_corr + 1) / 2 
        # But user says "Macro Risk: 0.70 (HIGH)" when Corr is ~0 (Broken).
        # So Normalized: 0.5 + (Corr * 0.5)? If Corr=0, Risk=0.5. If Corr=0.4, Risk=0.7.
        macro_risk = 0.5 + (yield_corr * 0.5)
        
        # China (Static 0.3) & Social (Static 0.55) as per User Request
        china_risk = 0.30
        social_risk = 0.55
        
        # -- 4. COMPOSITE SCORE --
        # Formula: (Crypto * 0.25) + (Metals * 0.25) + (Macro * 0.25) + (China * 0.15) + (Social * 0.10)
        composite_score = (crypto_risk * 0.25) + \
                          (metals_risk * 0.25) + \
                          (macro_risk * 0.25) + \
                          (china_risk * 0.15) + \
                          (social_risk * 0.10)
        
        composite_score = round(composite_score, 2)
                          
        # Status Label
        status_label = "MODERATE"
        if composite_score < 0.2: status_label = "EXTREME LOW (BUY ALL)"
        elif composite_score < 0.3: status_label = "LOW (ACCUMULATE)"
        elif composite_score < 0.6: status_label = "MODERATE"
        elif composite_score < 0.7: status_label = "HIGH (WATCH FOR SELL)"
        elif composite_score < 0.85: status_label = "VERY HIGH (WARNING)"
        else: status_label = "EXTREME (SELL)"

        # -- 5. GENERATE REPORT --
        cycle_report += f"\nCOMPOSITE RISK: {composite_score:.2f} ({status_label})\n"
        cycle_report += "-"*50 + "\n"
        
        def get_signal(r):
            if r < 0.3: return "🟢 [BUY]"
            if r > 0.70: return "🔴 [SELL]"
            return "🟡 [HOLD]"
        
        cycle_report += "ASSET STATUS:\n"
        cycle_report += f"- BTC:    ${btc_meta['last_price']:.0f} | Risk: {round(btc_meta['last_risk'],2):.2f} {get_signal(round(btc_meta['last_risk'],2))}\n"
        cycle_report += f"- ETH:    ${eth_meta['last_price']:.0f} | Risk: {round(eth_meta['last_risk'],2):.2f} {get_signal(round(eth_meta['last_risk'],2))}\n"
        cycle_report += f"- GOLD:   ${gold_meta['last_price']:.1f} | Risk: {round(gold_meta['last_risk'],2):.2f} {get_signal(round(gold_meta['last_risk'],2))}\n"
        cycle_report += f"- SILVER: ${silver_meta['last_price']:.1f} | Risk: {round(silver_meta['last_risk'],2):.2f} {get_signal(round(silver_meta['last_risk'],2))}\n"
        cycle_report += f"- GDX:    ${gdx_meta['last_price']:.2f} | Risk: {round(gdx_meta['last_risk'],2):.2f} {get_signal(round(gdx_meta['last_risk'],2))}\n\n"
        
        cycle_report += "KEY METRICS:\n"
        cycle_report += f"- Gold/Silver Ratio: {gsr:.2f} ({'Accumulation' if gsr > 80 else 'Distribution'})\n"
        cycle_report += f"- ETH/BTC Ratio:     {eth_btc:.4f}\n"
        cycle_report += f"- Miner Lev (MLR):   {mlr:.2f}x ({'Undervalued' if mlr < 0.5 else 'Normal'})\n"
        cycle_report += f"- Yield-Gold Corr:   {yield_corr:.2f} ({'Broken' if yield_corr > -0.3 else 'Normal'})\n\n"
        
        cycle_report += "RISK BREAKDOWN:\n"
        cycle_report += f"- Crypto: {crypto_risk:.2f}\n"
        cycle_report += f"- Metals: {metals_risk:.2f}\n"
        cycle_report += f"- Macro:  {macro_risk:.2f}\n"
        cycle_report += f"- China:  {china_risk:.2f} (Est)\n"
        cycle_report += f"- Social: {social_risk:.2f} (Est)\n"

    except Exception as e:
        cycle_report += f"Error calculating cycle metrics: {e}\n"
        import traceback
        traceback.print_exc()
    
    cycle_report += "="*50 + "\n\n"
    
    context = {
        "gsr": locals().get('gsr', 0),
        "eth_btc": locals().get('eth_btc', 0),
        "mlr": locals().get('mlr', 0),
        "composite_score": locals().get('composite_score', 0)
    }
    return cycle_report, context

def main():
    ensure_dirs()
    setup_logging()
    print("Starting Institutional Analysis Run...")
    logging.info("Starting Institutional Analysis Run...")
    
    report_path = os.path.join(OUTPUT_DIR, "institutional_analysis_report.txt")
    
    # --- MACRO CYCLE ---
    cycle_text, macro_context = analyze_market_cycle()
    
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
        
        # Signal Logic
        signal_str = "🟢 [BUY]" if r < 0.3 else "🔴 [SELL]" if r > 0.70 else "🟡 [HOLD]"

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
