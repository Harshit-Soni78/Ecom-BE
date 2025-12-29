from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, JSON
from app.db.base import Base
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Courier(Base):
    __tablename__ = "couriers"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(50))
    api_key = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

class PaymentGateway(Base):
    __tablename__ = "payment_gateways"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(50))
    merchant_id = Column(String(100), nullable=True)
    api_key = Column(String(100), nullable=True)
    is_test_mode = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(20), unique=True) # business
    business_name = Column(String(100))
    company_name = Column(String(100), nullable=True)  # Company name for invoices and labels
    gst_number = Column(String(20), nullable=True)
    address = Column(JSON, nullable=True)
    phone = Column(String(15), nullable=True)
    email = Column(String(100), nullable=True)
    logo_url = Column(Text, nullable=True)
    favicon_url = Column(Text, nullable=True)
    social_links = Column(JSON, nullable=True)
    configs = Column(JSON, nullable=True) # invoice_prefix, etc
    
    updated_at = Column(DateTime, default=datetime.utcnow)
