import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime

# Load configuration
load_dotenv()

# --- CONFIGURATION ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER")
# Strip single quotes if present (common copy-paste error)
SMTP_PASS = os.getenv("SMTP_PASS").strip("'").strip('"')
TO_EMAIL = os.getenv("TO_EMAIL")

def test_connection():
    if not all([SMTP_USER, SMTP_PASS, TO_EMAIL]):
        print(f"❌ Error: Missing configuration. User: {SMTP_USER}, Pass: {'SET' if SMTP_PASS else 'MISSING'}, To: {TO_EMAIL}")
        return

    print(f"[{datetime.now()}] Testing SMTP connection for {SMTP_USER}...")
    
    # Create a simple test email
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = TO_EMAIL
    msg['Subject'] = "🚀 Risk Bubble SMTP Test"

    body = f"Connection test successful at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.\n\nYour Risk Bubble automated reports are now ready for delivery."
    msg.attach(MIMEText(body, 'plain'))

    try:
        print(f"Connecting to {SMTP_SERVER}:{SMTP_PORT}...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.set_debuglevel(1) # See the conversation with the server
        server.starttls()
        print("Logging in...")
        server.login(SMTP_USER, SMTP_PASS)
        print("Sending test message...")
        server.send_message(msg)
        server.quit()
        print("\n✅ SMTP Connection Successful! You should receive a test email shortly.")
    except Exception as e:
        print(f"\n❌ SMTP Connection Failed: {e}")

if __name__ == "__main__":
    test_connection()
