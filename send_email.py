"""
Email Sender - Sends the daily report via Gmail SMTP
"""

import os
import glob
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your-email@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your-app-password")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "your-email@gmail.com")

def find_latest_report():
    export_dir = "./exports"
    files = glob.glob(os.path.join(export_dir, "pharma_leads_*.xlsx"))
    if not files:
        return None
    return max(files, key=os.path.getctime)

def send_email():
    report_path = find_latest_report()

    if not report_path:
        print("No report found. Sending alert.")
        subject = f"Pharma Pipeline Alert - {datetime.now().strftime('%Y-%m-%d')}"
        body = "No report was generated today. Please check the pipeline logs."
    else:
        print(f"Sending report: {report_path}")
        subject = f"Daily Pharma Leads Report - {datetime.now().strftime('%Y-%m-%d')}"
        body = f"Your daily pharma leads report is attached.\n\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    if report_path:
        with open(report_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {os.path.basename(report_path)}",
        )
        msg.attach(part)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)

    print("Email sent successfully!")

if __name__ == "__main__":
    send_email()
