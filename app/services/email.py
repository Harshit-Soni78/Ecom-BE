import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Email Configuration from environment variables
def get_email_config():
    return {
        "SMTP_HOST": os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
        "SMTP_PORT": int(os.environ.get('SMTP_PORT', '587')),
        "SMTP_USERNAME": os.environ.get('SMTP_USERNAME', 'support@amolias.com'),
        "SMTP_PASSWORD": os.environ.get('SMTP_PASSWORD', ''),
        "SMTP_FROM_EMAIL": os.environ.get('SMTP_FROM_EMAIL', 'support@amolias.com'),
        "SMTP_FROM_NAME": os.environ.get('SMTP_FROM_NAME', 'Amorlias Mart'),
        "EMAIL_ENABLED": os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true'
    }

def send_email(to_email: str, subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    """
    Send an email using SMTP.
    Falls back to console logging if EMAIL_ENABLED is False or SMTP credentials are not configured.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_body: HTML content of the email
        text_body: Plain text content (optional, defaults to stripped HTML)
    
    Returns:
        bool: True if email was sent successfully (or logged), False otherwise
    """
    config = get_email_config()
    
    try:
        # Console logging for development/testing
        if not config["EMAIL_ENABLED"] or not config["SMTP_PASSWORD"]:
            print("=" * 60)
            print(f"FROM: {config['SMTP_FROM_EMAIL']}")
            print(f"TO: {to_email}")
            print(f"SUBJECT: {subject}")
            print("-" * 60)
            print(html_body if not text_body else text_body)
            print("=" * 60)
            logger.info(f"Email logged to console (EMAIL_ENABLED={config['EMAIL_ENABLED']})")
            return True
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{config['SMTP_FROM_NAME']} <{config['SMTP_FROM_EMAIL']}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add text and HTML parts
        if text_body:
            part1 = MIMEText(text_body, 'plain')
            msg.attach(part1)
        
        part2 = MIMEText(html_body, 'html')
        msg.attach(part2)
        
        # Send email via SMTP
        with smtplib.SMTP(config['SMTP_HOST'], config['SMTP_PORT']) as server:
            server.starttls()
            server.login(config['SMTP_USERNAME'], config['SMTP_PASSWORD'])
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        # Still log to console as fallback
        print("=" * 60)
        print(f"EMAIL SEND FAILED - Logging to console instead")
        print(f"FROM: {config['SMTP_FROM_EMAIL']}")
        print(f"TO: {to_email}")
        print(f"SUBJECT: {subject}")
        print("-" * 60)
        print(html_body if not text_body else text_body)
        print("=" * 60)
        return False


def send_temporary_password_email(to_email: str, name: str, temporary_password: str, is_registration: bool = False) -> bool:
    """
    Send temporary password email for registration or password reset.
    
    Args:
        to_email: Recipient email address
        name: User's name
        temporary_password: The temporary password to send
        is_registration: True if this is for registration, False for password reset
    
    Returns:
        bool: True if email was sent successfully
    """
    if is_registration:
        subject = "Welcome to Amorlias Mart - Your Temporary Password"
        greeting = f"Welcome to Amorlias Mart, {name}!"
        message = """
        <p>Your account has been created successfully. We've generated a temporary password for you.</p>
        <p><strong>Note:</strong> If you're having trouble with OTP verification, you can use this temporary password to log in directly.</p>
        """
    else:
        subject = "Amorlias Mart - Password Reset"
        greeting = f"Hello {name},"
        message = """
        <p>You requested a password reset for your Amorlias Mart account.</p>
        <p>We've generated a new temporary password for you.</p>
        """
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 5px; margin-top: 20px; }}
            .password-box {{ background-color: #fff; border: 2px solid #4CAF50; padding: 15px; margin: 20px 0; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 2px; }}
            .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #666; }}
            .support {{ background-color: #e3f2fd; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Amorlias Mart</h1>
            </div>
            <div class="content">
                <h2>{greeting}</h2>
                {message}
                
                <div class="password-box">
                    {temporary_password}
                </div>
                
                <div class="warning">
                    <strong>⚠️ Important:</strong> For security reasons, please change this password after logging in.
                </div>
                
                <div class="support">
                    <h3>Need Help?</h3>
                    <p>If you're experiencing issues with OTP verification or have any questions, please contact our support team:</p>
                    <p><strong>Email:</strong> support@amolias.com</p>
                    <p>We're here to help you get started!</p>
                </div>
            </div>
            <div class="footer">
                <p>This is an automated email from Amorlias Mart. Please do not reply to this email.</p>
                <p>&copy; 2024 Amorlias Mart. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
{greeting}

{message.replace('<p>', '').replace('</p>', '').replace('<strong>', '').replace('</strong>', '')}

Your Temporary Password: {temporary_password}

IMPORTANT: For security reasons, please change this password after logging in.

Need Help?
If you're experiencing issues with OTP verification or have any questions, please contact our support team at support@amolias.com

---
This is an automated email from Amorlias Mart. Please do not reply to this email.
© 2024 Amorlias Mart. All rights reserved.
    """
    
    return send_email(to_email, subject, html_body, text_body)


def send_otp_email(to_email: str, phone: str, otp: str) -> bool:
    """
    Send OTP verification email with fallback instructions.
    
    Args:
        to_email: Recipient email address
        phone: User's phone number
        otp: The OTP code to send
    
    Returns:
        bool: True if email was sent successfully
    """
    subject = "Amorlias Mart - Your Verification Code"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
            .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 5px; margin-top: 20px; }}
            .otp-box {{ background-color: #fff; border: 2px solid #4CAF50; padding: 20px; margin: 20px 0; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; }}
            .info {{ background-color: #e3f2fd; padding: 15px; margin: 20px 0; border-radius: 5px; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Amorlias Mart</h1>
            </div>
            <div class="content">
                <h2>Your Verification Code</h2>
                <p>Please use the following OTP to verify your phone number ({phone}):</p>
                
                <div class="otp-box">
                    {otp}
                </div>
                
                <p><strong>This code will expire in 10 minutes.</strong></p>
                
                <div class="info">
                    <h3>OTP Not Working?</h3>
                    <p>If you're having trouble with OTP verification, you can:</p>
                    <ul>
                        <li>Request a temporary password during registration</li>
                        <li>Use the "Forgot Password" option to receive a temporary password via email</li>
                        <li>Contact our support team at <strong>support@amolias.com</strong></li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>If you didn't request this code, please ignore this email.</p>
                <p>&copy; 2024 Amorlias Mart. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
Amorlias Mart - Your Verification Code

Please use the following OTP to verify your phone number ({phone}):

{otp}

This code will expire in 10 minutes.

OTP Not Working?
If you're having trouble with OTP verification, you can:
- Request a temporary password during registration
- Use the "Forgot Password" option to receive a temporary password via email
- Contact our support team at support@amolias.com

---
If you didn't request this code, please ignore this email.
© 2024 Amorlias Mart. All rights reserved.
    """
    
    return send_email(to_email, subject, html_body, text_body)


def send_order_cancelled_email(to_email: str, order_number: str, reason: str, refund_amount: float) -> bool:
    """
    Send order cancellation email.
    
    Args:
        to_email: Recipient email address
        order_number: Order number
        reason: Cancellation reason
        refund_amount: Refund amount
    
    Returns:
        bool: True if email was sent successfully
    """
    subject = f"Amorlias Mart - Order #{order_number} Cancelled"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #f44336; color: white; padding: 20px; text-align: center; }}
            .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 5px; margin-top: 20px; }}
            .details {{ background-color: #fff; border-left: 4px solid #f44336; padding: 15px; margin: 20px 0; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Order Cancelled</h1>
            </div>
            <div class="content">
                <h2>Order #{order_number}</h2>
                <p>Your order #{order_number} has been cancelled.</p>
                
                <div class="details">
                    <p><strong>Reason:</strong> {reason}</p>
                    <p><strong>Refund Amount:</strong> ₹{refund_amount}</p>
                    <p><strong>Refund Timeline:</strong> 3-5 business days to your original payment method.</p>
                </div>
                
                <p>If you have any questions, please contact our support team at support@amolias.com</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 Amorlias Mart. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = f"""
Amorlias Mart - Order #{order_number} Cancelled

Your order #{order_number} has been cancelled.

Reason: {reason}
Refund Amount: ₹{refund_amount}
Refund Timeline: 3-5 business days to your original payment method.

If you have any questions, please contact our support team at support@amolias.com

---
© 2024 Amorlias Mart. All rights reserved.
    """
    
    return send_email(to_email, subject, html_body, text_body)
