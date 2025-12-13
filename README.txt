# Risk Bubble Analysis Tool

A Python tool that analyzes and visualizes "Risk Bubbles" for Bitcoin, Gold, Silver, and ASX shares. It calculates a normalized risk metric (0-1) based on Logarithmic Regression and Moving Average extensions to assist in Dollar Cost Averaging (DCA) decisions.

## Features
- Fetches historical market data using `yfinance`.
- Calculates a "Fair Value" trend using Logarithmic Regression.
- Visualizes Price vs Risk with standard deviation bands.
- Generates an "Intelligent Investment Analysis Report" with buy/sell recommendations.

## Installation

1. **Prerequisites**: Python 3.9+
2. **Clone/Navigate** to the project directory:
   ```bash
   cd /Users/ianskea/Sites/risk-bubbles
   ```
3. **Set up Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Configuration**:
   Copy the example environment file (if you plan to extend with external APIs):
   ```bash
   cp .env.example .env
   ```
   *Note: Current version runs locally without an API key, but the structure is ready for future AI integration.*

## Usage

Run the main script to generate charts and the analysis report:

```bash
./venv/bin/python3 main.py
```

### Output
- **Charts**: Saved in `output/*.png`.
- **Report**: Saved in `output/analysis_report.txt`.

## Risk Metric Interpretation
- **< 0.2 (Green)**: Low Risk / Strong Buy Zone.
- **> 0.8 (Red)**: High Risk / Sell Zone.
- **0.4 - 0.6**: Fair Value / Neutral.

## Disclaimer
This tool is for educational purposes only. Not financial advice.
