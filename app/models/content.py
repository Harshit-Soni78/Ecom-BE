from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON
from app.db.base import Base
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Banner(Base):
    __tablename__ = "banners"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(100))
    image_url = Column(Text)
    link = Column(String(200), nullable=True)
    position = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Offer(Base):
    __tablename__ = "offers"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(100))
    description = Column(Text, nullable=True)
    discount_type = Column(String(20)) # percentage, flat
    discount_value = Column(Float)
    min_order_value = Column(Float, default=0)
    max_discount = Column(Float, nullable=True)
    coupon_code = Column(String(20), nullable=True)
    product_ids = Column(JSON, default=list)
    category_ids = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Page(Base):
    __tablename__ = "pages"
    
    slug = Column(String(50), primary_key=True) # privacy-policy, terms, contact
    title = Column(String(100))
    content = Column(Text)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
