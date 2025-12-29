from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class CourierProviderCreate(BaseModel):
    name: str
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    webhook_url: Optional[str] = None
    tracking_url_template: Optional[str] = None
    is_active: bool = True
    priority: int = 1

class PaymentGatewayCreate(BaseModel):
    name: str
    merchant_id: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    is_test_mode: bool = True
    is_active: bool = True

class SettingsUpdate(BaseModel):
    business_name: Optional[str] = None
    company_name: Optional[str] = None  # Company name for invoices and labels
    gst_number: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    enable_gst_billing: bool = True
    default_gst_rate: float = 18.0
    invoice_prefix: str = "INV"
    order_prefix: str = "ORD"
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    twitter_url: Optional[str] = None
    youtube_url: Optional[str] = None
    whatsapp_number: Optional[str] = None
    upi_id: Optional[str] = None
