from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, Text, JSON, DECIMAL
from sqlalchemy.orm import relationship
from database import Base
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

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_number = Column(String(20), unique=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    customer_phone = Column(String(15), nullable=True)
    
    # Storing items as JSON for simplicity, OR could use OrderItem table
    # Using JSON for items to match Mongo structure exactly for now
    items = Column(JSON) 
    
    subtotal = Column(Float)
    gst_applied = Column(Boolean, default=True)
    gst_total = Column(Float, default=0)
    discount_amount = Column(Float, default=0)
    grand_total = Column(Float)
    
    shipping_address = Column(JSON)
    payment_method = Column(String(20)) # cod, online
    payment_status = Column(String(20), default="pending")
    status = Column(String(20), default="pending")
    
    is_offline = Column(Boolean, default=False)
    tracking_number = Column(String(50), nullable=True)
    courier_provider = Column(String(50), nullable=True)
    
    tracking_history = Column(JSON, default=list)
    notes = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="orders")

class ReturnRequest(Base):
    __tablename__ = "returns"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("orders.id"))
    user_id = Column(String(36), ForeignKey("users.id"))
    
    items = Column(JSON)
    reason = Column(Text)
    return_type = Column(String(20), default="defective")  # defective, wrong_item, not_satisfied, damaged
    refund_method = Column(String(20))
    status = Column(String(20), default="pending")  # pending, approved, rejected, pickup_scheduled, picked_up, received, completed
    refund_amount = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Evidence for returns
    evidence_images = Column(JSON, default=list)  # URLs to uploaded evidence images
    evidence_videos = Column(JSON, default=list)  # URLs to uploaded evidence videos
    
    # Courier tracking for returns
    return_awb = Column(String(50), nullable=True)
    courier_provider = Column(String(50), nullable=True)
    pickup_scheduled_date = Column(DateTime, nullable=True)
    pickup_completed_date = Column(DateTime, nullable=True)
    received_date = Column(DateTime, nullable=True)
    
    # Admin fields
    admin_notes = Column(Text, nullable=True)
    processed_by = Column(String(36), nullable=True)  # Admin user ID who processed the return
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="returns")

class OrderCancellation(Base):
    __tablename__ = "order_cancellations"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("orders.id"))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    
    reason = Column(Text)
    cancellation_type = Column(String(20), default="customer")  # customer, admin, system
    cancelled_by = Column(String(36), nullable=True)  # User ID who cancelled
    refund_amount = Column(Float, nullable=True)
    refund_status = Column(String(20), default="pending")  # pending, processed, failed
    
    # Shipment cancellation details
    shipment_cancelled = Column(Boolean, default=False)
    shipment_cancel_response = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

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

class Page(Base):
    __tablename__ = "pages"
    
    slug = Column(String(50), primary_key=True) # privacy-policy, terms, contact
    title = Column(String(100))
    content = Column(Text)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
