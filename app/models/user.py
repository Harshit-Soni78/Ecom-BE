from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    phone = Column(String(15), unique=True, index=True)
    name = Column(String(100))
    email = Column(String(100), unique=True, nullable=True)
    password = Column(String(255))
    gst_number = Column(String(20), nullable=True)
    is_gst_verified = Column(Boolean, default=False)
    is_wholesale = Column(Boolean, default=False)
    is_seller = Column(Boolean, default=False)
    supplier_status = Column(String(20), default="none") # none, pending, approved, rejected
    role = Column(String(20), default="customer") # customer, seller, admin
    
    # Storing address as JSON to keep it simple compatible with current frontend structure
    # Alternatively could be a separate table
    address = Column(JSON, nullable=True) 
    addresses = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orders = relationship("Order", back_populates="user")
    returns = relationship("ReturnRequest", back_populates="user")

class OTP(Base):
    __tablename__ = "otps"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    phone = Column(String(15), index=True)
    otp = Column(String(6))
    expiry = Column(DateTime)
    verified = Column(Boolean, default=False)

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    type = Column(String(50))
    title = Column(String(100))
    message = Column(Text)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    data = Column(JSON, nullable=True)
    for_admin = Column(Boolean, default=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class SellerRequest(Base):
    __tablename__ = "seller_requests"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"))
    user_name = Column(String(100))
    user_phone = Column(String(15))
    business_name = Column(String(100))
    gst_number = Column(String(20))
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
