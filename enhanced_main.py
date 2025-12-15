
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

def main():
    ensure_dirs()
    print("Starting Institutional Analysis Run...")
    
    report_path = os.path.join(OUTPUT_DIR, "institutional_analysis_report.txt")
    full_report = f"INSTITUTIONAL RISK REPORT - {datetime.now().strftime('%Y-%m-%d')}\n"
    full_report += "="*60 + "\n\n"
    
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

            # Report Section
            section = f"""
ASSET: {name} ({ticker})
Price: ${meta['last_price']:.2f}
RISK SCORE: {meta['last_risk']:.2f}  [{'BUY' if meta['last_risk']<0.3 else 'SELL' if meta['last_risk']>0.75 else 'HOLD'}]
{cowen_section}
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
