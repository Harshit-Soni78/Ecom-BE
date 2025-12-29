from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base
from datetime import datetime
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Category(Base):
    __tablename__ = "categories"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100))
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    parent_id = Column(String(36), ForeignKey("categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(200))
    description = Column(Text, nullable=True)
    sku = Column(String(50), unique=True, index=True)
    category_id = Column(String(36), ForeignKey("categories.id"))
    
    mrp = Column(Float)
    selling_price = Column(Float)
    wholesale_price = Column(Float, nullable=True)
    wholesale_min_qty = Column(Integer, default=10)
    cost_price = Column(Float)
    
    stock_qty = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=10)
    
    images = Column(JSON, default=list) # List of URLs
    variants = Column(JSON, default=list)
    
    gst_rate = Column(Float, default=18.0)
    hsn_code = Column(String(20), nullable=True)
    weight = Column(Float, nullable=True)
    color = Column(String(50), nullable=True)
    material = Column(String(100), nullable=True)
    origin = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    category = relationship("Category", back_populates="products")

class InventoryLog(Base):
    __tablename__ = "inventory_logs"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    product_id = Column(String(36), ForeignKey("products.id"))
    sku = Column(String(50))
    type = Column(String(20)) # adjustment, sale, return
    quantity = Column(Integer)
    previous_qty = Column(Integer, nullable=True)
    new_qty = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class WishlistCategory(Base):
    __tablename__ = "wishlist_categories"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"))
    name = Column(String(100))
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#3B82F6")  # Hex color code
    icon = Column(String(50), default="heart")  # Icon name
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    wishlist_items = relationship("Wishlist", back_populates="category")

class Wishlist(Base):
    __tablename__ = "wishlists"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"))
    product_id = Column(String(36), ForeignKey("products.id"))
    category_id = Column(String(36), ForeignKey("wishlist_categories.id"), nullable=True)
    notes = Column(Text, nullable=True)  # User notes about the product
    priority = Column(Integer, default=1)  # 1=Low, 2=Medium, 3=High
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User")
    product = relationship("Product")
    category = relationship("WishlistCategory", back_populates="wishlist_items")
