"""
SMTP email sender for news digests.
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytz

from .models import SMTPConfig

logger = logging.getLogger(__name__)

TAIPEI_TZ = pytz.timezone('Asia/Taipei')
OUTPUT_DIR = Path(__file__).parent.parent / 'output'


def get_smtp_config_from_env() -> SMTPConfig:
    """Load SMTP configuration from environment variables."""
    # Support both naming conventions
    host = os.environ.get('SMTP_HOST') or os.environ.get('SMTP_SERVER', '')
    port = int(os.environ.get('SMTP_PORT', 465))
    user = os.environ.get('SMTP_USER') or os.environ.get('SMTP_USERNAME', '')
    password = os.environ.get('SMTP_PASSWORD', '')
    
    return SMTPConfig(
        host=host,
        port=port,
        user=user,
        password=password,
        use_ssl=(port == 465)
    )


def send_email(
    html_content: str,
    subject: str,
    recipient: str,
    smtp_config: SMTPConfig,
    sender_name: str = "News Digest"
) -> bool:
    """
    Send HTML email via SMTP.
    
    Args:
        html_content: HTML body content
        subject: Email subject
        recipient: Recipient email address
        smtp_config: SMTP configuration
        sender_name: Sender display name
    
    Returns:
        True on success, False on failure
    """
    if not all([smtp_config.host, smtp_config.user, smtp_config.password]):
        logger.error("SMTP configuration incomplete")
        return False
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{sender_name} <{smtp_config.user}>"
    msg['To'] = recipient
    
    # Plain text fallback
    text_content = "This email requires an HTML-capable email client."
    msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
    
    # HTML content
    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    try:
        if smtp_config.use_ssl:
            # SSL connection (port 465)
            with smtplib.SMTP_SSL(smtp_config.host, smtp_config.port) as server:
                server.login(smtp_config.user, smtp_config.password)
                server.send_message(msg)
        else:
            # STARTTLS connection (port 587)
            with smtplib.SMTP(smtp_config.host, smtp_config.port) as server:
                server.starttls()
                server.login(smtp_config.user, smtp_config.password)
                server.send_message(msg)
        
        logger.info(f"Email sent successfully to {recipient}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_digest_email() -> bool:
    """
    Send the daily digest email using environment configuration.
    
    Reads the rendered email HTML from output directory.
    """
    # Load configuration from environment
    smtp_config = get_smtp_config_from_env()
    recipient = os.environ.get('EMAIL_RECIPIENT', '')
    subject_prefix = os.environ.get('EMAIL_SUBJECT_PREFIX', '[News Digest]')
    
    if not recipient:
        logger.error("EMAIL_RECIPIENT not set")
        return False
    
    # Load email HTML
    email_html_path = OUTPUT_DIR / 'email_digest.html'
    if not email_html_path.exists():
        logger.error(f"Email HTML not found: {email_html_path}")
        return False
    
    html_content = email_html_path.read_text(encoding='utf-8')
    
    # Generate subject with date
    now = datetime.now(TAIPEI_TZ)
    date_str = now.strftime("%Y-%m-%d")
    subject = f"{subject_prefix} {date_str}"
    
    return send_email(
        html_content=html_content,
        subject=subject,
        recipient=recipient,
        smtp_config=smtp_config
    )


def send_error_notification(run_id: str, run_url: str) -> bool:
    """
    Send error notification email when pipeline fails.
    
    Args:
        run_id: GitHub Actions run ID
        run_url: URL to the workflow run
    
    Returns:
        True on success
    """
    smtp_config = get_smtp_config_from_env()
    recipient = os.environ.get('EMAIL_RECIPIENT', '')
    
    if not recipient or not smtp_config.host:
        logger.error("Cannot send error notification: missing configuration")
        return False
    
    now = datetime.now(TAIPEI_TZ)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; background: #f3efe6; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: #fff; border: 1px solid #e6e1d6; padding: 24px;">
        <h2 style="color: #c00; margin-top: 0;">⚠️ News Digest Pipeline Failed</h2>
        <p><strong>Time:</strong> {timestamp} (Asia/Taipei)</p>
        <p><strong>Run ID:</strong> {run_id}</p>
        <p><a href="{run_url}" style="color: #0f5499;">View Details on GitHub</a></p>
        <hr style="border: none; border-top: 1px solid #e6e1d6; margin: 20px 0;">
        <p style="font-size: 12px; color: #666;">
            Please check the GitHub Actions logs for error details.
            The digest was not generated or sent today.
        </p>
    </div>
</body>
</html>
"""
    
    subject = f"[News Digest] Pipeline Failed - {now.strftime('%Y-%m-%d')}"
    
    return send_email(
        html_content=html_content,
        subject=subject,
        recipient=recipient,
        smtp_config=smtp_config,
        sender_name="News Digest Alert"
    )
