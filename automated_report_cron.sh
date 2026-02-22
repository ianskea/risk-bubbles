#!/bin/bash
# automated_report_cron.sh

# Navigate to the project directory
cd /Users/ianskea/Sites/risk-bubbles

# Run the macOS notifier script using the venv
./venv/bin/python3 macos_notifier.py >> logs/cron_output.log 2>&1

# Also run the email report script
./venv/bin/python3 send_report.py >> logs/cron_output.log 2>&1
