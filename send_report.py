import os
import smtplib
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime

# Load configuration
load_dotenv()

# --- CONFIGURATION ---
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
TO_EMAIL = "me@ianskea.com"

REPORT_PATH = "output/institutional_analysis_report.txt"

def run_analysis():
    print(f"[{datetime.now()}] Running Institutional Analysis...")
    try:
        # Runs the analysis script
        # Using the venv python if possible
        python_executable = "./venv/bin/python3" if os.path.exists("./venv/bin/python3") else "python3"
        result = subprocess.run([python_executable, "enhanced_main.py"], capture_output=True, text=True)
        if result.returncode != 0:
            print("Error running analysis:")
            print(result.stderr)
            return False
        return True
    except Exception as e:
        print(f"Critical error during analysis run: {e}")
        return False

def send_email():
    if not all([SMTP_USER, SMTP_PASS]):
        print("Error: SMTP_USER or SMTP_PASS not set in .env. Email skipped.")
        return

    print(f"[{datetime.now()}] Preparing email to {TO_EMAIL}...")
    
    if not os.path.exists(REPORT_PATH):
        print(f"Error: Report not found at {REPORT_PATH}")
        return

    with open(REPORT_PATH, 'r') as f:
        report_content = f.read()

    # Create the email
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = TO_EMAIL
    msg['Subject'] = f"Risk Bubble Institutional Report - {datetime.now().strftime('%Y-%m-%d')}"

    # Body
    body = "The latest Risk Bubble Intelligence analysis has completed. Find the summary below.\n\n"
    body += "-" * 60 + "\n\n"
    body += report_content
    
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect and send
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

if __name__ == "__main__":
    if run_analysis():
        send_email()
    else:
        print("Analysis failed. Email not sent.")
