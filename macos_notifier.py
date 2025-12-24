import os
import subprocess
from datetime import datetime
import re

REPORT_PATH = "output/institutional_analysis_report.txt"

def trigger_macos_notification(title, message):
    """Triggers a native macOS desktop notification."""
    cmd = f'osascript -e \'display notification "{message}" with title "{title}" sound name "Glass"\''
    subprocess.run(cmd, shell=True)

def run_analysis():
    print(f"[{datetime.now()}] Running Institutional Analysis (this can take 15-20 min)...")
    python_executable = "./venv/bin/python3" if os.path.exists("./venv/bin/python3") else "python3"
    
    # Run and stream output to console so user sees progress
    process = subprocess.Popen(
        [python_executable, "enhanced_main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    for line in process.stdout:
        print(f"  {line.strip()}")
    
    process.wait()
    return process.returncode == 0

def parse_signals():
    """Extracts a summary of BUY/SELL signals from the report."""
    if not os.path.exists(REPORT_PATH):
        return "Analysis complete."

    with open(REPORT_PATH, 'r') as f:
        content = f.read()

    # Find the Validated Signals section
    validated_section = re.search(r"SECTION 1: ACTIONABLE INSTITUTIONAL SIGNALS.*?\n(.*?)\nSECTION 2", content, re.DOTALL)
    if not validated_section:
        return "No actionable signals found."

    signals = validated_section.group(1)
    
    # Extract asset names and signals (e.g. BTC-USD: 🟢 [BUY])
    findings = []
    # Pattern to match: ASSET: Bitcoin (BTC-USD) \n Price ... \n RISK SCORE: 0.32 🟢 [BUY]
    matches = re.findall(r"ASSET: .*?\((.*?)\).*?RISK SCORE: .*?([🟢🔴].*?)\n", signals, re.DOTALL)
    
    for ticker, signal in matches:
        clean_signal = signal.replace("[", "").replace("]", "")
        findings.append(f"{ticker}: {clean_signal}")

    if not findings:
        return "Analysis finished. See report for details."
    
    return " | ".join(findings[:3]) # Limit to top 3 for the notification banner

def open_report():
    """Opens the report in the default system text editor."""
    if os.path.exists(REPORT_PATH):
        subprocess.run(["open", REPORT_PATH])

if __name__ == "__main__":
    if run_analysis():
        summary = parse_signals()
        trigger_macos_notification("Risk Bubble Intelligence", summary)
        open_report()
        print(f"✅ Analysis complete: {summary}")
    else:
        trigger_macos_notification("Risk Bubble Intelligence", "⚠️ Analysis Failed. Check logs.")
        print("❌ Analysis failed.")
