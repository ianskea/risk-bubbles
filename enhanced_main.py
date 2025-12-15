
import os
import time
from datetime import datetime
from PIL import Image # For potential future image processing
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
IMG_DIR = os.path.join(OUTPUT_DIR, "charts")

def ensure_dirs():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    if not os.path.exists(IMG_DIR): os.makedirs(IMG_DIR)

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
    ax2.axhline(0.8, color='red', ls='--', alpha=0.5)
    ax2.axhline(0.2, color='green', ls='--', alpha=0.5)
    ax2.fill_between(df.index, 0.8, 1.0, color='red', alpha=0.1)
    ax2.fill_between(df.index, 0.0, 0.2, color='green', alpha=0.1)
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
    path = os.path.join(IMG_DIR, f"{ticker_symbol}_comprehensive.png")
    plt.savefig(path)
    plt.close()
    return path

def generate_ai_analysis(ticker, price, risk, metrics):
    if not client:
        return "AI Analysis not available (No API Key)"
        
    prompt = f"""
    Analyze {ticker}. Price: ${price:.2f}. Composite Risk Score: {risk:.2f} (0=Buy, 1=Sell).
    Validation Model Score: {metrics.get('score')}/100.
    Correlation: {metrics.get('correlation'):.2f}.
    
    Provide a professional institutional risk assessment. 
    Focus on whether the statistical model is trustworthy for this asset (based on validation score) 
    and what the current risk score implies.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"AI Error: {e}"

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
                          
        # Status Label
        status_label = "MODERATE"
        if composite_score < 0.2: status_label = "EXTREME LOW (BUY ALL)"
        elif composite_score < 0.4: status_label = "LOW (ACCUMULATE)"
        elif composite_score < 0.6: status_label = "MODERATE"
        elif composite_score < 0.75: status_label = "HIGH (SCALE OUT)"
        elif composite_score < 0.85: status_label = "VERY HIGH (WARNING)"
        else: status_label = "EXTREME (SELL)"

        # -- 5. GENERATE REPORT --
        cycle_report += f"\nCOMPOSITE RISK: {composite_score:.2f} ({status_label})\n"
        cycle_report += "-"*50 + "\n"
        
        def get_signal(r):
            if r < 0.3: return "🟢 [BUY]"
            if r > 0.75: return "🔴 [SELL]"
            return "🟡 [HOLD]"
        
        cycle_report += "ASSET STATUS:\n"
        cycle_report += f"- BTC:    ${btc_meta['last_price']:.0f} | Risk: {btc_meta['last_risk']:.2f} {get_signal(btc_meta['last_risk'])}\n"
        cycle_report += f"- ETH:    ${eth_meta['last_price']:.0f} | Risk: {eth_meta['last_risk']:.2f} {get_signal(eth_meta['last_risk'])}\n"
        cycle_report += f"- GOLD:   ${gold_meta['last_price']:.1f} | Risk: {gold_meta['last_risk']:.2f} {get_signal(gold_meta['last_risk'])}\n"
        cycle_report += f"- SILVER: ${silver_meta['last_price']:.1f} | Risk: {silver_meta['last_risk']:.2f} {get_signal(silver_meta['last_risk'])}\n"
        cycle_report += f"- GDX:    ${gdx_meta['last_price']:.2f} | Risk: {gdx_meta['last_risk']:.2f} {get_signal(gdx_meta['last_risk'])}\n\n"
        
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
    print("Starting Institutional Analysis Run...")
    
    report_path = os.path.join(OUTPUT_DIR, "institutional_analysis_report.txt")
    full_report = f"INSTITUTIONAL RISK REPORT - {datetime.now().strftime('%Y-%m-%d')}\n"
    full_report += "="*60 + "\n\n"
    
    # --- MACRO CYCLE ---
    cycle_text, macro_context = analyze_market_cycle()
    full_report += cycle_text
    
    for name, ticker in TICKERS.items():
        print(f"Processing {name}...")
        try:
            df, _, meta = analyze_asset(ticker)
            if df.empty: continue
            
            # Run Validation
            val_metrics = validate_model(df)
            
            # Generate Chart
            plot_comprehensive_analysis(name, ticker, df)
            
            # AI Insight
            ai_text = generate_ai_analysis(name, meta['last_price'], meta['last_risk'], val_metrics)
            
            # Cowen Framework Data
            cowen_section = ""
            if "bmsb_20w_sma" in meta:
                cowen_section = f"""
BEN COWEN FRAMEWORK ANALYSIS:
20W SMA (BMSB): ${meta['bmsb_20w_sma']:.2f}
21W EMA (BMSB): ${meta['bmsb_21w_ema']:.2f}
Status vs BMSB: {meta['status_bmsb']}

50W SMA (Bear Line): ${meta['sma_50w']:.2f}
Status vs 50W:  {meta['status_50w']}

200W SMA (Bottom): ${meta['sma_200w']:.2f}
"""

            # Macro Context Integration
            macro_note = ""
            # Silver Logic
            if ticker == "SI=F":
                gsr = macro_context.get('gsr', 0)
                if gsr > 80:
                    macro_note = f"\n[MACRO CONTEXT]: GSR is High ({gsr:.2f}). Silver is CHEAP vs Gold (Accumulation).\n"
                elif gsr < 50:
                    macro_note = f"\n[MACRO CONTEXT]: GSR is Low ({gsr:.2f}). Silver is EXPENSIVE vs Gold (Distribution Risk).\n"
            
            # Altcoin Logic (ETH, ADA, etc)
            if ticker in ["ETH-USD", "ADA-USD"]:
                eth_btc = macro_context.get('eth_btc', 0)
                if eth_btc < 0.05:
                     macro_note = f"\n[MACRO CONTEXT]: ETH/BTC Low ({eth_btc:.4f}). BTC Dominance High. Setup for Alt Rotation eventually.\n"
                elif eth_btc > 0.08:
                     macro_note = f"\n[MACRO CONTEXT]: ETH/BTC High ({eth_btc:.4f}). Alt Season Peaking? Caution.\n"

            # Signal Logic
            r = meta['last_risk']
            signal_str = "🟢 [BUY]" if r < 0.3 else "🔴 [SELL]" if r > 0.75 else "🟡 [HOLD]"

            # Report Section
            section = f"""
ASSET: {name} ({ticker})
Price: ${meta['last_price']:.2f}
RISK SCORE: {meta['last_risk']:.2f}  {signal_str}
{cowen_section}{macro_note}
Validation Reliability: {val_metrics.get('score', 0)}/100
(Correlation: {val_metrics.get('correlation', 0):.2f})

AI INSIGHT:
{ai_text}

--------------------------------------------------
"""
            full_report += section
            
            # Rate Limit
            time.sleep(2)
            
        except Exception as e:
            print(f"Error {name}: {e}")
            
    with open(report_path, "w") as f:
        f.write(full_report)
        
    print(f"\nDone. Report saved to {report_path}")

if __name__ == "__main__":
    main()
