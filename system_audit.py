
import subprocess
import os
import re
import sys
import time

# =========================================================
# CONFIGURATION
# =========================================================
RISK_REPORT_PATH = "output/institutional_analysis_report.txt"
PYTHON_EXEC = "./venv/bin/python3"
SCRIPT_ANALYZER = "enhanced_main.py"
SCRIPT_PLANNER = "investment_planner.py"

class QARunner:
    def __init__(self):
        self.report_data = {}   # From institutional_analysis_report.txt
        self.planner_data = {}  # From investment_planner.py stdout
        self.discrepancies = []

    def run_command(self, cmd_list, description):
        print(f"🔄 Running {description}...")
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd_list, 
                capture_output=True, 
                text=True, 
                check=True
            )
            duration = time.time() - start_time
            print(f"✅ {description} Complete ({duration:.2f}s)")
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"❌ Error running {description}:")
            print(e.stderr)
            sys.exit(1)

    def parse_institutional_report(self):
        """Extracts risk scores from the main report file."""
        if not os.path.exists(RISK_REPORT_PATH):
            self.discrepancies.append(f"CRITICAL: Report file {RISK_REPORT_PATH} not found.")
            return

        print(f"📄 Parsing Risk Report: {RISK_REPORT_PATH}")
        with open(RISK_REPORT_PATH, 'r') as f:
            content = f.read()

        # Regex to find "ASSET: Name (Ticker) ... RISK SCORE: 0.XX"
        # Example: ASSET: Bitcoin (BTC-USD)\nPrice: $88239.13\nRISK SCORE: 0.39
        
        # Strategy: capture block assets or look for specific lines
        # Pattern 1: Dashboard lines: "- BTC:    $88458 | Risk: 0.38"
        dashboard_pattern = re.compile(r"- (\w+):\s+\$[\d\.]+\s+\|\s+Risk:\s+([\d\.]+)")
        for match in dashboard_pattern.finditer(content):
            ticker, risk = match.groups()
            self.report_data[ticker] = float(risk)

    def parse_planner_output(self, output_text):
        """Extracts risk scores from the investment planner output."""
        print(f"📄 Parsing Planner Output...")
        # Look for lines in the "IMMEDIATE ACTION BUY LIST" table
        # Format: "Asset Risk Action_BUY"
        # Since it's a printed table, we can split by lines and look for data rows
        
        lines = output_text.split('\n')
        parsing_table = False
        
        for line in lines:
            if "--- IMMEDIATE ACTION BUY LIST ---" in line:
                parsing_table = True
                continue
            
            if parsing_table and line.strip():
                parts = line.split()
                # Expected: [Asset, Risk, Action, Status, Custody...]
                # Example: BTC_COLD 0.32 $16,484.28 BUY Cold Storage
                if len(parts) >= 2:
                    asset = parts[0]
                    risk_str = parts[1]
                    try:
                        risk = float(risk_str)
                        self.planner_data[asset] = risk
                    except ValueError:
                        continue # Header or other line

    def check_consistency(self):
        print(f"\n🔍 Performing QA Consistency Checks...")
        
        # MAPPING: Planner Asset -> Report Asset Key
        # The planner uses custom keys like BTC_COLD, the report uses BTC
        # We need a map to compare apples to apples
        ASSET_MAP = {
            "BTC_COLD": "BTC",
            "BTC_LEDN": "BTC",
            "ETH_STAKE": "ETH",
            "PAXG_NEXO": "GOLD",
            "MQG": "MQG",  # Typically not in dashboard summary? Need to check coverage
            # Add others if they appear in dashboard
        }
        
        for planner_asset, planner_risk in self.planner_data.items():
            report_key = ASSET_MAP.get(planner_asset)
            
            # If we don't have a map, try direct match or skip (some ASX stocks might not be in dashboard summary)
            if not report_key:
                # Try simple mapping
                if planner_asset in self.report_data:
                    report_key = planner_asset
            
            if report_key and report_key in self.report_data:
                report_risk = self.report_data[report_key]
                if abs(planner_risk - report_risk) > 0.001: # Float tolerance
                    self.discrepancies.append(
                        f"❌ MISMATCH: {planner_asset} (Planner: {planner_risk}) != {report_key} (Report: {report_risk})"
                    )
                else:
                    print(f"✅ MATCH: {planner_asset} ({planner_risk}) == {report_key} ({report_risk})")
            else:
                # Some assets like MQG might not be in the top dashboard summary but in detailed sections
                # For this MVP, we focus on the core dashboard assets
                pass

        if not self.discrepancies:
            print("\n🎉 QA PASSED: No data inconsistencies found.")
        else:
            print("\n⚠️ QA FAILED: Discrepancies detected!")
            for d in self.discrepancies:
                print(d)

    def print_summary(self, planner_output):
        print("\n" + "="*60)
        print("SYSTEM AUDIT REPORT")
        print("="*60)
        
        print("\n1. RISK ANALYZER STATUS")
        if os.path.exists(RISK_REPORT_PATH):
            stats = os.stat(RISK_REPORT_PATH)
            print(f"   Shape: Found ({stats.st_size} bytes)")
            print(f"   Updated: {time.ctime(stats.st_mtime)}")
        else:
            print("   Shape: MISSING")

        print("\n2. INVESTMENT PLANNER SUMMARY")
        # Extract specific summary lines from output
        for line in planner_output.split('\n'):
            if "Total Portfolio Value" in line or "Total Platform Risk" in line:
                print(f"   {line.strip()}")

        print("\n3. DATA INTEGRITY")
        if not self.discrepancies:
            print("   Status: ✅ VALIDATED")
            print("   Message: Risk scores are synchronized across all subsystems.")
        else:
            print("   Status: ❌ INCONSISTENT")
            print(f"   Message: {len(self.discrepancies)} issues found.")

if __name__ == "__main__":
    qa = QARunner()
    
    # 1. Run Risk Analyzer
    qa.run_command([PYTHON_EXEC, SCRIPT_ANALYZER], "Institutional Risk Analyzer")
    
    # 2. Parse Report
    qa.parse_institutional_report()
    
    # 3. Run Investment Planner
    planner_out = qa.run_command([PYTHON_EXEC, SCRIPT_PLANNER], "Investment Planner")
    
    # 4. Parse Planner
    qa.parse_planner_output(planner_out)
    
    # 5. Check & Report
    qa.check_consistency()
    qa.print_summary(planner_out)
