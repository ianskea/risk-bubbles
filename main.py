import matplotlib.pyplot as plt
import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from risk_analyzer import fetch_data, calculate_log_regression_risk

# Load Environment Variables
load_dotenv()
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if DEEPSEEK_API_KEY:
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
else:
    client = None
    print("Warning: DEEPSEEK_API_KEY not found. Using standard rule-based reporting.")

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

def plot_risk_analysis(ticker_name: str, ticker_symbol: str, df):
    # ... (Plotting logic remains same but keeping imports clean)
    """
    Generates a chart with 2 subplots:
    1. Log Price with Regression Bands
    2. Risk Metric (0-1)
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
    
    # --- Plot 1: Price and Bands ---
    ax1.set_title(f"{ticker_name} ({ticker_symbol}) - Risk Analysis")
    ax1.plot(df.index, df['Close'], label='Price', color='black', linewidth=1)
    
    # Plot Bands
    ax1.plot(df.index, df['predicted_price'], '--', label='Fair Value (Reg)', color='orange', alpha=0.8)
    ax1.plot(df.index, df['top_band'], label='+2 StdDev', color='red', alpha=0.5)
    ax1.plot(df.index, df['bottom_band'], label='-2 StdDev', color='green', alpha=0.5)
    
    # Fill between bands
    ax1.fill_between(df.index, df['bottom_band'], df['top_band'], color='gray', alpha=0.1)
    
    ax1.set_yscale('log')
    ax1.set_ylabel('Price (Log Scale)')
    ax1.legend(loc='upper left')
    ax1.grid(True, which="both", ls="-", alpha=0.2)
    
    # --- Plot 2: Risk Metric ---
    ax2.set_title("Risk Metric (0-1)")
    ax2.plot(df.index, df['risk'], color='blue', linewidth=1)
    
    # Zones
    ax2.axhline(0.8, color='red', linestyle='--', alpha=0.5, label='High Risk (Sell)')
    ax2.axhline(0.2, color='green', linestyle='--', alpha=0.5, label='Low Risk (Buy)')
    ax2.axhline(0.5, color='gray', linestyle=':', alpha=0.5)
    
    # Fill zones
    ax2.fill_between(df.index, 0.8, 1.0, color='red', alpha=0.1)
    ax2.fill_between(df.index, 0.0, 0.2, color='green', alpha=0.1)
    
    ax2.set_ylabel('Risk Score')
    ax2.set_ylim(-0.1, 1.1)
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    # Save fig
    filename = os.path.join(OUTPUT_DIR, f"{ticker_symbol}_risk_bubble.png")
    plt.tight_layout()
    plt.savefig(filename)
    print(f"Saved chart to {filename}")
    plt.close()

def generate_traffic_light(risk):
    if risk < 0.4:
        return "ðŸŸ¢" # Green - Buy/Opportunity
    elif risk < 0.6:
        return "ðŸŸ¡" # Yellow - Neutral/Hold
    else:
        return "ðŸ”´" # Red - Sell/Risk

def generate_recommendation(ticker_name, price, risk):
    """
    Generates a textual analysis based on the risk score.
    Uses Gemini API if available, otherwise falls back to logic.
    """
    light = generate_traffic_light(risk)
    
    # 1. Try DeepSeek API
    if client:
        try:
            prompt = f"""
            You are a professional financial trading assistant using a Risk Bubble Analysis tool.
            
            Analyze the following asset data:
            - Asset: {ticker_name}
            - Current Price: ${price:,.2f}
            - Risk Score (0-1 Normalized): {risk:.2f}
            - Traffic Light Indicator: {light}
            
            Methodology:
            - Risk 0.5 = Fair Value Trend.
            - Risk > 0.8 = Statistical "Bubble" / Overvalued (Sell Zone).
            - Risk < 0.2 = Statistical Undervalued / Trend Bottom (Buy Zone).
            - Indicator: ðŸŸ¢=Good/Buy, ðŸŸ¡=Neutral, ðŸ”´=Risk/Sell
            
            Task:
            Write a short, punchy 3-sentence analysis for a user looking to Dollar Cost Average (DCA).
            Give a specific recommendation: "Strong Buy", "Accumulate", "Hold", "Take Profit", or "Sell".
            Start your response with the Traffic Light Emoji {light} provided.
            Be decisive. Do not use markdown bolding in the text body, just plain text.
            """
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150
            )
            content = response.choices[0].message.content.strip()
            return f"\nAsset: {ticker_name}\nPrice: ${price:,.2f} | Risk: {risk:.2f} {light}\nAI Analysis:\n{content}\n------------------------------------------------"
        except Exception as e:
            print(f"DeepSeek API Error: {e}. Falling back to standard reporting.")

    # 2. Fallback Rule-Based Logic
    if risk < 0.2:
        status = f"{light} EXTREME OPPORTUNITY"
        action = "Strong Buy (Heavy DCA)"
        details = "Price is significantly below fair value trend. Historical bottom zone."
    elif risk < 0.4:
        status = f"{light} OPPORTUNITY"
        action = "Buy (Standard DCA)"
        details = "Price is below fair value. Good area to accumulate."
    elif risk < 0.6:
        status = f"{light} FAIR VALUE"
        action = "Hold / Light DCA"
        details = "Price is near fair value trend. Market is in equilibrium."
    elif risk < 0.8:
        status = f"{light} ELEVATED RISK"
        action = "Caution / Take Profit"
        details = "Price is above fair value. Upside may be limited."
    else:
        status = f"{light} BUBBLE TERRITORY"
        action = "Sell / Hedge"
        details = "Price is significantly extended. High probability of mean reversion."
    
    report = f"""
Asset: {ticker_name}
Price: ${price:,.2f}
Risk Score: {risk:.2f} {light}
Status: {status}
Recommendation: {action}
Analysis: {details}
------------------------------------------------"""
    return report

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    report_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    full_report = f"--- INTELLIGENT RISK ANALYSIS REPORT ---\nReport Date: {report_date}\n"
    
    for name, ticker in TICKERS.items():
        try:
            print(f"\nProcessing {name} ({ticker})...")
            data = fetch_data(ticker)
            risk_df = calculate_log_regression_risk(data)
            
            # Print current stats
            current = risk_df.iloc[-1]
            price = current['Close']
            risk = current['risk']
            
            print(f"Current Price: {price:.2f}")
            print(f"Current Risk:  {risk:.4f}")
            
            # Generate Report
            item_report = generate_recommendation(name, price, risk)
            full_report += f"\n{item_report}"
            
            plot_risk_analysis(name, ticker, risk_df)
            
            # Rate Limit Protection
            import time
            time.sleep(5) # Wait 5 seconds between API calls to avoid 429
            
        except Exception as e:
            print(f"Error processing {name}: {e}")
            full_report += f"\n\nAsset: {name}\nError: Could not process data ({e})\n------------------------------------------------"

    # Save Report
    report_path = os.path.join(OUTPUT_DIR, "analysis_report.txt")
    with open(report_path, "w") as f:
        f.write(full_report)
    
    print(f"\nAnalysis Report saved to {report_path}")
    print(full_report)

if __name__ == "__main__":
    main()