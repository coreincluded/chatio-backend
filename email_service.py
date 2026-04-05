"""Email service for Chatio using Gmail SMTP."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import get_settings

settings = get_settings()

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = settings.smtp_user      # chatioinfo@gmail.com
SMTP_PASSWORD = settings.smtp_pass  # Gmail App Password


def send_reset_email(to_email: str, reset_token: str, base_url: str = "http://localhost:3000") -> bool:
    """Send password-reset email with a link containing the token."""
    reset_link = f"{base_url}/auth/login?reset_token={reset_token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Chatio — Reset Your Password"
    msg["From"] = f"Chatio <{SMTP_USER}>"
    msg["To"] = to_email

    text = f"""Hi,

You requested a password reset for your Chatio account.

Click the link below to set a new password (expires in 15 minutes):
{reset_link}

If you did not request this, you can safely ignore this email.

— Chatio Team
"""

    html = f"""<div style="font-family:sans-serif;max-width:480px;margin:0 auto">
  <h2 style="color:#2563eb">Chatio</h2>
  <p>You requested a password reset for your Chatio account.</p>
  <p><a href="{reset_link}"
        style="display:inline-block;padding:12px 24px;background:#2563eb;color:#fff;
               border-radius:8px;text-decoration:none;font-weight:600">
     Reset Password
  </a></p>
  <p style="color:#666;font-size:13px">This link expires in 15 minutes.<br>
     If you did not request this, ignore this email.</p>
</div>"""

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[email_service] Failed to send reset email: {e}")
        return False
