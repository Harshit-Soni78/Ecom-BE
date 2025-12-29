from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import os

from app.db.session import get_db
from app.api.v1.endpoints.auth import admin_required
from app.models.settings import Settings
from app.schemas.settings import SettingsUpdate
from app.services import email as email_utils

router = APIRouter()

@router.get("/admin/settings/email")
def get_email_settings(admin: dict = Depends(admin_required)):
    return {
        "email_enabled": os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true',
        "smtp_host": os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
        "smtp_port": int(os.environ.get('SMTP_PORT', '587')),
        "smtp_username": os.environ.get('SMTP_USERNAME', ''),
        "smtp_from_email": os.environ.get('SMTP_FROM_EMAIL', ''),
        "smtp_from_name": os.environ.get('SMTP_FROM_NAME', 'BharatBazaar Support'),
        "smtp_password_configured": bool(os.environ.get('SMTP_PASSWORD', ''))
    }

@router.post("/admin/settings/email/test")
def test_email_settings(data: dict, admin: dict = Depends(admin_required)):
    test_email = data.get("email", admin.get("email", "test@example.com"))
    
    otp_result = email_utils.send_otp_email(test_email, "9876543210", "123456")
    
    temp_pass_result = email_utils.send_temporary_password_email(
        test_email, admin.get("name", "Test User"), "TempPass123", True
    )
    
    return {
        "message": "Email test completed",
        "otp_email_sent": otp_result,
        "temp_password_email_sent": temp_pass_result,
        "test_email": test_email,
        "note": "Check server console logs if EMAIL_ENABLED=false"
    }

@router.put("/admin/settings")
def update_settings(data: SettingsUpdate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    settings = db.query(Settings).filter(Settings.type == "business").first()
    if not settings:
        settings = Settings(
            type="business",
            company_name="Amorlias International Pvt Ltd"
        )
        db.add(settings)
    
    if data.business_name is not None:
        settings.business_name = data.business_name
    if data.company_name is not None:
        settings.company_name = data.company_name
    if data.gst_number is not None:
        settings.gst_number = data.gst_number
    if data.phone is not None:
        settings.phone = data.phone
    if data.email is not None:
        settings.email = data.email
    if data.address is not None:
        settings.address = data.address
    if data.logo_url is not None:
        settings.logo_url = data.logo_url
    if data.favicon_url is not None:
        settings.favicon_url = data.favicon_url
    
    social_links = dict(settings.social_links) if settings.social_links else {}
    if data.facebook_url is not None:
        social_links["facebook_url"] = data.facebook_url
    if data.instagram_url is not None:
        social_links["instagram_url"] = data.instagram_url
    if data.twitter_url is not None:
        social_links["twitter_url"] = data.twitter_url
    if data.youtube_url is not None:
        social_links["youtube_url"] = data.youtube_url
    if data.whatsapp_number is not None:
        social_links["whatsapp_number"] = data.whatsapp_number
    settings.social_links = social_links
    
    configs = dict(settings.configs) if settings.configs else {}
    if hasattr(data, 'enable_gst_billing'):
        configs["enable_gst_billing"] = data.enable_gst_billing
    if data.default_gst_rate is not None:
        configs["default_gst_rate"] = data.default_gst_rate
    if data.invoice_prefix is not None:
        configs["invoice_prefix"] = data.invoice_prefix
    if data.order_prefix is not None:
        configs["order_prefix"] = data.order_prefix
    if data.upi_id is not None:
        configs["upi_id"] = data.upi_id
    settings.configs = configs
    
    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    
    return {"message": "Settings updated successfully"}

@router.get("/settings/public")
def get_public_settings(db: Session = Depends(get_db)):
    settings = db.query(Settings).filter(Settings.type == "business").first()
    
    if not settings:
        return {
            "business_name": "BharatBazaar",
            "company_name": "Amorlias International Pvt Ltd",
            "logo_url": "",
            "favicon_url": "",
            "phone": "",
            "email": "",
            "address": {},
            "gst_number": "",
            "facebook_url": "",
            "instagram_url": "",
            "twitter_url": "",
            "youtube_url": "",
            "whatsapp_number": ""
        }
    
    social_links = settings.social_links or {}
    
    return {
        "business_name": settings.business_name or "BharatBazaar",
        "company_name": settings.company_name or "Amorlias International Pvt Ltd",
        "logo_url": settings.logo_url or "",
        "favicon_url": settings.favicon_url or "",
        "phone": settings.phone or "",
        "email": settings.email or "",
        "address": settings.address or {},
        "gst_number": settings.gst_number or "",
        "facebook_url": social_links.get("facebook_url", ""),
        "instagram_url": social_links.get("instagram_url", ""),
        "twitter_url": social_links.get("twitter_url", ""),
        "youtube_url": social_links.get("youtube_url", ""),
        "whatsapp_number": social_links.get("whatsapp_number", "")
    }

@router.get("/admin/settings")
def get_admin_settings(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    settings = db.query(Settings).filter(Settings.type == "business").first()
    
    if not settings:
        default_settings = Settings(
            type="business",
            business_name="BharatBazaar",
            company_name="Amorlias International Pvt Ltd",
            phone="9999999999",
            email="info@bharatbazaar.com",
            configs={
                "enable_gst_billing": True,
                "default_gst_rate": 18.0,
                "invoice_prefix": "INV",
                "order_prefix": "ORD"
            }
        )
        db.add(default_settings)
        db.commit()
        db.refresh(default_settings)
        settings = default_settings
    
    configs = settings.configs or {}
    social_links = settings.social_links or {}
    
    return {
        "business_name": settings.business_name or "BharatBazaar",
        "company_name": settings.company_name or "",
        "gst_number": settings.gst_number or "",
        "phone": settings.phone or "",
        "email": settings.email or "",
        "address": settings.address or {},
        "logo_url": settings.logo_url or "",
        "favicon_url": settings.favicon_url or "",
        "enable_gst_billing": configs.get("enable_gst_billing", True),
        "default_gst_rate": configs.get("default_gst_rate", 18.0),
        "invoice_prefix": configs.get("invoice_prefix", "INV"),
        "order_prefix": configs.get("order_prefix", "ORD"),
        "upi_id": configs.get("upi_id", ""),
        "facebook_url": social_links.get("facebook_url", ""),
        "instagram_url": social_links.get("instagram_url", ""),
        "twitter_url": social_links.get("twitter_url", ""),
        "youtube_url": social_links.get("youtube_url", ""),
        "whatsapp_number": social_links.get("whatsapp_number", "")
    }
