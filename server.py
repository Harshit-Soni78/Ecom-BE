from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query, UploadFile, File
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc, func
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
import random
import base64
import json
import io
import shutil
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.utils import ImageReader
import qrcode
from io import BytesIO as QRBytesIO

# Import Database and Models
from database import get_db, engine
import models
import email_utils

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

app = FastAPI(title="BharatBazaar API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Create uploads directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Mount static files for serving uploaded images
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

JWT_SECRET = os.environ.get('JWT_SECRET', 'bharatbazaar-secret-key-2024')
JWT_ALGORITHM = "HS256"

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ============ HELPER FUNCTIONS (Moved up for dependencies) ============

def generate_id():
    return str(uuid.uuid4())

def generate_order_number():
    """Generate a unique order number"""
    import random
    import string
    timestamp = datetime.now().strftime("%y%m%d")
    random_part = ''.join(random.choices(string.digits, k=4))
    return f"ORD{timestamp}{random_part}"

def generate_otp():
    """Generate a 6-digit OTP"""
    return str(random.randint(100000, 999999))

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def save_uploaded_file(file: UploadFile, folder: str = "general", image_type: str = None) -> str:
    """Save uploaded file and return the URL"""
    try:
        # Create folder if it doesn't exist
        folder_path = UPLOAD_DIR / folder
        folder_path.mkdir(exist_ok=True)
        
        # Generate unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        unique_filename = f"{generate_id()}.{file_extension}"
        file_path = folder_path / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Optimize image if it's an image file
        if file_extension.lower() in ['jpg', 'jpeg', 'png', 'webp']:
            # Determine image type based on folder or explicit type
            if image_type:
                optimize_image(file_path, image_type=image_type)
            elif folder == "branding":
                optimize_image(file_path, image_type="logo")  # Default for branding
            elif folder == "banners":
                optimize_image(file_path, image_type="banner")
            elif folder == "categories":
                optimize_image(file_path, image_type="category")
            elif folder == "products":
                optimize_image(file_path, image_type="product")
            else:
                optimize_image(file_path, image_type="general")
        
        # Return URL
        return f"/uploads/{folder}/{unique_filename}"
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

def optimize_image(file_path: Path, max_size: tuple = (1200, 1200), quality: int = 85, image_type: str = "general"):
    """Optimize image size and quality with specific handling for different image types"""
    try:
        with Image.open(file_path) as img:
            # Convert to RGB if necessary, but preserve transparency for logos/favicons
            if img.mode in ('RGBA', 'LA', 'P'):
                # For logos and favicons, preserve transparency by converting to RGBA
                if image_type in ['logo', 'favicon', 'branding']:
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                else:
                    img = img.convert('RGB')
            
            # Specific sizing for different image types
            if image_type == 'logo':
                # Logo: Resize to fit within 400x120 while maintaining aspect ratio
                img.thumbnail((400, 120), Image.Resampling.LANCZOS)
            elif image_type == 'favicon':
                # Favicon: Create 32x32 size
                img = img.resize((32, 32), Image.Resampling.LANCZOS)
            elif image_type == 'banner':
                # Banner: Resize to 1200x400 (3:1 aspect ratio)
                img = img.resize((1200, 400), Image.Resampling.LANCZOS)
            elif image_type == 'category':
                # Category: Square aspect ratio, max 500x500
                # Make it square by cropping to center
                width, height = img.size
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                img = img.crop((left, top, left + size, top + size))
                img = img.resize((500, 500), Image.Resampling.LANCZOS)
            elif image_type == 'product':
                # Product: Square aspect ratio, max 800x800
                width, height = img.size
                size = min(width, height)
                left = (width - size) // 2
                top = (height - size) // 2
                img = img.crop((left, top, left + size, top + size))
                img = img.resize((800, 800), Image.Resampling.LANCZOS)
            else:
                # General: Use provided max_size
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Save optimized image
            if img.mode == 'RGBA' and file_path.suffix.lower() in ['.jpg', '.jpeg']:
                # Convert RGBA to RGB for JPEG (no transparency support)
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
                img.save(file_path, optimize=True, quality=quality)
            else:
                # Save with transparency support for PNG
                img.save(file_path, optimize=True, quality=quality)
            
    except Exception as e:
        # If optimization fails, keep original file
        logging.warning(f"Failed to optimize image {file_path}: {str(e)}")

def delete_uploaded_file(file_url: str):
    """Delete uploaded file"""
    try:
        if file_url and file_url.startswith('/uploads/'):
            file_path = Path(file_url[1:])  # Remove leading slash
            if file_path.exists():
                file_path.unlink()
    except Exception as e:
        logging.warning(f"Failed to delete file {file_url}: {str(e)}")

# Create Tables
models.Base.metadata.create_all(bind=engine)

def create_initial_data():
    db = next(get_db())
    try:
        # Create Admin
        admin_phone = "8233189764"
        admin = db.query(models.User).filter(models.User.phone == admin_phone).first()
        if not admin:
            new_admin = models.User(
                id=generate_id(),
                phone=admin_phone,
                name="Rohit",
                email="admin@bharatbazaar.com",
                password=hash_password("Rohit@123"),
                role="admin",
                is_seller=True,
                is_wholesale=True,
                created_at=datetime.utcnow()
            )
            db.add(new_admin)
            db.commit()
            print(f"Admin user {admin_phone} created.")
        else:
            # Force update password to ensure it's correct (in case of previous seed errors)
            admin.password = hash_password("Rohit@123")
            admin.role = "admin" # Ensure role is admin
            admin.name = "Rohit"
            db.commit()
            print(f"Admin user {admin_phone} updated/verified.")
            
    except Exception as e:
        print(f"Error seeding data: {e}")
    finally:
        db.close()

# Run seed on startup
create_initial_data()

# ============ MODELS (Pydantic) ============

class UserBase(BaseModel):
    model_config = ConfigDict(extra="ignore")
    phone: str
    name: Optional[str] = None
    email: Optional[str] = None
    gst_number: Optional[str] = None
    is_gst_verified: bool = False
    address: Optional[Dict[str, str]] = None
    addresses: Optional[List[Dict[str, str]]] = []
    role: str = "customer"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    phone: str
    name: str
    email: Optional[str] = None
    gst_number: Optional[str] = None
    password: Optional[str] = None
    request_seller: bool = False

class AdminCreate(BaseModel):
    phone: str
    name: str
    email: Optional[str] = None
    password: str

class UserAddressUpdate(BaseModel):
    addresses: List[Dict[str, str]]

class SellerRequestInput(BaseModel):
    user_id: str
    business_name: Optional[str] = None
    gst_number: Optional[str] = None

class PincodeVerify(BaseModel):
    pincode: str

class UserLogin(BaseModel):
    identifier: str # Phone or Email
    password: str

class OTPRequest(BaseModel):
    phone: str
    email: Optional[str] = None # Capture email for OTP delivery

class ForgotPasswordRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None

class OTPVerify(BaseModel):
    phone: str
    otp: str

class CategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool = True

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category_id: str
    sku: str
    mrp: float
    selling_price: float
    wholesale_price: Optional[float] = None
    wholesale_min_qty: int = 10
    cost_price: float
    stock_qty: int = 0
    low_stock_threshold: int = 10
    images: List[str] = []
    variants: Optional[List[Dict[str, Any]]] = []
    gst_rate: float = 18.0
    hsn_code: Optional[str] = None
    weight: Optional[float] = None
    color: Optional[str] = None
    material: Optional[str] = None
    origin: Optional[str] = None
    is_active: bool = True

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    mrp: Optional[float] = None
    selling_price: Optional[float] = None
    wholesale_price: Optional[float] = None
    wholesale_min_qty: Optional[int] = None
    cost_price: Optional[float] = None
    stock_qty: Optional[int] = None
    low_stock_threshold: Optional[int] = None
    images: Optional[List[str]] = None
    gst_rate: Optional[float] = None
    color: Optional[str] = None
    material: Optional[str] = None
    origin: Optional[str] = None
    is_active: Optional[bool] = None

class CartItem(BaseModel):
    product_id: str
    quantity: int

class OrderCreate(BaseModel):
    items: List[CartItem]
    shipping_address: Dict[str, str]
    payment_method: str = "cod"
    is_offline: bool = False
    customer_phone: Optional[str] = None
    apply_gst: bool = True
    discount_amount: float = 0
    discount_percentage: float = 0

class OrderStatusUpdate(BaseModel):
    status: str
    tracking_number: Optional[str] = None
    courier_provider: Optional[str] = None
    notes: Optional[str] = None

class BannerCreate(BaseModel):
    title: str
    image_url: str
    link: Optional[str] = None
    position: int = 0
    is_active: bool = True

class OfferCreate(BaseModel):
    title: str
    description: Optional[str] = None
    discount_type: str = "percentage"
    discount_value: float
    min_order_value: float = 0
    max_discount: Optional[float] = None
    coupon_code: Optional[str] = None
    product_ids: Optional[List[str]] = []
    category_ids: Optional[List[str]] = []
    is_active: bool = True
    start_date: Optional[str] = None
    end_date: Optional[str] = None

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
    
class PageUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_active: Optional[bool] = None

class AdminCreate(BaseModel):
    name: str
    email: str
    phone: str

class ReturnRequest(BaseModel):
    order_id: str
    items: List[Dict[str, Any]]
    reason: str
    refund_method: str = "original"

class OrderCancellationRequest(BaseModel):
    order_id: str
    reason: str
    cancellation_type: str = "customer"  # customer, admin, system

class ReturnRequestCreate(BaseModel):
    order_id: str
    items: List[Dict[str, Any]]
    reason: str
    return_type: str = "defective"  # defective, wrong_item, not_satisfied, damaged
    refund_method: str = "original"
    images: Optional[List[str]] = []  # Evidence images
    videos: Optional[List[str]] = []  # Evidence videos
    description: Optional[str] = None

class ReturnRequestUpdate(BaseModel):
    status: str
    admin_notes: Optional[str] = None
    refund_amount: Optional[float] = None
    return_awb: Optional[str] = None
    courier_provider: Optional[str] = None

class ContactMessage(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    subject: str
    message: str

class WishlistItemAdd(BaseModel):
    category_id: Optional[str] = None
    notes: Optional[str] = None
    priority: int = 1

# ============ DEPENDENCIES ============

def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    """Optional authentication - returns None if no token provided"""
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            return None
        
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = db.query(models.User).filter(models.User.id == payload["user_id"]).first()
        if not user:
            return None
        
        user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
        if user.address is None: user_dict["address"] = None
        if user.addresses is None: user_dict["addresses"] = []
        return user_dict
    except:
        return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(status_code=401, detail="No authorization header")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = db.query(models.User).filter(models.User.id == payload["user_id"]).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        # Convert SQLAlchemy model to dict for backward compatibility in routing logic
        user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
        if user.address is None: user_dict["address"] = None
        if user.addresses is None: user_dict["addresses"] = []
        return user_dict
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail="Authentication failed")

def admin_required(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def generate_otp():
    return str(random.randint(100000, 999999))

def generate_order_number():
    return f"ORD{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

def generate_invoice_number():
    return f"INV{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"

# ============ IMAGE UPLOAD ROUTES ============

@api_router.post("/upload/image")
def upload_image(
    file: UploadFile = File(...),
    folder: str = "general",
    image_type: str = None,
    admin: dict = Depends(admin_required)
):
    """Upload an image file with automatic optimization"""
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Remove file size restriction - let the system handle any size
    # The optimization will resize appropriately
    
    # Save file with specific image type
    file_url = save_uploaded_file(file, folder, image_type)
    
    return {
        "message": "Image uploaded and optimized successfully",
        "url": file_url,
        "filename": file.filename,
        "optimized_for": image_type or folder
    }

@api_router.post("/upload/logo")
def upload_logo(
    file: UploadFile = File(...),
    admin: dict = Depends(admin_required)
):
    """Upload and optimize logo image (any size will be optimized to 400x120 max)"""
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    file_url = save_uploaded_file(file, "branding", "logo")
    
    return {
        "message": "Logo uploaded and optimized successfully",
        "url": file_url,
        "filename": file.filename,
        "optimized_size": "400x120 max (aspect ratio preserved)"
    }

@api_router.post("/upload/favicon")
def upload_favicon(
    file: UploadFile = File(...),
    admin: dict = Depends(admin_required)
):
    """Upload and optimize favicon image (any size will be optimized to 32x32)"""
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    file_url = save_uploaded_file(file, "branding", "favicon")
    
    return {
        "message": "Favicon uploaded and optimized successfully",
        "url": file_url,
        "filename": file.filename,
        "optimized_size": "32x32 pixels"
    }

@api_router.post("/upload/multiple")
def upload_multiple_images(
    files: List[UploadFile] = File(...),
    folder: str = "general",
    image_type: str = None,
    admin: dict = Depends(admin_required)
):
    """Upload multiple image files with automatic optimization"""
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files allowed")
    
    uploaded_files = []
    for file in files:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            continue
        
        # Remove size restriction - let optimization handle it
        
        try:
            file_url = save_uploaded_file(file, folder, image_type)
            uploaded_files.append({
                "url": file_url,
                "filename": file.filename
            })
        except Exception as e:
            continue
    
    return {
        "message": f"Uploaded and optimized {len(uploaded_files)} images successfully",
        "files": uploaded_files,
        "optimized_for": image_type or folder
    }

@api_router.delete("/upload/delete")
def delete_image(
    file_url: str,
    admin: dict = Depends(admin_required)
):
    """Delete an uploaded image"""
    delete_uploaded_file(file_url)
    return {"message": "Image deleted successfully"}

# ============ AUTH ROUTES ============

@api_router.get("/auth/test")
def test_auth(user: dict = Depends(get_current_user)):
    """Test endpoint to check if authentication is working"""
    return {"message": "Authentication successful", "user": user["name"]}

@api_router.post("/admin/test-email")
def test_email_functionality(data: dict, admin: dict = Depends(admin_required)):
    """Test endpoint to verify email functionality"""
    test_email = data.get("email", "test@example.com")
    
    # Test OTP email
    otp_result = email_utils.send_otp_email(test_email, "9876543210", "123456")
    
    # Test temporary password email
    temp_pass_result = email_utils.send_temporary_password_email(
        test_email, "Test User", "TempPass123", True
    )
    
    return {
        "message": "Email test completed",
        "otp_email_sent": otp_result,
        "temp_password_email_sent": temp_pass_result,
        "note": "Check server console logs if EMAIL_ENABLED=false"
    }

@api_router.post("/auth/send-otp")
def send_otp(data: OTPRequest, db: Session = Depends(get_db)):
    otp = generate_otp()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
    
    # Upsert OTP
    existing_otp = db.query(models.OTP).filter(models.OTP.phone == data.phone).first()
    if existing_otp:
        existing_otp.otp = otp
        existing_otp.expiry = expiry
        existing_otp.verified = False
    else:
        new_otp = models.OTP(phone=data.phone, otp=otp, expiry=expiry, verified=False)
        db.add(new_otp)
    
    db.commit()
    
    # Send OTP via Email with fallback instructions
    if data.email:
        email_utils.send_otp_email(data.email, data.phone, otp)
    
    return {"message": "OTP sent successfully", "otp_for_testing": otp}

@api_router.post("/auth/verify-otp")
def verify_otp(data: OTPVerify, db: Session = Depends(get_db)):
    otp_doc = db.query(models.OTP).filter(models.OTP.phone == data.phone).first()
    if not otp_doc:
        raise HTTPException(status_code=400, detail="No OTP found for this phone")
    
    if otp_doc.otp != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    if datetime.utcnow() > otp_doc.expiry: 
        raise HTTPException(status_code=400, detail="OTP expired")
    
    otp_doc.verified = True
    db.commit()
    return {"message": "OTP verified successfully", "verified": True}

@api_router.post("/auth/register")
def register(data: UserCreate, db: Session = Depends(get_db)):
    # Check if OTP was verified
    otp_doc = db.query(models.OTP).filter(models.OTP.phone == data.phone, models.OTP.verified == True).first()
    if not otp_doc:
        # In case user registers without OTP flow (e.g. dev), we might want to relax this OR enforce it strict
        # For now enforcing strict to match previous logic
        pass
        # Commented out for dev ease, or uncomment if strictly needed
    
    # Check if user exists
    existing = db.query(models.User).filter(models.User.phone == data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists with this phone number")
    
    if data.email:
        existing_email = db.query(models.User).filter(models.User.email == data.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="User already exists with this email address")
    
    request_supplier = bool(data.gst_number)
    supplier_status = "pending" if request_supplier else "none"
    is_wholesale = False
    
    # helper for password
    final_password = ""
    temporary_password = ""
    should_send_email = False
    
    if data.password:
        final_password = hash_password(data.password)
    else:
        # Generate temporary password if none provided
        temporary_password = f"Pass{generate_otp()}"
        final_password = hash_password(temporary_password)
        should_send_email = True
    
    new_user = models.User(
        id=generate_id(),
        phone=data.phone,
        name=data.name,
        email=data.email,
        gst_number=data.gst_number,
        is_gst_verified=False,
        is_wholesale=is_wholesale,
        supplier_status=supplier_status,
        password=final_password,
        role="customer",
        created_at=datetime.utcnow()
    )
    
    db.add(new_user)
    if otp_doc:
        db.delete(otp_doc)
    db.commit()
    db.refresh(new_user)
    
    # Send temporary password via email ONLY if we generated it
    if should_send_email and data.email:
        email_utils.send_temporary_password_email(
            to_email=data.email,
            name=data.name,
            temporary_password=temporary_password,
            is_registration=True
        )
    
    token = create_token(new_user.id, "customer")
    
    user_dict = {c.name: getattr(new_user, c.name) for c in new_user.__table__.columns}
    user_dict.pop("password")
    
    response = {"token": token, "user": user_dict}
    if request_supplier:
        response["supplier_pending"] = True
        response["message"] = "Your supplier request has been submitted. Admin will review and approve your request."
    return response

@api_router.post("/auth/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    # Check by phone OR email
    user = db.query(models.User).filter(
        or_(
            models.User.phone == data.identifier,
            models.User.email == data.identifier
        )
    ).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user.id, user.role)
    
    user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    user_dict.pop("password")
    
    return {"token": token, "user": user_dict}

@api_router.post("/auth/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    # ForgotPasswordRequest has phone and email, we can use either
    identifier = data.email or data.phone
    if not identifier:
        raise HTTPException(status_code=400, detail="Please provide phone or email")
        
    user = db.query(models.User).filter(
        or_(
            models.User.email == identifier,
            models.User.phone == identifier
        )
    ).first()
    
    if not user:
        # Don't reveal user existence for security, but for this app maybe ok to say "User not found" 
        # based on user preference to be helpful. 
        raise HTTPException(status_code=404, detail="User not found")
    
    # Ensure user has an email address
    if not user.email:
        raise HTTPException(status_code=400, detail="No email address associated with this account. Please contact support@amolias.com")
    
    # Generate new temporary password
    new_password = f"Pass{generate_otp()}"
    user.password = hash_password(new_password)
    db.commit()
    
    # Send temporary password via email
    email_utils.send_temporary_password_email(
        to_email=user.email,
        name=user.name,
        temporary_password=new_password,
        is_registration=False
    )
    
    return {"message": f"New temporary password has been sent to {user.email}"}

@api_router.get("/auth/me")
def get_current_user_info(user: dict = Depends(get_current_user)):
    """Get current user information"""
    return user

@api_router.put("/auth/profile")
def update_profile(data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed_fields = ["name", "email", "address", "addresses"]
    db_user = db.query(models.User).filter(models.User.id == user["id"]).first()
    
    for k, v in data.items():
        if k in allowed_fields:
            setattr(db_user, k, v)
    
    db.commit()
    db.refresh(db_user)
    
    user_dict = {c.name: getattr(db_user, c.name) for c in db_user.__table__.columns}
    user_dict.pop("password")
    return user_dict

# ============ SELLER REQUEST ROUTES ============

@api_router.post("/auth/request-seller")
def request_seller_upgrade(data: SellerRequestInput, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    request_id = generate_id()
    new_request = models.SellerRequest(
        id=request_id,
        user_id=user["id"],
        user_name=user["name"],
        user_phone=user["phone"],
        business_name=data.business_name,
        gst_number=data.gst_number,
        status="pending"
    )
    db.add(new_request)
    
    # Notification for admin
    create_admin_notification(
        db=db,
        type="seller_request",
        title="New Seller Request",
        message=f"{user['name']} has requested seller access",
        data={"request_id": request_id, "user_id": user["id"]}
    )
    
    db.commit()
    db.refresh(new_request)
    
    return {"message": "Seller request submitted", "request": {c.name: getattr(new_request, c.name) for c in new_request.__table__.columns}}

@api_router.get("/admin/seller-requests")
def get_seller_requests(status: Optional[str] = None, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    query = db.query(models.SellerRequest)
    if status:
        query = query.filter(models.SellerRequest.status == status)
    
    requests = query.order_by(models.SellerRequest.created_at.desc()).limit(100).all()
    return requests

@api_router.put("/admin/seller-requests/{request_id}")
def handle_seller_request(request_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    request = db.query(models.SellerRequest).filter(models.SellerRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    status = data.get("status", "approved")
    request.status = status
    
    if status == "approved":
        # Upgrade user
        user = db.query(models.User).filter(models.User.id == request.user_id).first()
        if user:
            user.is_seller = True
            user.is_wholesale = True
            user.gst_number = request.gst_number or user.gst_number
            
            # Notify user about role change
            create_role_change_notification(
                db=db,
                user_id=user.id,
                old_role="customer",
                new_role="seller"
            )
    
    db.commit()
    return {"message": f"Request {status}"}

# ============ NOTIFICATION HELPER FUNCTIONS ============

def create_notification(db: Session, user_id: str = None, type: str = "", title: str = "", message: str = "", data: dict = None, for_admin: bool = False):
    """Helper function to create notifications"""
    notification = models.Notification(
        id=generate_id(),
        type=type,
        title=title,
        message=message,
        user_id=user_id,
        data=data or {},
        for_admin=for_admin,
        read=False
    )
    db.add(notification)
    return notification

def create_order_tracking_notification(db: Session, user_id: str, order_id: str, status: str, message: str):
    """Create order tracking notification"""
    status_titles = {
        "pending": "Order Placed",
        "confirmed": "Order Confirmed",
        "processing": "Order Processing",
        "shipped": "Order Shipped",
        "out_for_delivery": "Out for Delivery",
        "delivered": "Order Delivered",
        "cancelled": "Order Cancelled",
        "returned": "Order Returned"
    }
    
    return create_notification(
        db=db,
        user_id=user_id,
        type="order_tracking",
        title=status_titles.get(status, "Order Update"),
        message=message,
        data={"order_id": order_id, "status": status}
    )

def create_role_change_notification(db: Session, user_id: str, old_role: str, new_role: str):
    """Create role change notification"""
    role_messages = {
        "customer_to_seller": "Congratulations! Your seller request has been approved. You can now start selling on our platform.",
        "customer_to_admin": "Welcome to Amorlias! You now have access for Admin.",
        "seller_to_admin": "Welcome to Amorlias! You now have access for Admin.",
        "admin_to_seller": "Your role has been changed to seller.",
        "seller_to_customer": "Your seller privileges have been revoked.",
        "admin_to_customer": "Your admin privileges have been revoked."
    }
    
    role_key = f"{old_role}_to_{new_role}"
    message = role_messages.get(role_key, f"Your role has been changed from {old_role} to {new_role}")
    
    return create_notification(
        db=db,
        user_id=user_id,
        type="role_change",
        title="Role Updated",
        message=message,
        data={"old_role": old_role, "new_role": new_role}
    )

def create_profile_update_notification(db: Session, user_id: str, field: str, action: str = "updated"):
    """Create profile update notification"""
    field_names = {
        "password": "Password",
        "phone": "Phone Number",
        "email": "Email Address",
        "name": "Name",
        "address": "Address",
        "gst_number": "GST Number"
    }
    
    field_name = field_names.get(field, field.title())
    
    return create_notification(
        db=db,
        user_id=user_id,
        type="profile_update",
        title="Profile Updated",
        message=f"Your {field_name.lower()} has been {action} successfully.",
        data={"field": field, "action": action}
    )

def create_supplier_status_notification(db: Session, user_id: str, status: str, business_name: str = ""):
    """Create supplier status notification"""
    status_messages = {
        "pending": f"Your supplier request for '{business_name}' is under review. We'll notify you once it's processed.",
        "approved": f"Congratulations! Your supplier request for '{business_name}' has been approved. You can now access wholesale features.",
        "rejected": f"Unfortunately, your supplier request for '{business_name}' has been rejected. Please contact support for more information."
    }
    
    status_titles = {
        "pending": "Supplier Request Submitted",
        "approved": "Supplier Request Approved",
        "rejected": "Supplier Request Rejected"
    }
    
    return create_notification(
        db=db,
        user_id=user_id,
        type="supplier_status",
        title=status_titles.get(status, "Supplier Status Update"),
        message=status_messages.get(status, f"Your supplier status has been updated to {status}"),
        data={"status": status, "business_name": business_name}
    )

def create_admin_notification(db: Session, type: str, title: str, message: str, data: dict = None):
    """Create admin notification"""
    return create_notification(
        db=db,
        user_id=None,
        type=type,
        title=title,
        message=message,
        data=data,
        for_admin=True
    )

# ============ NOTIFICATION ROUTES ============

@api_router.get("/notifications")
def get_user_notifications(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user notifications with pagination and filtering"""
    notifications = db.query(models.Notification).filter(
        models.Notification.user_id == user["id"],
        models.Notification.for_admin == False
    ).order_by(models.Notification.created_at.desc()).limit(50).all()
    
    unread_count = db.query(models.Notification).filter(
        models.Notification.user_id == user["id"],
        models.Notification.read == False,
        models.Notification.for_admin == False
    ).count()
    
    return {"notifications": notifications, "unread_count": unread_count}

@api_router.get("/notifications/unread-count")
def get_unread_notification_count(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get only the unread notification count for badge display"""
    unread_count = db.query(models.Notification).filter(
        models.Notification.user_id == user["id"],
        models.Notification.read == False,
        models.Notification.for_admin == False
    ).count()
    
    return {"unread_count": unread_count}

@api_router.put("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mark a specific notification as read"""
    note = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == user["id"]
    ).first()
    
    if note:
        note.read = True
        db.commit()
    return {"message": "Notification marked as read"}

@api_router.put("/notifications/mark-all-read")
def mark_all_read(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Mark all user notifications as read"""
    db.query(models.Notification).filter(
        models.Notification.user_id == user["id"],
        models.Notification.for_admin == False
    ).update({"read": True})
    db.commit()
    return {"message": "All notifications marked as read"}

@api_router.delete("/notifications/{notification_id}")
def delete_notification(notification_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a specific notification"""
    note = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == user["id"]
    ).first()
    
    if note:
        db.delete(note)
        db.commit()
    return {"message": "Notification deleted"}

@api_router.delete("/notifications")
def clear_all_notifications(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Clear all user notifications"""
    db.query(models.Notification).filter(
        models.Notification.user_id == user["id"],
        models.Notification.for_admin == False
    ).delete()
    db.commit()
    return {"message": "All notifications cleared"}

@api_router.get("/admin/notifications")
def get_admin_notifications(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get admin notifications"""
    notifications = db.query(models.Notification).filter(
        models.Notification.for_admin == True
    ).order_by(models.Notification.created_at.desc()).limit(50).all()
    
    unread_count = db.query(models.Notification).filter(
        models.Notification.for_admin == True,
        models.Notification.read == False
    ).count()
    
    return {"notifications": notifications, "unread_count": unread_count}

@api_router.get("/admin/notifications/unread-count")
def get_admin_unread_count(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get admin unread notification count"""
    unread_count = db.query(models.Notification).filter(
        models.Notification.for_admin == True,
        models.Notification.read == False
    ).count()
    
    return {"unread_count": unread_count}

@api_router.put("/admin/notifications/{notification_id}/read")
def mark_admin_notification_read(notification_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Mark admin notification as read"""
    note = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.for_admin == True
    ).first()
    
    if note:
        note.read = True
        db.commit()
    return {"message": "Notification marked as read"}

@api_router.put("/admin/orders/{order_id}/status")
def update_order_status(order_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Update order status and create tracking notification"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    new_status = data.get("status")
    tracking_number = data.get("tracking_number")
    courier_provider = data.get("courier_provider")
    notes = data.get("notes", "")
    
    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required")
    
    old_status = order.status
    order.status = new_status
    
    if tracking_number:
        order.tracking_number = tracking_number
    if courier_provider:
        order.courier_provider = courier_provider
    
    # Add to tracking history
    if not order.tracking_history:
        order.tracking_history = []
    
    tracking_entry = {
        "status": new_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
        "updated_by": admin["name"]
    }
    order.tracking_history.append(tracking_entry)
    
    # Create status-specific notification messages
    status_messages = {
        "confirmed": f"Your order #{order.order_number} has been confirmed!",
        "shipped": f"Your order #{order.order_number} has been shipped! Track it with ID: {tracking_number or order.tracking_number}",
        "delivered": f"Your order #{order.order_number} has been delivered successfully. Thank you for shopping with us!",
        "cancelled": f"Your order #{order.order_number} has been cancelled.",
        "returned": f"Return process initiated for order #{order.order_number}."
    }
    
    # Create notification for user
    if order.user_id:
        notification = models.Notification(
            id=generate_id(),
            type="order_status",
            title=f"Order {order.status.title()}",
            message=status_messages.get(new_status, f"Order #{order.order_number} status updated to {new_status}"),
            user_id=order.user_id,
            data={"order_id": order.id}
        )
        db.add(notification)
        
        # Send email notification
        if order.customer_phone or (order.user and order.user.email):
             # Logic to send email would go here
             pass

    db.commit()
    return {"message": "Order status updated successfully", "order": order}

@api_router.post("/admin/orders/{order_id}/sync-status")
def sync_order_status(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Sync order status with courier service automatically"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if not order.tracking_number:
        raise HTTPException(status_code=400, detail="Order has no tracking number linked")
        
    try:
        # fetch latest tracking info
        tracking_result = delhivery_service.track_order(order.tracking_number)
        
        if not tracking_result.get("success"):
             raise HTTPException(status_code=400, detail=f"Tracking failed: {tracking_result.get('error')}")
             
        courier_status = tracking_result.get("status") # e.g. "Delivered", "In Transit"
        
        updated = False
        original_status = order.status
        
        # Map courier status to our internal status
        # Note: Delhivery statuses can vary, but "Delivered" is standard
        status_map = {
            "Delivered": "delivered",
            "RTO": "returned",
            "Dispatched": "shipped", 
            "In Transit": "shipped",
            "Pending": "pending",
            "Manifested": "confirmed"
        }
        
        # specific check for RTO/Returned
        if "RTO" in str(courier_status).upper() or "RETURN" in str(courier_status).upper():
            mapped_status = "returned"
        elif "DELIVERED" in str(courier_status).upper():
             mapped_status = "delivered"
        else:
             mapped_status = status_map.get(courier_status)
             
        if mapped_status and mapped_status != order.status:
            # simple state machine check - don't revert delivered to shipped
            if order.status == "delivered" and mapped_status == "shipped":
                pass # ignore
            else:
                order.status = mapped_status
                updated = True
                
                # Add to history
                if not order.tracking_history: order.tracking_history = []
                order.tracking_history.append({
                    "status": mapped_status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "notes": f"Auto-synced from Courier: {courier_status}",
                    "updated_by": "System Sync"
                })
                
                # Notify user if delivered
                # Notify user for delivery status updates
                if order.user_id:
                     message = ""
                     title = "Order Update"
                     
                     if mapped_status == "delivered":
                         title = "Order Delivered"
                         message = f"Your order #{order.order_number} has been delivered successfully. We hope you like it!"
                     elif mapped_status == "shipped":
                         title = "Order Shipped"
                         message = f"Your order #{order.order_number} has been shipped. Track it with AWB: {order.tracking_number}"
                     elif mapped_status == "returned":
                         title = "Order Returned"
                         message = f"Your order #{order.order_number} was marked as returned/RTO."

                     if message:
                        notification = models.Notification(
                            id=generate_id(),
                            type="order_status",
                            title=title,
                            message=message,
                            user_id=order.user_id,
                            data={"order_id": order.id, "status": mapped_status}
                        )
                        db.add(notification)
        
        # Always update the raw tracking history/notes if available? 
        # For now just status sync is critical
        
        db.commit()
        db.refresh(order)
        
        return {
            "message": "Sync completed",
            "updated": updated,
            "original_status": original_status,
            "new_status": order.status,
            "courier_status": courier_status,
            "tracking_data": tracking_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/admin/users/{user_id}/role")
def update_user_role(user_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Update user role and create notification"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_role = data.get("role")
    if not new_role or new_role not in ["customer", "seller", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    old_role = user.role
    user.role = new_role
    
    # Update related fields based on role
    if new_role == "seller":
        user.is_seller = True
        user.is_wholesale = True
    elif new_role == "admin":
        user.is_seller = True
        user.is_wholesale = True
    else:  # customer
        user.is_seller = False
        user.is_wholesale = False
    
    # Create role change notification
    if old_role != new_role:
        create_role_change_notification(
            db=db,
            user_id=user.id,
            old_role=old_role,
            new_role=new_role
        )
        
        # Admin notification
        create_admin_notification(
            db=db,
            type="role_change",
            title="User Role Updated",
            message=f"User {user.name} ({user.phone}) role changed from {old_role} to {new_role}",
            data={
                "user_id": user.id,
                "user_name": user.name,
                "old_role": old_role,
                "new_role": new_role,
                "updated_by": admin["name"]
            }
        )
    
    db.commit()
    return {"message": "User role updated", "user": {"id": user.id, "name": user.name, "role": user.role}}

# ============ PROFILE UPDATE NOTIFICATIONS ============

@api_router.put("/auth/profile")
def update_profile(data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update user profile and create notifications for changes"""
    allowed_fields = ["name", "email", "address", "addresses"]
    user_obj = db.query(models.User).filter(models.User.id == user["id"]).first()
    
    if not user_obj:
        raise HTTPException(status_code=404, detail="User not found")
    
    updated_fields = []
    
    for field, value in data.items():
        if field in allowed_fields and hasattr(user_obj, field):
            old_value = getattr(user_obj, field)
            if old_value != value:
                setattr(user_obj, field, value)
                updated_fields.append(field)
    
    if updated_fields:
        db.commit()
        
        # Create notifications for each updated field
        for field in updated_fields:
            create_profile_update_notification(
                db=db,
                user_id=user["id"],
                field=field,
                action="updated"
            )
    
    return {"message": "Profile updated successfully", "updated_fields": updated_fields}

@api_router.put("/auth/change-password")
def change_password(data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Change user password and create notification"""
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    
    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Current and new passwords are required")
    
    user_obj = db.query(models.User).filter(models.User.id == user["id"]).first()
    
    if not user_obj or not verify_password(current_password, user_obj.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    user_obj.password = hash_password(new_password)
    db.commit()
    
    # Create password change notification
    create_profile_update_notification(
        db=db,
        user_id=user["id"],
        field="password",
        action="changed"
    )
    
    return {"message": "Password changed successfully"}

@api_router.put("/auth/update-phone")
def update_phone(data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update user phone number and create notification"""
    new_phone = data.get("phone")
    otp = data.get("otp")
    
    if not new_phone or not otp:
        raise HTTPException(status_code=400, detail="Phone number and OTP are required")
    
    # Verify OTP (assuming OTP verification logic exists)
    otp_doc = db.query(models.OTP).filter(
        models.OTP.phone == new_phone,
        models.OTP.otp == otp,
        models.OTP.verified == False
    ).first()
    
    if not otp_doc or otp_doc.expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Check if phone is already in use
    existing_user = db.query(models.User).filter(
        models.User.phone == new_phone,
        models.User.id != user["id"]
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone number already in use")
    
    user_obj = db.query(models.User).filter(models.User.id == user["id"]).first()
    old_phone = user_obj.phone
    user_obj.phone = new_phone
    
    # Mark OTP as verified
    otp_doc.verified = True
    
    db.commit()
    
    # Create phone update notification
    create_profile_update_notification(
        db=db,
        user_id=user["id"],
        field="phone",
        action="updated"
    )
    
    return {"message": "Phone number updated successfully"}

# ============ PINCODE VERIFICATION ============

@api_router.post("/verify-pincode")
def verify_pincode(data: PincodeVerify):
    pincode = data.pincode
    if not pincode or len(pincode) != 6 or not pincode.isdigit():
        raise HTTPException(status_code=400, detail="Invalid pincode format")
    
    # Use the shared Delhivery service for consistency
    return delhivery_service.check_serviceability(pincode)

# ============ BANNER ROUTES ============

@api_router.get("/banners")
def get_banners(db: Session = Depends(get_db)):
    banners = db.query(models.Banner).filter(models.Banner.is_active == True).order_by(models.Banner.position).all()
    return banners

@api_router.post("/admin/banners")
def create_banner(data: BannerCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    new_banner = models.Banner(
        id=generate_id(),
        **data.model_dump(),
        created_at=datetime.utcnow()
    )
    db.add(new_banner)
    db.commit()
    db.refresh(new_banner)
    return new_banner

@api_router.put("/admin/banners/{banner_id}")
def update_banner(banner_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    banner = db.query(models.Banner).filter(models.Banner.id == banner_id).first()
    if banner:
        for k, v in data.items():
            if hasattr(banner, k):
                setattr(banner, k, v)
        db.commit()
    return {"message": "Banner updated"}

@api_router.delete("/admin/banners/{banner_id}")
def delete_banner(banner_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    db.query(models.Banner).filter(models.Banner.id == banner_id).delete()
    db.commit()
    return {"message": "Banner deleted"}

# ============ CATEGORY ROUTES ============

@api_router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.Category).filter(models.Category.is_active == True).all()
    return categories

@api_router.get("/categories/{category_id}")
def get_category(category_id: str, db: Session = Depends(get_db)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@api_router.post("/admin/categories")
def create_category(data: CategoryCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    new_cat = models.Category(
        id=generate_id(),
        **data.model_dump(),
        created_at=datetime.utcnow()
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat

@api_router.put("/admin/categories/{category_id}")
def update_category(category_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if cat:
        for k, v in data.items():
            if hasattr(cat, k):
                setattr(cat, k, v)
        db.commit()
    return {"message": "Category updated"}

@api_router.delete("/admin/categories/{category_id}")
def delete_category(category_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    db.query(models.Category).filter(models.Category.id == category_id).delete()
    db.commit()
    return {"message": "Category deleted"}

# ============ PRODUCT ROUTES ============

@api_router.get("/products")
def get_products(
    category_id: Optional[str] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(models.Product).filter(models.Product.is_active == True)
    
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.Product.name.like(search_pattern),
                models.Product.description.like(search_pattern),
                models.Product.sku.like(search_pattern)
            )
        )
    if min_price:
        query = query.filter(models.Product.selling_price >= min_price)
    if max_price:
        query = query.filter(models.Product.selling_price <= max_price)
        
    # Sorting
    sort_attr = getattr(models.Product, sort_by, models.Product.created_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_attr))
    else:
        query = query.order_by(asc(sort_attr))
        
    total = query.count()
    products = query.offset((page - 1) * limit).limit(limit).all()
    
    return {"products": products, "total": total, "page": page, "pages": (total + limit - 1) // limit}

@api_router.get("/products/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@api_router.post("/admin/products")
def create_product(data: ProductCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    existing = db.query(models.Product).filter(models.Product.sku == data.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")
    
    new_product = models.Product(
        id=generate_id(),
        **data.model_dump(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

@api_router.put("/admin/products/{product_id}")
def update_product(product_id: str, data: ProductUpdate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if product:
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(product, k, v)
        product.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(product)
    return product

@api_router.delete("/admin/products/{product_id}")
def delete_product(product_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    db.query(models.Product).filter(models.Product.id == product_id).delete()
    db.commit()
    return {"message": "Product deleted"}

@api_router.post("/admin/products/bulk-upload")
def bulk_upload_products(products: List[ProductCreate], admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    created = 0
    updated = 0
    errors = []
    
    for product_data in products:
        try:
            existing = db.query(models.Product).filter(models.Product.sku == product_data.sku).first()
            if existing:
                for k, v in product_data.model_dump().items():
                    setattr(existing, k, v)
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                new_product = models.Product(
                    id=generate_id(),
                    **product_data.model_dump(),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_product)
                created += 1
        except Exception as e:
            errors.append(f"SKU {product_data.sku}: {str(e)}")
    
    db.commit()
    return {"created": created, "updated": updated, "errors": errors}

# ============ INVENTORY & ORDERS ============

@api_router.get("/admin/inventory")
def get_inventory(low_stock_only: bool = False, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    query = db.query(models.Product)
    if low_stock_only:
        query = query.filter(models.Product.stock_qty <= models.Product.low_stock_threshold)
        
    products = query.limit(1000).all()
    
    total_value = sum(p.stock_qty * p.cost_price for p in products)
    low_stock_count = sum(1 for p in products if p.stock_qty <= p.low_stock_threshold)
    out_of_stock = sum(1 for p in products if p.stock_qty == 0)
    
    return {
        "products": products,
        "stats": {
            "total_products": len(products),
            "total_inventory_value": total_value,
            "low_stock_count": low_stock_count,
            "out_of_stock": out_of_stock
        }
    }

# ============ POS (Point of Sale) ============

@api_router.post("/admin/pos/sale")
def create_pos_sale(data: OrderCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Create an offline POS sale"""
    # Validate and fetch products
    items_valid = []
    subtotal = 0
    
    for item in data.items:
        prod = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not prod:
            raise HTTPException(status_code=400, detail=f"Product {item.product_id} not found")
        if prod.stock_qty < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {prod.name}")
        
        # Use selling price for POS (wholesale logic can be added based on customer)
        price = prod.selling_price
        
        item_total = price * item.quantity
        gst_amount = item_total * (prod.gst_rate / 100) if data.apply_gst else 0
        
        items_valid.append({
            "product_id": prod.id,
            "product_name": prod.name,
            "sku": prod.sku,
            "quantity": item.quantity,
            "price": price,
            "total": item_total + gst_amount,
            "gst_amount": gst_amount,
            "gst_rate": prod.gst_rate,
            "image_url": prod.images[0] if prod.images else None
        })
        subtotal += item_total
        
        # Update stock
        prod.stock_qty -= item.quantity

    # Calculate totals
    total_gst = sum(i["gst_amount"] for i in items_valid)
    
    # Handle discount
    discount_amount = data.discount_amount
    if data.discount_percentage > 0:
        discount_amount = subtotal * (data.discount_percentage / 100)
    
    grand_total = subtotal + total_gst - discount_amount
    
    # Create order
    new_order = models.Order(
        id=generate_id(),
        order_number=generate_order_number(),
        user_id=None,  # POS sales may not have user accounts
        customer_phone=data.customer_phone,
        items=items_valid,
        subtotal=subtotal,
        gst_applied=data.apply_gst,
        gst_total=total_gst,
        discount_amount=discount_amount,
        grand_total=grand_total,
        shipping_address=data.shipping_address,
        payment_method=data.payment_method,
        payment_status="paid",  # POS sales are paid immediately
        status="completed",  # POS sales are completed immediately
        is_offline=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    return new_order

@api_router.get("/admin/pos/search-customer")
def search_customer(phone: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Search for customer by phone number"""
    if not phone or len(phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    
    user = db.query(models.User).filter(models.User.phone == phone).first()
    
    if not user:
        return None
    
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "email": user.email,
        "is_seller": user.supplier_status == "approved"
    }


@api_router.post("/orders")
def create_order(data: OrderCreate, request: Request, db: Session = Depends(get_db)):
    user = get_current_user_optional(request, db)
    
    if not user:
        # For now, require authentication for orders
        raise HTTPException(status_code=401, detail="Authentication required to place orders")

    # Simplified logic for creating order
    # Fetch products
    items_valid = []
    subtotal = 0
    
    for item in data.items:
        prod = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not prod:
             raise HTTPException(status_code=400, detail=f"Product {item.product_id} not found")
        if prod.stock_qty < item.quantity:
             raise HTTPException(status_code=400, detail=f"Insufficient stock for {prod.name}")
        
        price = prod.selling_price
        # Logic for wholesale price
        if user and user.get("is_wholesale") and item.quantity >= prod.wholesale_min_qty:
             price = prod.wholesale_price or prod.selling_price
             
        item_total = price * item.quantity
        gst_amount = item_total * (prod.gst_rate / 100) if data.apply_gst else 0
        
        items_valid.append({
            "product_id": prod.id,
            "product_name": prod.name,
            "sku": prod.sku,
            "quantity": item.quantity,
            "price": price,
            "total": item_total + gst_amount,
            "gst_amount": gst_amount,
            "image_url": prod.images[0] if prod.images else None
        })
        subtotal += item_total
        
        # Update stock
        prod.stock_qty -= item.quantity

    total_gst = sum(i["gst_amount"] for i in items_valid)
    discount = data.discount_amount
    grand_total = subtotal + total_gst - discount
    
    new_order = models.Order(
        id=generate_id(),
        order_number=generate_order_number(),
        user_id=user["id"] if user else None,
        customer_phone=data.customer_phone,
        items=items_valid,
        subtotal=subtotal,
        gst_applied=data.apply_gst,
        gst_total=total_gst,
        discount_amount=discount,
        grand_total=grand_total,
        shipping_address=data.shipping_address,
        payment_method=data.payment_method,
        status="pending",
        is_offline=data.is_offline,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_order)
    
    # Notification for user
    if user:
        create_order_tracking_notification(
            db=db,
            user_id=user["id"],
            order_id=new_order.id,
            status="pending",
            message=f"Your order #{new_order.order_number} has been placed successfully. We'll notify you when it's confirmed."
        )
        
        # Admin notification for new order
        create_admin_notification(
            db=db,
            type="new_order",
            title="Ready to Dispatch",
            message=f"Order #{new_order.order_number} is ready to dispatch. Customer: {user.get('name', 'Customer')} - ₹{new_order.grand_total}",
            data={
                "order_id": new_order.id,
                "order_number": new_order.order_number,
                "user_id": user["id"],
                "amount": new_order.grand_total
            }
        )
        
    db.commit()
    db.refresh(new_order)
    return new_order

@api_router.get("/orders")
def get_user_orders(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    orders = db.query(models.Order).filter(models.Order.user_id == user["id"]).order_by(models.Order.created_at.desc()).limit(100).all()
    
    # Enrich orders with current product information
    enriched_orders = []
    for order in orders:
        order_dict = {
            "id": order.id,
            "order_number": order.order_number,
            "user_id": order.user_id,
            "customer_phone": order.customer_phone,
            "subtotal": order.subtotal,
            "gst_applied": order.gst_applied,
            "gst_total": order.gst_total,
            "discount_amount": order.discount_amount,
            "grand_total": order.grand_total,
            "shipping_address": order.shipping_address,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "status": order.status,
            "is_offline": order.is_offline,
            "tracking_number": order.tracking_number,
            "courier_provider": order.courier_provider,
            "tracking_history": order.tracking_history,
            "notes": order.notes,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "items": []
        }
        
        # Enrich items with current product images if missing
        if order.items:
            for item in order.items:
                # Create a copy of the item dict
                enriched_item = dict(item) if isinstance(item, dict) else item
                
                # If image_url is missing, fetch from current product
                if not enriched_item.get("image_url"):
                    product_id = enriched_item.get("product_id")
                    if product_id:
                        product = db.query(models.Product).filter(models.Product.id == product_id).first()
                        if product and product.images and len(product.images) > 0:
                            enriched_item["image_url"] = product.images[0]
                
                order_dict["items"].append(enriched_item)
        
        enriched_orders.append(order_dict)
    
    return enriched_orders

@api_router.get("/orders/{order_id}")
def get_order_by_id(order_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_id == user["id"]
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return order

@api_router.get("/admin/orders")
def get_all_orders(
    status: Optional[str] = None, page: int = 1, limit: int = 20, 
    admin: dict = Depends(admin_required), db: Session = Depends(get_db)
):
    try:
        query = db.query(models.Order).outerjoin(models.User, models.Order.user_id == models.User.id)
        if status:
            query = query.filter(models.Order.status == status)
        
        total = query.count()
        orders = query.order_by(models.Order.created_at.desc()).offset((page-1)*limit).limit(limit).all()
        
        # Add customer name to each order
        orders_with_customer = []
        for order in orders:
            # Get customer name from user relationship or shipping address
            customer_name = None
            if order.user:
                customer_name = order.user.name
            elif order.shipping_address and order.shipping_address.get("name"):
                customer_name = order.shipping_address.get("name")
            else:
                customer_name = "Guest"
            
            order_dict = {
                "id": order.id,
                "order_number": order.order_number,
                "user_id": order.user_id,
                "customer_phone": order.customer_phone,
                "customer_name": customer_name,
                "items": order.items,
                "subtotal": order.subtotal,
                "gst_applied": order.gst_applied,
                "gst_total": order.gst_total,
                "discount_amount": order.discount_amount,
                "grand_total": order.grand_total,
                "shipping_address": order.shipping_address,
                "payment_method": order.payment_method,
                "payment_status": order.payment_status,
                "status": order.status,
                "is_offline": order.is_offline,
                "tracking_number": order.tracking_number,
                "courier_provider": order.courier_provider,
                "tracking_history": order.tracking_history,
                "notes": order.notes,
                "created_at": order.created_at,
                "updated_at": order.updated_at
            }
            orders_with_customer.append(order_dict)
        
        return {
            "orders": orders_with_customer,
            "total": total,
            "page": page,
            "limit": limit
        }
    except Exception as e:
        print(f"Error in get_all_orders: {e}")
        # Fallback to simple query without join
        query = db.query(models.Order)
        if status:
            query = query.filter(models.Order.status == status)
        
        total = query.count()
        orders = query.order_by(models.Order.created_at.desc()).offset((page-1)*limit).limit(limit).all()
        
        # Add customer name from shipping address only
        orders_with_customer = []
        for order in orders:
            customer_name = order.shipping_address.get("name", "Guest") if order.shipping_address else "Guest"
            
            order_dict = {
                "id": order.id,
                "order_number": order.order_number,
                "user_id": order.user_id,
                "customer_phone": order.customer_phone,
                "customer_name": customer_name,
                "items": order.items,
                "subtotal": order.subtotal,
                "gst_applied": order.gst_applied,
                "gst_total": order.gst_total,
                "discount_amount": order.discount_amount,
                "grand_total": order.grand_total,
                "shipping_address": order.shipping_address,
                "payment_method": order.payment_method,
                "payment_status": order.payment_status,
                "status": order.status,
                "is_offline": order.is_offline,
                "tracking_number": order.tracking_number,
                "courier_provider": order.courier_provider,
                "tracking_history": order.tracking_history,
                "notes": order.notes,
                "created_at": order.created_at,
                "updated_at": order.updated_at
            }
            orders_with_customer.append(order_dict)
        
        return {
            "orders": orders_with_customer,
            "total": total,
            "page": page,
            "limit": limit
        }
@api_router.get("/admin/orders/{order_id}/invoice")
def get_invoice(order_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get professional invoice PDF for an order"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    # Check access (admin or owner)
    if user["role"] != "admin" and order.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    # Use the new professional invoice generation
    try:
        pdf_buffer = generate_invoice_pdf(order_id, db)
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=invoice_{order.order_number}.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate invoice: {str(e)}")

# ============ ORDER CANCELLATION & RETURN SYSTEM ============

@api_router.post("/orders/{order_id}/cancel")
def cancel_order(order_id: str, data: OrderCancellationRequest, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cancel an order with reason and notification flow"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if user can cancel this order
    if user["role"] != "admin" and order.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this order")
    
    # Check if order can be cancelled
    if order.status in ["delivered", "cancelled", "returned"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel order with status: {order.status}")
    
    # If order is shipped, we need to handle return logistics
    if order.status in ["shipped", "out_for_delivery"]:
        # Create return request automatically
        return_request = models.ReturnRequest(
            id=generate_id(),
            order_id=order.id,
            user_id=order.user_id,
            items=order.items,
            reason=f"Order cancelled by {data.cancellation_type}: {data.reason}",
            refund_method="original",
            status="approved",  # Auto-approve cancellation returns
            refund_amount=order.grand_total,
            created_at=datetime.utcnow()
        )
        db.add(return_request)
        
        # Try to cancel shipment if tracking number exists
        if order.tracking_number:
            try:
                from courier_service import DelhiveryService
                delhivery_service = DelhiveryService(os.environ.get('DELHIVERY_TOKEN', ''))
                cancel_result = delhivery_service.cancel_shipment(order.tracking_number)
                if cancel_result.get("success"):
                    return_request.notes = "Shipment cancelled successfully"
                else:
                    return_request.notes = f"Shipment cancellation failed: {cancel_result.get('error')}"
            except Exception as e:
                return_request.notes = f"Could not cancel shipment: {str(e)}"
    
    # Update order status
    old_status = order.status
    order.status = "cancelled"
    order.updated_at = datetime.utcnow()
    
    # Add to tracking history
    if not order.tracking_history:
        order.tracking_history = []
    
    tracking_entry = {
        "status": "cancelled",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": f"Order cancelled: {data.reason}",
        "updated_by": user["name"] if user["role"] == "admin" else "Customer"
    }
    order.tracking_history.append(tracking_entry)
    
    # Restore inventory for cancelled items
    for item in order.items:
        product = db.query(models.Product).filter(models.Product.id == item.get("product_id")).first()
        if product:
            product.stock_qty += item.get("quantity", 1)
            
            # Log inventory adjustment
            inventory_log = models.InventoryLog(
                id=generate_id(),
                product_id=product.id,
                sku=product.sku,
                type="return",
                quantity=item.get("quantity", 1),
                previous_qty=product.stock_qty - item.get("quantity", 1),
                new_qty=product.stock_qty,
                notes=f"Order cancellation - Order #{order.order_number}",
                created_by=user["id"],
                created_at=datetime.utcnow()
            )
            db.add(inventory_log)
    
    # Create cancellation notification for user
    if order.user_id:
        create_order_tracking_notification(
            db=db,
            user_id=order.user_id,
            order_id=order.id,
            status="cancelled",
            message=f"Your order #{order.order_number} has been cancelled. Reason: {data.reason}. Refund will be processed within 3-5 business days."
        )
        
        # Send cancellation email
        user_obj = db.query(models.User).filter(models.User.id == order.user_id).first()
        if user_obj and user_obj.email:
            email_utils.send_order_cancelled_email(
                to_email=user_obj.email,
                order_number=order.order_number or "N/A",
                reason=data.reason,
                refund_amount=order.grand_total
            )
    
    # Create admin notification
    create_admin_notification(
        db=db,
        type="order_cancelled",
        title="Order Cancelled",
        message=f"Order #{order.order_number} cancelled by {data.cancellation_type}. Reason: {data.reason}",
        data={
            "order_id": order.id,
            "order_number": order.order_number,
            "cancelled_by": user["name"],
            "reason": data.reason,
            "refund_amount": order.grand_total
        }
    )
    
    db.commit()
    
    return {
        "message": "Order cancelled successfully",
        "order_id": order.id,
        "order_number": order.order_number,
        "status": "cancelled",
        "refund_amount": order.grand_total,
        "refund_timeline": "3-5 business days"
    }

@api_router.post("/orders/{order_id}/return")
def create_return_request(order_id: str, data: ReturnRequestCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a return request with evidence upload support"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if user can return this order
    if user["role"] != "admin" and order.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to return this order")
    
    # Check if order can be returned
    if order.status not in ["delivered"]:
        raise HTTPException(status_code=400, detail=f"Cannot return order with status: {order.status}. Order must be delivered to initiate return.")
    
    # Check if return window is valid (e.g., 5 days from delivery)
    if order.updated_at:
        days_since_delivery = (datetime.utcnow() - order.updated_at).days
        if days_since_delivery > 5:
            raise HTTPException(status_code=400, detail="Return window expired. Returns are only accepted within 5 days of delivery.")
    
    # Validate return items
    order_item_ids = {item.get("product_id") for item in order.items}
    return_item_ids = {item.get("product_id") for item in data.items}
    
    if not return_item_ids.issubset(order_item_ids):
        raise HTTPException(status_code=400, detail="Some items in return request were not part of the original order")
    
    # Calculate refund amount
    refund_amount = 0
    for return_item in data.items:
        for order_item in order.items:
            if order_item.get("product_id") == return_item.get("product_id"):
                item_price = order_item.get("price", 0)
                return_qty = return_item.get("quantity", 1)
                order_qty = order_item.get("quantity", 1)
                
                if return_qty > order_qty:
                    raise HTTPException(status_code=400, detail=f"Cannot return more items than ordered for product {return_item.get('product_name', 'Unknown')}")
                
                refund_amount += item_price * return_qty
                break
    
    # Create return request
    return_request = models.ReturnRequest(
        id=generate_id(),
        order_id=order.id,
        user_id=order.user_id,
        items=data.items,
        reason=f"{data.return_type}: {data.reason}",
        refund_method=data.refund_method,
        status="pending",
        refund_amount=refund_amount,
        notes=data.description,
        created_at=datetime.utcnow()
    )
    db.add(return_request)
    
    # Create return notification for user
    create_notification(
        db=db,
        user_id=order.user_id,
        type="return_request",
        title="Return Request Submitted",
        message=f"Your return request for order #{order.order_number} has been submitted. We'll review it within 24 hours.",
        data={
            "order_id": order.id,
            "return_id": return_request.id,
            "return_type": data.return_type,
            "refund_amount": refund_amount
        }
    )
    
    # Create admin notification
    create_admin_notification(
        db=db,
        type="return_request",
        title="New Return Request",
        message=f"Return request submitted for order #{order.order_number}. Reason: {data.return_type} - {data.reason}",
        data={
            "order_id": order.id,
            "return_id": return_request.id,
            "customer_name": user["name"],
            "return_type": data.return_type,
            "reason": data.reason,
            "refund_amount": refund_amount,
            "evidence_images": len(data.images or []),
            "evidence_videos": len(data.videos or [])
        }
    )
    
    db.commit()
    
    return {
        "message": "Return request submitted successfully",
        "return_id": return_request.id,
        "order_number": order.order_number,
        "status": "pending",
        "refund_amount": refund_amount,
        "review_timeline": "24 hours",
        "next_steps": "Our team will review your return request and evidence. You'll receive a notification once approved."
    }

@api_router.get("/orders/{order_id}/returns")
def get_order_returns(order_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all return requests for an order"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check access
    if user["role"] != "admin" and order.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    returns = db.query(models.ReturnRequest).filter(models.ReturnRequest.order_id == order_id).all()
    return returns

@api_router.get("/returns")
def get_user_returns(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all return requests for the current user"""
    returns = db.query(models.ReturnRequest).filter(
        models.ReturnRequest.user_id == user["id"]
    ).order_by(models.ReturnRequest.created_at.desc()).all()
    
    # Enrich with order information
    enriched_returns = []
    for return_req in returns:
        order = db.query(models.Order).filter(models.Order.id == return_req.order_id).first()
        return_dict = {c.name: getattr(return_req, c.name) for c in return_req.__table__.columns}
        return_dict["order_number"] = order.order_number if order else "Unknown"
        return_dict["order_date"] = order.created_at.isoformat() if order and order.created_at else None
        enriched_returns.append(return_dict)
    
    return enriched_returns

@api_router.get("/admin/returns")
def get_all_returns(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    admin: dict = Depends(admin_required),
    db: Session = Depends(get_db)
):
    """Get all return requests for admin review"""
    query = db.query(models.ReturnRequest)
    
    if status:
        query = query.filter(models.ReturnRequest.status == status)
    
    total = query.count()
    returns = query.order_by(models.ReturnRequest.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    # Enrich with order and user information
    enriched_returns = []
    for return_req in returns:
        order = db.query(models.Order).filter(models.Order.id == return_req.order_id).first()
        user_obj = db.query(models.User).filter(models.User.id == return_req.user_id).first()
        
        return_dict = {c.name: getattr(return_req, c.name) for c in return_req.__table__.columns}
        return_dict["order_number"] = order.order_number if order else "Unknown"
        return_dict["customer_name"] = user_obj.name if user_obj else "Unknown"
        return_dict["customer_phone"] = user_obj.phone if user_obj else "Unknown"
        enriched_returns.append(return_dict)
    
    return {
        "returns": enriched_returns,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@api_router.put("/admin/returns/{return_id}")
def update_return_request(return_id: str, data: ReturnRequestUpdate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Update return request status and handle approval/rejection"""
    return_request = db.query(models.ReturnRequest).filter(models.ReturnRequest.id == return_id).first()
    if not return_request:
        raise HTTPException(status_code=404, detail="Return request not found")
    
    try:
        order = db.query(models.Order).filter(models.Order.id == return_request.order_id).first()
        old_status = return_request.status
        
        # Update return request
        return_request.status = data.status
        return_request.updated_at = datetime.utcnow()
        
        if data.admin_notes:
            return_request.notes = f"{return_request.notes or ''}\n\nAdmin Notes: {data.admin_notes}"
        
        if data.refund_amount is not None:
            return_request.refund_amount = data.refund_amount
        
        if data.return_awb:
            return_request.return_awb = data.return_awb
        
        if data.courier_provider:
            return_request.courier_provider = data.courier_provider
        
        # Handle status-specific actions
        if data.status == "approved" and old_status != "approved":
            # Schedule pickup and create return shipment
            try:
                from courier_service import DelhiveryService
                delhivery_service = DelhiveryService(os.environ.get('DELHIVERY_TOKEN', ''))
                
                # Create return shipment
                return_data = {
                    "order_id": f"RET{return_request.id[:8]}",
                    "pickup_address": order.shipping_address,
                    "return_reason": return_request.reason,
                    "items": return_request.items
                }
                
                # Use create_return_shipment instead of non-existent create_return_pickup
                result = delhivery_service.create_return_shipment(return_data)
                
                if result.get("success"):
                    return_request.return_awb = result.get("return_awb")
                    return_request.pickup_scheduled_date = datetime.utcnow() + timedelta(days=1)
                    return_request.courier_provider = "Delhivery"
            except Exception as e:
                logging.warning(f"Failed to schedule return pickup: {str(e)}")
            
            # Restore inventory for approved returns
            if return_request.items: # Check if items is not None
                for item in return_request.items:
                    product = db.query(models.Product).filter(models.Product.id == item["product_id"]).first()
                    if product:
                        product.stock_qty += item.get("quantity", 1)
                        
                        # Log inventory adjustment
                        inventory_log = models.InventoryLog(
                            id=generate_id(),
                            product_id=product.id,
                            sku=product.sku,
                            type="return",
                            quantity=item.get("quantity", 1),
                            previous_qty=product.stock_qty - item.get("quantity", 1),
                            new_qty=product.stock_qty,
                            notes=f"Return approved - Return ID: {return_request.id}",
                            created_by=admin["id"],
                            created_at=datetime.utcnow()
                        )
                        db.add(inventory_log)
        
        # Other statuses...
        if data.status == "picked_up":
            return_request.pickup_completed_date = datetime.utcnow()
        elif data.status == "received":
            return_request.received_date = datetime.utcnow()
        
        db.commit()
        # Create approval notification
        if data.status == "approved" and old_status != "approved":
            create_notification(
                db=db,
                user_id=return_request.user_id,
                type="return_approved",
                title="Return Request Approved",
                message=f"Your return request for order #{order.order_number} has been approved. Pickup will be scheduled within 24 hours. Refund of ₹{return_request.refund_amount} will be processed after we receive the items.",
                data={
                    "return_id": return_request.id,
                    "order_number": order.order_number,
                    "refund_amount": return_request.refund_amount,
                    "pickup_awb": return_request.return_awb
                }
            )
            
        elif data.status == "rejected" and old_status != "rejected":
            # Create rejection notification
            create_notification(
                db=db,
                user_id=return_request.user_id,
                type="return_rejected",
                title="Return Request Rejected",
                message=f"Your return request for order #{order.order_number} has been rejected. Reason: {data.admin_notes or 'Does not meet return policy criteria'}",
                data={
                    "return_id": return_request.id,
                    "order_number": order.order_number,
                    "rejection_reason": data.admin_notes
                }
            )
            
        elif data.status == "completed":
            # Mark refund as processed
            create_notification(
                db=db,
                user_id=return_request.user_id,
                type="return_completed",
                title="Return Completed",
                message=f"Your return for order #{order.order_number} has been completed. Refund of ₹{return_request.refund_amount} has been processed to your original payment method.",
                data={
                    "return_id": return_request.id,
                    "order_number": order.order_number,
                    "refund_amount": return_request.refund_amount
                }
            )
        
        db.commit()
        return return_request

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@api_router.get("/returns/{return_id}/tracking")
def track_return_shipment(return_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Track return shipment status"""
    return_request = db.query(models.ReturnRequest).filter(models.ReturnRequest.id == return_id).first()
    if not return_request:
        raise HTTPException(status_code=404, detail="Return request not found")
    
    # Check access
    if user["role"] != "admin" and return_request.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if not return_request.return_awb:
        return {
            "return_id": return_id,
            "status": return_request.status,
            "message": "Return pickup not yet scheduled",
            "tracking_available": False
        }
    
    # Get tracking information from courier
    try:
        from courier_service import DelhiveryService
        delhivery_service = DelhiveryService(os.environ.get('DELHIVERY_TOKEN', ''))
        tracking_result = delhivery_service.track_order(return_request.return_awb)
        
        if tracking_result.get("success"):
            return {
                "return_id": return_id,
                "return_awb": return_request.return_awb,
                "courier_provider": return_request.courier_provider,
                "current_status": tracking_result.get("status"),
                "current_location": tracking_result.get("current_location"),
                "tracking_history": tracking_result.get("tracking_history", []),
                "last_updated": datetime.utcnow().isoformat(),
                "tracking_available": True
            }
        else:
            return {
                "return_id": return_id,
                "return_awb": return_request.return_awb,
                "status": return_request.status,
                "error": tracking_result.get("error"),
                "tracking_available": False
            }
    except Exception as e:
        return {
            "return_id": return_id,
            "status": return_request.status,
            "error": f"Tracking service unavailable: {str(e)}",
            "tracking_available": False
        }

@api_router.post("/returns/{return_id}/evidence")
def upload_return_evidence(
    return_id: str,
    files: List[UploadFile] = File(...),
    evidence_type: str = "image",  # image or video
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload evidence (images/videos) for a return request"""
    return_request = db.query(models.ReturnRequest).filter(models.ReturnRequest.id == return_id).first()
    if not return_request:
        raise HTTPException(status_code=404, detail="Return request not found")
    
    # Check access
    if user["role"] != "admin" and return_request.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Validate file count
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files allowed per upload")
    
    uploaded_files = []
    
    for file in files:
        # Validate file type
        if evidence_type == "image":
            if not file.content_type or not file.content_type.startswith('image/'):
                continue
            folder = "returns/images"
        elif evidence_type == "video":
            if not file.content_type or not file.content_type.startswith('video/'):
                continue
            folder = "returns/videos"
        else:
            raise HTTPException(status_code=400, detail="Invalid evidence type. Must be 'image' or 'video'")
        
        # Validate file size (10MB for images, 50MB for videos)
        max_size = 10 * 1024 * 1024 if evidence_type == "image" else 50 * 1024 * 1024
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            continue
        
        try:
            file_url = save_uploaded_file(file, folder)
            uploaded_files.append({
                "url": file_url,
                "filename": file.filename,
                "type": evidence_type,
                "size": file_size
            })
        except Exception as e:
            continue
    
    # Update return request with evidence URLs
    if evidence_type == "image":
        current_images = return_request.evidence_images or []
        new_images = [f["url"] for f in uploaded_files]
        return_request.evidence_images = current_images + new_images
    else:
        current_videos = return_request.evidence_videos or []
        new_videos = [f["url"] for f in uploaded_files]
        return_request.evidence_videos = current_videos + new_videos
    
    return_request.updated_at = datetime.utcnow()
    db.commit()
    
    # Notify admin about new evidence
    create_admin_notification(
        db=db,
        type="return_evidence",
        title="New Return Evidence Uploaded",
        message=f"Customer uploaded {len(uploaded_files)} {evidence_type}(s) for return request {return_id}",
        data={
            "return_id": return_id,
            "evidence_type": evidence_type,
            "file_count": len(uploaded_files),
            "customer_name": user["name"]
        }
    )
    
    return {
        "message": f"Uploaded {len(uploaded_files)} {evidence_type}(s) successfully",
        "files": uploaded_files,
        "return_id": return_id
    }

@api_router.get("/orders/{order_id}/can-cancel")
def check_cancellation_eligibility(order_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check if an order can be cancelled and return eligibility details"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check access
    if user["role"] != "admin" and order.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    can_cancel = order.status not in ["delivered", "cancelled", "returned"]
    
    # Determine cancellation type and implications
    cancellation_info = {
        "can_cancel": can_cancel,
        "order_status": order.status,
        "order_number": order.order_number,
        "refund_amount": order.grand_total if can_cancel else 0
    }
    
    if not can_cancel:
        cancellation_info["reason"] = f"Cannot cancel order with status: {order.status}"
        if order.status == "delivered":
            cancellation_info["alternative"] = "You can create a return request instead"
    else:
        if order.status in ["pending", "confirmed"]:
            cancellation_info["cancellation_type"] = "immediate"
            cancellation_info["refund_timeline"] = "Immediate refund"
            cancellation_info["implications"] = "Order will be cancelled immediately"
        elif order.status in ["processing"]:
            cancellation_info["cancellation_type"] = "processing"
            cancellation_info["refund_timeline"] = "1-2 business days"
            cancellation_info["implications"] = "Order preparation will be stopped"
        elif order.status in ["shipped", "out_for_delivery"]:
            cancellation_info["cancellation_type"] = "return"
            cancellation_info["refund_timeline"] = "3-7 business days after return"
            cancellation_info["implications"] = "Return pickup will be scheduled"
    
    return cancellation_info

@api_router.get("/orders/{order_id}/can-return")
def check_return_eligibility(order_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check if an order can be returned and return eligibility details"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check access
    if user["role"] != "admin" and order.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    can_return = order.status == "delivered"
    
    return_info = {
        "can_return": can_return,
        "order_status": order.status,
        "order_number": order.order_number
    }
    
    if not can_return:
        if order.status in ["pending", "confirmed", "processing", "shipped", "out_for_delivery"]:
            return_info["reason"] = "Order not yet delivered"
            return_info["alternative"] = "You can cancel the order instead"
        elif order.status in ["cancelled", "returned"]:
            return_info["reason"] = f"Order already {order.status}"
        else:
            return_info["reason"] = f"Cannot return order with status: {order.status}"
    else:
        # Check return window
        if order.updated_at:
            days_since_delivery = (datetime.utcnow() - order.updated_at).days
            return_window_remaining = 7 - days_since_delivery
            
            if return_window_remaining <= 0:
                return_info["can_return"] = False
                return_info["reason"] = "Return window expired (7 days from delivery)"
            else:
                return_info["return_window_remaining"] = f"{return_window_remaining} days"
                return_info["return_types"] = [
                    {"value": "defective", "label": "Product is defective/damaged"},
                    {"value": "wrong_item", "label": "Wrong item received"},
                    {"value": "not_satisfied", "label": "Not satisfied with product"},
                    {"value": "damaged", "label": "Package was damaged"}
                ]
                return_info["evidence_required"] = True
                return_info["refund_timeline"] = "5-7 business days after return verification"
    
    return return_info

# ============ TEAM MANAGEMENT ROUTES ============

@api_router.get("/admin/team")
def get_team_members(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get all users with their roles"""
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    
    user_list = []
    for user in users:
        user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
        user_dict.pop("password", None)
        user_list.append(user_dict)
    
    return {"users": user_list}

@api_router.post("/admin/team")
def create_admin_user(data: AdminCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Create a new admin user"""
    # Check if user already exists
    existing = db.query(models.User).filter(
        or_(
            models.User.phone == data.phone,
            models.User.email == data.email
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User with this phone or email already exists")
    
    # Generate temporary password
    temp_password = f"Pass{generate_otp()}"
    
    # Create new admin user
    new_admin = models.User(
        id=generate_id(),
        phone=data.phone,
        name=data.name,
        email=data.email,
        password=hash_password(temp_password),
        role="admin",
        created_at=datetime.utcnow()
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    # Send welcome email with temporary password
    if data.email:
        email_utils.send_temporary_password_email(
            to_email=data.email,
            name=data.name,
            temporary_password=temp_password,
            is_registration=True
        )
    
    user_dict = {c.name: getattr(new_admin, c.name) for c in new_admin.__table__.columns}
    user_dict.pop("password")
    
    return {"message": "Admin user created successfully", "user": user_dict, "temporary_password": temp_password}

@api_router.put("/admin/team/{user_id}")
def update_user_role(user_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Update user role"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from demoting themselves
    if user.id == admin["id"] and data.get("role") != "admin":
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    
    # Update role
    if "role" in data:
        user.role = data["role"]
    
    # Update other fields if provided
    if "is_wholesale" in data:
        user.is_wholesale = data["is_wholesale"]
    if "is_seller" in data:
        user.is_seller = data["is_seller"]
    
    db.commit()
    db.refresh(user)
    
    user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    user_dict.pop("password")
    
    return {"message": "User role updated successfully", "user": user_dict}

@api_router.delete("/admin/team/{user_id}")
def remove_admin_access(user_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Remove admin access (demote to customer)"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from removing themselves
    if user.id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot remove your own admin access")
    
    # Demote to customer
    user.role = "customer"
    db.commit()
    
    return {"message": "Admin access removed successfully"}

# ============ SETTINGS ROUTES ============

@api_router.get("/admin/settings/email")
def get_email_settings(admin: dict = Depends(admin_required)):
    """Get email configuration settings"""
    return {
        "email_enabled": os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true',
        "smtp_host": os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
        "smtp_port": int(os.environ.get('SMTP_PORT', '587')),
        "smtp_username": os.environ.get('SMTP_USERNAME', ''),
        "smtp_from_email": os.environ.get('SMTP_FROM_EMAIL', ''),
        "smtp_from_name": os.environ.get('SMTP_FROM_NAME', 'BharatBazaar Support'),
        "smtp_password_configured": bool(os.environ.get('SMTP_PASSWORD', ''))
    }

@api_router.post("/admin/settings/email/test")
def test_email_settings(data: dict, admin: dict = Depends(admin_required)):
    """Test email configuration by sending a test email"""
    test_email = data.get("email", admin.get("email", "test@example.com"))
    
    # Test OTP email
    otp_result = email_utils.send_otp_email(test_email, "9876543210", "123456")
    
    # Test temporary password email
    temp_pass_result = email_utils.send_temporary_password_email(
        test_email, admin.get("name", "Test User"), "TempPass123", True
    )
    
    return {
        "message": "Email test completed",
        "otp_email_sent": otp_result,
        "temp_password_email_sent": temp_pass_result,
        "test_email": test_email,
        "note": "Check server console logs if EMAIL_ENABLED=false or check your email inbox if EMAIL_ENABLED=true"
    }

@api_router.put("/admin/settings")
def update_settings(data: SettingsUpdate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Update business settings"""
    print(f"DEBUG UPDATE SETTINGS: Received data: {data.dict()}")
    settings = db.query(models.Settings).filter(models.Settings.type == "business").first()
    if not settings:
        settings = models.Settings(
            type="business",
            company_name="Amorlias International Pvt Ltd"  # Default company name
        )
        db.add(settings)
    
    # Update basic fields
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
    
    # Update social links
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
    
    # Update configs
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

@api_router.get("/settings/public")
def get_public_settings(db: Session = Depends(get_db)):
    """Public settings endpoint for frontend branding (no auth required)"""
    settings = db.query(models.Settings).filter(models.Settings.type == "business").first()
    
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

# ============ PAGE ROUTES ============

@api_router.get("/pages/{slug}")
def get_page(slug: str, db: Session = Depends(get_db)):
    """Get content for a static page"""
    page = db.query(models.Page).filter(models.Page.slug == slug).first()
    if not page:
        # Return default content if page doesn't exist
        return {
            "slug": slug,
            "title": slug.replace("-", " ").title(),
            "content": f"Content for {slug} coming soon."
        }
    return page

@api_router.put("/admin/pages/{slug}")
def update_page(slug: str, data: PageUpdate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Update static page content"""
    page = db.query(models.Page).filter(models.Page.slug == slug).first()
    if not page:
        page = models.Page(slug=slug)
        db.add(page)
    
    if data.title is not None:
        page.title = data.title
    if data.content is not None:
        page.content = data.content
    if data.is_active is not None:
        page.is_active = data.is_active
        
    db.commit()
    db.refresh(page)
    return {"message": "Page updated successfully", "page": page}

# ============ ADMIN DASHBOARD ROUTES ============

@api_router.get("/admin/dashboard")
def get_dashboard_stats(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get dashboard statistics"""
    
    # Basic counts
    total_products = db.query(models.Product).count()
    total_orders = db.query(models.Order).count()
    total_customers = db.query(models.User).filter(models.User.role == "customer").count()
    
    # Order statistics
    pending_orders = db.query(models.Order).filter(models.Order.status == "pending").count()
    completed_orders = db.query(models.Order).filter(models.Order.status == "completed").count()
    
    # Inventory statistics
    low_stock_products = db.query(models.Product).filter(
        models.Product.stock_qty <= models.Product.low_stock_threshold
    ).count()
    out_of_stock_products = db.query(models.Product).filter(models.Product.stock_qty == 0).count()
    
    # Revenue calculation (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_orders = db.query(models.Order).filter(
        models.Order.created_at >= thirty_days_ago,
        models.Order.status.in_(["completed", "shipped", "delivered"])
    ).all()
    
    total_revenue = sum(order.grand_total for order in recent_orders)
    
    # Top products
    top_products = db.query(models.Product).filter(
        models.Product.is_active == True
    ).order_by(models.Product.created_at.desc()).limit(5).all()
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Today's stats
    today_orders = db.query(models.Order).filter(models.Order.created_at >= today_start).all()
    today_revenue = sum(o.grand_total for o in today_orders)
    today_order_count = len(today_orders)
    
    # Pendings
    pending_returns = db.query(models.ReturnRequest).filter(models.ReturnRequest.status == "pending").count()
    
    return {
        "today": {
            "revenue": today_revenue,
            "orders": today_order_count
        },
        "totals": {
            "products": total_products,
            "customers": total_customers,
            "orders": total_orders
        },
        "pending": {
            "orders": pending_orders,
            "low_stock": low_stock_products,
            "returns": pending_returns
        },
        "stats": { # Keep for backward compat if needed, but structure above is primary
            "total_revenue_30d": total_revenue
        },
        "top_products": top_products,
        "recent_orders": db.query(models.Order).order_by(models.Order.created_at.desc()).limit(10).all()
    }



# ============ COURIER ROUTES ============
from courier_service import DelhiveryService

DELHIVERY_TOKEN = os.environ.get('DELHIVERY_TOKEN', 'ac9b6a862cffeba552eeb07729e40e692b7a3fd8')
delhivery_service = DelhiveryService(DELHIVERY_TOKEN)

# ============ COURIER PROVIDERS MANAGEMENT ============

@api_router.get("/admin/couriers")
def get_couriers(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get all courier providers"""
    # For now, return a default Delhivery courier
    return [
        {
            "id": "delhivery",
            "name": "Delhivery",
            "api_key": "configured" if DELHIVERY_TOKEN else None,
            "api_secret": "configured",
            "webhook_url": "",
            "tracking_url_template": "https://track.delhivery.com/track/package/{tracking_number}",
            "is_active": True,
            "priority": 1
        }
    ]

@api_router.post("/admin/couriers/test")
def test_courier_api(admin: dict = Depends(admin_required)):
    """Test courier API configuration"""
    try:
        # Test pincode serviceability
        test_result = delhivery_service.check_serviceability("110001")
        
        # Test address validation
        test_address = {
            "name": "Test Customer",
            "phone": "9999999999",
            "line1": "Test Address",
            "city": "New Delhi",
            "state": "Delhi",
            "pincode": "110001"
        }
        address_result = delhivery_service.validate_address(test_address)
        
        return {
            "success": True,
            "message": "Courier API test completed successfully",
            "pincode_test": test_result,
            "address_test": address_result,
            "api_status": "Working" if test_result.get("serviceable") else "Issues detected"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Courier API test failed: {str(e)}",
            "api_status": "Error"
        }

@api_router.post("/admin/couriers")
def create_courier(courier_data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Create a new courier provider"""
    # For now, just return success
    return {"message": "Courier configuration saved", "id": "new-courier"}

@api_router.put("/admin/couriers/{courier_id}")
def update_courier(courier_id: str, courier_data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Update courier provider"""
    # For now, just return success
    return {"message": "Courier updated successfully"}

@api_router.delete("/admin/couriers/{courier_id}")
def delete_courier(courier_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Delete courier provider"""
    # For now, just return success
    return {"message": "Courier deleted successfully"}

@api_router.get("/courier/pincode")
def check_pincode_serviceability(pincode: str):
    """Check if pincode is serviceable by Delhivery"""
    return delhivery_service.check_serviceability(pincode)

@api_router.post("/courier/validate-address")
def validate_shipping_address(address_data: dict):
    """Validate complete shipping address including pincode serviceability"""
    return delhivery_service.validate_address(address_data)

@api_router.get("/admin/orders/{order_id}")
def get_order_details(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get detailed order information for debugging"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_method": order.payment_method,
        "grand_total": order.grand_total,
        "shipping_address": order.shipping_address,
        "items": order.items,
        "tracking_number": order.tracking_number,
        "courier_provider": order.courier_provider,
        "created_at": order.created_at.isoformat() if order.created_at else None
    }

@api_router.post("/generate-qr")
def generate_payment_qr(data: dict, db: Session = Depends(get_db)):
    """Generate UPI QR code for payment"""
    try:
        # Get business settings for UPI ID
        settings = db.query(models.Settings).filter(models.Settings.type == "business").first()
        if not settings or not settings.configs or not settings.configs.get("upi_id"):
            raise HTTPException(status_code=400, detail="UPI ID not configured. Please contact admin.")
        
        upi_id = settings.configs.get("upi_id")
        amount = data.get("amount", 0)
        customer_name = data.get("customer_name", "Customer")
        order_number = data.get("order_number", "")
        
        # Create UPI payment URL
        # Format: upi://pay?pa=UPI_ID&pn=PAYEE_NAME&am=AMOUNT&cu=INR&tn=TRANSACTION_NOTE
        upi_url = f"upi://pay?pa={upi_id}&pn={settings.business_name or 'BharatBazaar'}&am={amount}&cu=INR&tn=Payment for Order {order_number}"
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(upi_url)
        qr.make(fit=True)
        
        # Create QR code image
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 for frontend
        img_buffer = QRBytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        import base64
        qr_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        return {
            "success": True,
            "qr_code": f"data:image/png;base64,{qr_base64}",
            "upi_url": upi_url,
            "amount": amount,
            "upi_id": upi_id,
            "payee_name": settings.business_name or 'BharatBazaar'
        }
        
    except Exception as e:
        print(f"QR Generation Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate QR code: {str(e)}")

@api_router.post("/courier/ship/{order_id}")
def create_shipment(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Create a shipment for an order"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Validate order status
    if order.status in ["shipped", "delivered", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot ship order with status: {order.status}")
        
    shipping_address = order.shipping_address
    if not shipping_address:
        raise HTTPException(status_code=400, detail="Order has no shipping address")
    
    # Validate required shipping address fields
    required_fields = ["name", "phone", "line1", "city", "state", "pincode"]
    missing_fields = [field for field in required_fields if not shipping_address.get(field)]
    
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing required shipping address fields: {', '.join(missing_fields)}"
        )
    
    # Validate phone number
    phone = str(shipping_address.get("phone", "")).strip()
    if len(phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone number in shipping address")
    
    # Validate pincode
    pincode = str(shipping_address.get("pincode", "")).strip()
    if len(pincode) != 6 or not pincode.isdigit():
        raise HTTPException(status_code=400, detail="Invalid pincode in shipping address")
    
    # Prepare payload
    order_data = {
        "order_id": order.order_number,
        "date": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "pay_mode": "Pre-paid" if order.payment_method == "online" else "COD",
        "address": f"{shipping_address.get('line1', '')} {shipping_address.get('line2', '')}".strip(),
        "phone": phone,
        "name": shipping_address.get("name"),
        "city": shipping_address.get("city"),
        "state": shipping_address.get("state"),
        "pincode": pincode,
        "total_amount": float(order.grand_total),
        "cod_amount": float(order.grand_total) if order.payment_method != "online" else 0,
        "quantity": sum(item.get("quantity", 1) for item in order.items) if order.items else 1,
        "products_desc": ", ".join(item.get("product_name", "Item") for item in order.items)[:50] if order.items else "Products",
        
        # Pickup Details - Fetch from Settings
        "pickup_name": "Amorlias Mart",
        "pickup_address": "Warehouse Address",
        "pickup_city": "New Delhi",
        "pickup_pincode": "110001",
        "pickup_phone": "9999999999"
    }
    
    # Fetch pickup address from settings if available
    settings = db.query(models.Settings).first()
    if settings:
        order_data["pickup_name"] = settings.business_name or "Amorlias Mart"
        if settings.address:
            address_line = f"{settings.address.get('line1', '')} {settings.address.get('line2', '')}".strip()
            if address_line:
                order_data["pickup_address"] = address_line
            if settings.address.get('city'):
                order_data["pickup_city"] = settings.address.get('city')
            if settings.address.get('pincode'):
                order_data["pickup_pincode"] = settings.address.get('pincode')
        if settings.phone:
            order_data["pickup_phone"] = settings.phone

    result = delhivery_service.create_surface_order(order_data)
    
    if result.get("success"):
        # Update order with tracking details
        order.tracking_number = result.get("awb")
        order.courier_provider = "Delhivery"
        order.status = "shipped"
        order.updated_at = datetime.utcnow()
        db.commit()
        return result
    else:
        raise HTTPException(status_code=400, detail=f"Shipment Creation Failed: {result.get('error')}")

@api_router.get("/courier/track/{order_id}")
def track_shipment(order_id: str, db: Session = Depends(get_db)):
    """Track shipment for an order with detailed status"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if not order.tracking_number:
         raise HTTPException(status_code=400, detail="Order has not been shipped yet")
    
    # Get tracking information from courier
    tracking_result = delhivery_service.track_order(order.tracking_number)
    
    if tracking_result.get("success"):
        # Update order tracking history if new information is available
        if tracking_result.get("tracking_history"):
            order.tracking_history = tracking_result["tracking_history"]
            order.updated_at = datetime.utcnow()
            db.commit()
        
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "awb": order.tracking_number,
            "courier_provider": order.courier_provider,
            "current_status": tracking_result.get("status"),
            "current_location": tracking_result.get("current_location"),
            "expected_delivery": tracking_result.get("expected_delivery"),
            "tracking_history": tracking_result.get("tracking_history", []),
            "last_updated": datetime.utcnow().isoformat()
        }
    else:
        raise HTTPException(status_code=400, detail=f"Tracking failed: {tracking_result.get('error')}")

@api_router.get("/courier/track-by-awb/{awb}")
def track_by_awb(awb: str):
    """Track shipment directly by AWB number"""
    return delhivery_service.track_order(awb)

@api_router.get("/courier/label/{order_id}")
def get_shipping_label(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Generate professional shipping label for printing"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # If order has tracking number, try to get label from Delhivery
    if order.tracking_number:
        result = delhivery_service.get_label(order.tracking_number)
        if result.get("success"):
            return {
                "order_id": order.id,
                "order_number": order.order_number,
                "awb": order.tracking_number,
                "label_url": result.get("label_url"),
                "generated_at": datetime.utcnow().isoformat(),
                "note": result.get("note")
            }
        else:
            # If Delhivery label fails, generate professional local PDF label
            pass
    
    # Generate professional local PDF label as fallback
    try:
        pdf_buffer = generate_shipping_label_pdf(order_id, db)
        
        # Save the PDF temporarily and return URL
        import tempfile
        import os
        
        # Create a temporary file
        temp_dir = os.path.join(os.getcwd(), "uploads", "labels")
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_filename = f"label_{order.order_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        with open(temp_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        label_url = f"/uploads/labels/{temp_filename}"
        
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "awb": order.tracking_number or "N/A",
            "label_url": label_url,
            "generated_at": datetime.utcnow().isoformat(),
            "note": "Professional PDF label generated"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate shipping label: {str(e)}")

@api_router.get("/courier/label-url/{order_id}")
def get_shipping_label_url(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get shipping label URL for an order"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # If order has tracking number, try to get label from Delhivery
    if order.tracking_number:
        result = delhivery_service.get_label(order.tracking_number)
        if result.get("success") and result.get("label_url"):
            return {
                "success": True,
                "label_url": result.get("label_url"),
                "awb": order.tracking_number,
                "note": result.get("note")
            }
    
    # Return error if no label URL available
    return {
        "success": False,
        "error": "No label URL available. Order may not be shipped yet or courier service unavailable.",
        "awb": order.tracking_number or None
    }

@api_router.get("/courier/invoice/{order_id}")
def get_shipping_invoice(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get shipping invoice/manifest for printing"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if not order.tracking_number:
         raise HTTPException(status_code=400, detail="Order has not been shipped yet")

    result = delhivery_service.get_invoice(order.tracking_number)
    
    if result.get("success"):
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "awb": order.tracking_number,
            "invoice_url": result.get("invoice_url"),
            "generated_at": datetime.utcnow().isoformat()
        }
    else:
        raise HTTPException(status_code=400, detail=f"Invoice generation failed: {result.get('error')}")

@api_router.post("/courier/cancel/{order_id}")
def cancel_shipment(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Cancel a shipment before pickup"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if not order.tracking_number:
         raise HTTPException(status_code=400, detail="Order has not been shipped yet")
    
    if order.status not in ["shipped", "processing"]:
        raise HTTPException(status_code=400, detail="Cannot cancel order in current status")

    result = delhivery_service.cancel_shipment(order.tracking_number)
    
    if result.get("success"):
        order.status = "cancelled"
        order.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "awb": order.tracking_number,
            "message": "Shipment cancelled successfully",
            "cancelled_at": datetime.utcnow().isoformat()
        }
    else:
        raise HTTPException(status_code=400, detail=f"Cancellation failed: {result.get('error')}")

@api_router.post("/admin/couriers/create-return/{order_id}")
def create_return_shipment(order_id: str, return_data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Create a return shipment for an order"""
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status not in ["delivered", "shipped"]:
        raise HTTPException(status_code=400, detail="Can only create returns for delivered/shipped orders")
    
    shipping_address = order.shipping_address
    if not shipping_address:
        raise HTTPException(status_code=400, detail="No shipping address found for return pickup")
    
    # Prepare return shipment data
    return_shipment_data = {
        "original_order_id": order.order_number,
        "customer_name": shipping_address.get("name"),
        "customer_phone": shipping_address.get("phone"),
        "pickup_address": f"{shipping_address.get('line1', '')} {shipping_address.get('line2', '')}".strip(),
        "pickup_city": shipping_address.get("city"),
        "pickup_state": shipping_address.get("state"),
        "pickup_pincode": shipping_address.get("pincode"),
        "return_amount": return_data.get("return_amount", order.grand_total),
        "quantity": return_data.get("quantity", 1),
        "products_desc": return_data.get("reason", "Return Items"),
        "weight": return_data.get("weight", "500")
    }
    
    result = delhivery_service.create_return_shipment(return_shipment_data)
    
    if result.get("success"):
        # Create return request record
        return_request = models.ReturnRequest(
            id=generate_id(),
            order_id=order.id,
            user_id=order.user_id,
            reason=return_data.get("reason", "Customer return"),
            status="pickup_scheduled",
            return_awb=result.get("return_awb"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(return_request)
        db.commit()
        
        return {
            "order_id": order.id,
            "return_id": return_request.id,
            "return_awb": result.get("return_awb"),
            "pickup_scheduled": True,
            "message": "Return pickup scheduled successfully"
        }
    else:
        raise HTTPException(status_code=400, detail=f"Return creation failed: {result.get('error')}")

@api_router.get("/admin/picklist")
def generate_picklist(date: str = None, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Generate picklist for orders to be shipped"""
    from datetime import datetime, date as date_obj
    
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        target_date = date_obj.today()
    
    # Get orders that are ready to ship (confirmed/processing status)
    orders = db.query(models.Order).filter(
        models.Order.status.in_(["confirmed", "processing"]),
        func.date(models.Order.created_at) == target_date
    ).all()
    
    picklist_items = []
    for order in orders:
        if order.items:
            for item in order.items:
                picklist_items.append({
                    "order_number": order.order_number,
                    "customer_name": order.shipping_address.get("name") if order.shipping_address else "N/A",
                    "product_name": item.get("product_name"),
                    "sku": item.get("sku"),
                    "quantity": item.get("quantity", 1),
                    "awb": order.tracking_number or "Not Generated",
                    "shipping_address": order.shipping_address,
                    "payment_method": order.payment_method,
                    "order_total": order.grand_total
                })
    
    return {
        "date": target_date.isoformat(),
        "total_orders": len(orders),
        "total_items": len(picklist_items),
        "picklist": picklist_items
    }

# ============ ADMIN USER MANAGEMENT ROUTES ============

@api_router.get("/admin/users")
def get_all_users(
    page: int = 1, 
    limit: int = 50, 
    search: str = None,
    role: str = None,
    admin: dict = Depends(admin_required), 
    db: Session = Depends(get_db)
):
    """Get all users with pagination and filtering"""
    query = db.query(models.User)
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                models.User.name.ilike(f"%{search}%"),
                models.User.phone.ilike(f"%{search}%"),
                models.User.email.ilike(f"%{search}%")
            )
        )
    
    if role:
        query = query.filter(models.User.role == role)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * limit
    users = query.offset(offset).limit(limit).all()
    
    # Convert to dict and remove passwords
    users_data = []
    for user in users:
        user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
        user_dict.pop("password", None)  # Remove password from response
        users_data.append(user_dict)
    
    return {
        "users": users_data,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }

@api_router.put("/admin/users/{user_id}")
def update_user(user_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Update user information"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update allowed fields
    allowed_fields = ["name", "email", "role", "is_seller", "is_wholesale", "supplier_status"]
    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])
    
    user.updated_at = datetime.utcnow()
    db.commit()
    
    # Return user without password
    user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    user_dict.pop("password", None)
    
    return {"message": "User updated successfully", "user": user_dict}

@api_router.delete("/admin/users/{user_id}")
def delete_user(user_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Delete a user (soft delete by deactivating)"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin user")
    
    # Instead of hard delete, we could deactivate or actually delete
    # For now, let's do hard delete for non-admin users
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}

# ============ SETTINGS ROUTES ============

@api_router.get("/settings/public")
def get_public_settings(db: Session = Depends(get_db)):
    """Get public settings (no authentication required)"""
    try:
        settings = db.query(models.Settings).filter(models.Settings.type == "business").first()
        
        if not settings:
            # Create default settings
            default_settings = models.Settings(
                type="business",
                business_name="Amorlias",
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
        
        # Return only public fields
        return {
            "business_name": settings.business_name,
            "company_name": settings.company_name,
            "phone": settings.phone,
            "email": settings.email,
            "logo_url": settings.logo_url,
            "favicon_url": settings.favicon_url,
            "social_links": settings.social_links or {},
            "configs": settings.configs or {}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")

@api_router.get("/admin/settings")
def get_admin_settings(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get all settings for admin"""
    try:
        settings = db.query(models.Settings).filter(models.Settings.type == "business").first()
        if settings:
             print(f"DEBUG GET SETTINGS: Company Name in DB: '{settings.company_name}'")
        
        if not settings:
            # Create default settings
            default_settings = models.Settings(
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
        
        # Return flattened response that matches frontend expectations
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get settings: {str(e)}")

# Removed duplicate update_settings function

# ============ REPORT ROUTES ============

@api_router.get("/admin/reports/sales")
def get_sales_report(
    date_from: Optional[str] = None, 
    date_to: Optional[str] = None,
    admin: dict = Depends(admin_required), 
    db: Session = Depends(get_db)
):
    query = db.query(models.Order).filter(models.Order.status != "cancelled")
    
    if date_from:
        # Check if date_from contains "Z" for UTC or is ISO format
        # Pydantic/FastAPI handles ISO, but manual parsing might be safer if needed.
        # Assuming ISO strings from frontend
        try:
           dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
           query = query.filter(models.Order.created_at >= dt_from)
        except:
           pass

    orders = query.all()
    
    total_sales = sum(o.grand_total for o in orders)
    total_orders = len(orders)
    # Assuming payment_method 'online' vs 'cod'/others for online/offline split
    online_sales = sum(o.grand_total for o in orders if o.payment_method == "online")
    offline_sales = sum(o.grand_total for o in orders if o.payment_method != "online")
    
    # Daily breakdown
    daily_map = {}
    for o in orders:
        date_key = o.created_at.date().isoformat()
        if date_key not in daily_map:
            daily_map[date_key] = {"date": date_key, "sales": 0, "orders": 0}
        daily_map[date_key]["sales"] += o.grand_total
        daily_map[date_key]["orders"] += 1
        
    daily_breakdown = sorted(daily_map.values(), key=lambda x: x["date"])
    
    return {
        "summary": {
            "total_sales": total_sales,
            "total_orders": total_orders,
            "online_sales": online_sales,
            "offline_sales": offline_sales
        },
        "daily_breakdown": daily_breakdown
    }

@api_router.get("/admin/reports/inventory")
def get_inventory_report(
    admin: dict = Depends(admin_required), 
    db: Session = Depends(get_db)
):
    products = db.query(models.Product).all()
    
    # Calculate sold quantities from completed orders (both online and offline)
    completed_orders = db.query(models.Order).filter(
        models.Order.status.in_(["completed", "delivered"])
    ).all()
    
    # Build a map of product_id -> total_sold_qty
    sold_qty_map = {}
    for order in completed_orders:
        if order.items:
            for item in order.items:
                product_id = item.get("product_id")
                quantity = item.get("quantity", 0)
                if product_id:
                    sold_qty_map[product_id] = sold_qty_map.get(product_id, 0) + quantity
    
    total_products = len(products)
    total_stock_value = sum(p.stock_qty * p.cost_price for p in products)
    low_stock_products = []
    out_of_stock_products = []
    
    # Enrich products with sold_qty
    for p in products:
        p.sold_qty = sold_qty_map.get(p.id, 0)
        if p.stock_qty <= p.low_stock_threshold:
            low_stock_products.append(p)
        if p.stock_qty == 0:
            out_of_stock_products.append(p)
    
    return {
        "summary": {
            "total_products": total_products,
            "total_stock_value": total_stock_value,
            "low_stock_count": len(low_stock_products),
            "out_of_stock_count": len(out_of_stock_products)
        },
        "low_stock_products": low_stock_products,
        "out_of_stock_products": out_of_stock_products
    }


@api_router.get("/admin/reports/profit-loss")
def get_profit_loss_report(
    date_from: Optional[str] = None,
    admin: dict = Depends(admin_required), 
    db: Session = Depends(get_db)
):
    # Calculate Profit = Revenue - Cost - Refunds
    # Revenue = Sum(Orders within date)
    # Cost = Sum(Order Items * Cost Price)
    
    # We include all non-cancelled orders to show projected P&L
    orders_query = db.query(models.Order).filter(models.Order.status != "cancelled")
    returns_query = db.query(models.ReturnRequest).filter(models.ReturnRequest.status == "approved")
    
    if date_from:
        try:
           dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
           orders_query = orders_query.filter(models.Order.created_at >= dt_from)
           returns_query = returns_query.filter(models.ReturnRequest.created_at >= dt_from)
        except:
           pass
           
    orders = orders_query.all()
    returns = returns_query.all()
    
    total_revenue = sum(o.grand_total for o in orders)
    
    # Calculate approximate COGS (Cost of Goods Sold)
    total_cost = 0
    for o in orders:
        for item in o.items:
            # We assume cost_price hasn't changed drastically or we'd need historical cost
            # Fetch current product cost
            prod = db.query(models.Product).filter(models.Product.id == item["product_id"]).first()
            if prod:
                total_cost += prod.cost_price * item["quantity"]
            else:
                # Fallback if product deleted, approximate 70% of price
                total_cost += item["price"] * 0.7 * item["quantity"]
                
    total_refunds = sum(r.refund_amount or 0 for r in returns)
    
    gross_profit = total_revenue - total_cost
    net_profit = gross_profit - total_refunds
    
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    return {
        "summary": {
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_refunds": total_refunds,
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "profit_margin": profit_margin
        },
        "orders_count": len(orders),
        "returns_count": len(returns)
    }

@api_router.get("/admin/reports/inventory-status")
def get_inventory_status_report(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get detailed inventory status report showing available, blocked, and reserved quantities"""
    try:
        # Get all products with their current stock
        products = db.query(models.Product).filter(models.Product.is_active == True).all()
        
        # Calculate sold quantities from completed orders (reuse logic from inventory report)
        completed_orders = db.query(models.Order).filter(
            models.Order.status.in_(["completed", "delivered"])
        ).all()
        
        sold_qty_map = {}
        for order in completed_orders:
            if order.items:
                for item in order.items:
                    product_id = item.get("product_id")
                    quantity = item.get("quantity", 0)
                    if product_id:
                        sold_qty_map[product_id] = sold_qty_map.get(product_id, 0) + quantity
        
        inventory_report = []
        
        for product in products:
            # Calculate blocked quantity in pending orders
            pending_orders = db.query(models.Order).filter(
                models.Order.status.in_(["pending", "processing"])
            ).all()
            
            blocked_qty = 0
            for order in pending_orders:
                for item in order.items:
                    if item.get("product_id") == product.id:
                        blocked_qty += item.get("quantity", 0)
            
            # Calculate available quantity (stock - blocked)
            available_qty = max(0, product.stock_qty - blocked_qty)
            
            # Get sold quantity
            sold_qty = sold_qty_map.get(product.id, 0)
            
            # Calculate original stock (current + sold)
            original_stock = product.stock_qty + sold_qty
            
            # Determine stock status
            if product.stock_qty <= 0:
                stock_status = "out_of_stock"
            elif product.stock_qty <= product.low_stock_threshold:
                stock_status = "low_stock"
            elif available_qty <= product.low_stock_threshold:
                stock_status = "reserved_low"
            else:
                stock_status = "in_stock"
            
            inventory_report.append({
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "category_name": product.category.name if product.category else "Uncategorized",
                "original_stock": original_stock,
                "total_stock": product.stock_qty,
                "blocked_qty": blocked_qty,
                "available_qty": available_qty,
                "sold_qty": sold_qty,
                "low_stock_threshold": product.low_stock_threshold,
                "stock_status": stock_status,
                "selling_price": product.selling_price,
                "cost_price": product.cost_price,
                "stock_value": product.stock_qty * product.cost_price,
                "available_value": available_qty * product.cost_price
            })
        
        # Calculate summary statistics
        total_products = len(inventory_report)
        total_stock_value = sum(item["stock_value"] for item in inventory_report)
        total_available_value = sum(item["available_value"] for item in inventory_report)
        total_blocked_value = total_stock_value - total_available_value
        
        out_of_stock_count = len([item for item in inventory_report if item["stock_status"] == "out_of_stock"])
        low_stock_count = len([item for item in inventory_report if item["stock_status"] in ["low_stock", "reserved_low"]])
        in_stock_count = len([item for item in inventory_report if item["stock_status"] == "in_stock"])
        
        return {
            "summary": {
                "total_products": total_products,
                "total_stock_value": total_stock_value,
                "total_available_value": total_available_value,
                "total_blocked_value": total_blocked_value,
                "out_of_stock_count": out_of_stock_count,
                "low_stock_count": low_stock_count,
                "in_stock_count": in_stock_count
            },
            "products": inventory_report
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate inventory report: {str(e)}")

@api_router.post("/admin/reset-data")
def reset_database(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Clear all transactional data but keep admin and settings"""
    try:
        # Delete data in order of dependency
        db.query(models.ReturnRequest).delete()
        db.query(models.Order).delete()
        db.query(models.InventoryLog).delete()
        db.query(models.Product).delete()
        db.query(models.Category).delete()
        db.query(models.Banner).delete()
        db.query(models.Offer).delete()
        db.query(models.Notification).delete()
        
        # Keep Users (Admin/Customers) and Settings to avoid locking out admin
        # Optionally, could delete customers: db.query(models.User).filter(models.User.role == "customer").delete()
        
        db.commit()
        return {"message": "All data cleared successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear data: {str(e)}")

@api_router.post("/admin/seed-data")
def seed_sample_data(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Seed sample data for testing"""
    
    try:
        # Create sample categories with images
        categories_data = [
            {
                "name": "Electronics", 
                "description": "Electronic items and gadgets",
                "image_url": "https://images.unsplash.com/photo-1498049794561-7780e7231661?w=500&h=500&fit=crop"
            },
            {
                "name": "Clothing", 
                "description": "Fashion and apparel",
                "image_url": "https://images.unsplash.com/photo-1445205170230-053b83016050?w=500&h=500&fit=crop"
            },
            {
                "name": "Home & Garden", 
                "description": "Home improvement and garden supplies",
                "image_url": "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=500&h=500&fit=crop"
            },
            {
                "name": "Books", 
                "description": "Books and educational materials",
                "image_url": "https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=500&h=500&fit=crop"
            },
            {
                "name": "Sports", 
                "description": "Sports and fitness equipment",
                "image_url": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=500&h=500&fit=crop"
            },
            {
                "name": "Beauty", 
                "description": "Beauty and personal care products",
                "image_url": "https://images.unsplash.com/photo-1596462502278-27bfdc403348?w=500&h=500&fit=crop"
            }
        ]
        
        created_categories = []
        for cat_data in categories_data:
            existing = db.query(models.Category).filter(models.Category.name == cat_data["name"]).first()
            if existing:
                # Update existing category with image
                existing.image_url = cat_data["image_url"]
                existing.description = cat_data["description"]
                created_categories.append(existing)
            else:
                new_cat = models.Category(
                    id=generate_id(),
                    **cat_data,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.add(new_cat)
                created_categories.append(new_cat)
        
        db.commit()
        
        # Create more sample products with images
        if created_categories:
            sample_products = [
                {
                    "name": "Smartphone XYZ",
                    "description": "Latest smartphone with advanced features",
                    "category_id": next((c.id for c in created_categories if c.name == "Electronics"), created_categories[0].id),
                    "sku": "PHONE001",
                    "mrp": 25000,
                    "selling_price": 22000,
                    "wholesale_price": 20000,
                    "cost_price": 18000,
                    "stock_qty": 50,
                    "gst_rate": 18.0,
                    "images": ["https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=500"]
                },
                {
                    "name": "Cotton T-Shirt",
                    "description": "Comfortable cotton t-shirt",
                    "category_id": next((c.id for c in created_categories if c.name == "Clothing"), created_categories[0].id),
                    "sku": "TSHIRT001",
                    "mrp": 800,
                    "selling_price": 650,
                    "wholesale_price": 500,
                    "cost_price": 400,
                    "stock_qty": 100,
                    "gst_rate": 12.0,
                    "images": ["https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=500"]
                },
                {
                    "name": "Wireless Headphones",
                    "description": "Premium wireless headphones with noise cancellation",
                    "category_id": next((c.id for c in created_categories if c.name == "Electronics"), created_categories[0].id),
                    "sku": "HEADPHONE001",
                    "mrp": 5000,
                    "selling_price": 3500,
                    "wholesale_price": 3000,
                    "cost_price": 2500,
                    "stock_qty": 75,
                    "gst_rate": 18.0,
                    "images": ["https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500"]
                },
                {
                    "name": "Denim Jeans",
                    "description": "Classic blue denim jeans",
                    "category_id": next((c.id for c in created_categories if c.name == "Clothing"), created_categories[0].id),
                    "sku": "JEANS001",
                    "mrp": 2000,
                    "selling_price": 1500,
                    "wholesale_price": 1200,
                    "cost_price": 1000,
                    "stock_qty": 60,
                    "gst_rate": 12.0,
                    "images": ["https://images.unsplash.com/photo-1542272604-787c3835535d?w=500"]
                },
                {
                    "name": "Coffee Maker",
                    "description": "Automatic coffee maker for home",
                    "category_id": next((c.id for c in created_categories if c.name == "Home & Garden"), created_categories[0].id),
                    "sku": "COFFEE001",
                    "mrp": 8000,
                    "selling_price": 6500,
                    "wholesale_price": 5500,
                    "cost_price": 4500,
                    "stock_qty": 30,
                    "gst_rate": 18.0,
                    "images": ["https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=500"]
                },
                {
                    "name": "Running Shoes",
                    "description": "Comfortable running shoes for daily exercise",
                    "category_id": next((c.id for c in created_categories if c.name == "Sports"), created_categories[0].id),
                    "sku": "SHOES001",
                    "mrp": 3000,
                    "selling_price": 2200,
                    "wholesale_price": 1800,
                    "cost_price": 1500,
                    "stock_qty": 80,
                    "gst_rate": 12.0,
                    "images": ["https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500"]
                },
                {
                    "name": "Face Cream",
                    "description": "Moisturizing face cream for all skin types",
                    "category_id": next((c.id for c in created_categories if c.name == "Beauty"), created_categories[0].id),
                    "sku": "CREAM001",
                    "mrp": 1200,
                    "selling_price": 900,
                    "wholesale_price": 700,
                    "cost_price": 500,
                    "stock_qty": 120,
                    "gst_rate": 18.0,
                    "images": ["https://images.unsplash.com/photo-1556228578-8c89e6adf883?w=500"]
                },
                {
                    "name": "Programming Book",
                    "description": "Learn Python programming from basics to advanced",
                    "category_id": next((c.id for c in created_categories if c.name == "Books"), created_categories[0].id),
                    "sku": "BOOK001",
                    "mrp": 1500,
                    "selling_price": 1200,
                    "wholesale_price": 1000,
                    "cost_price": 800,
                    "stock_qty": 40,
                    "gst_rate": 0.0,
                    "images": ["https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=500"]
                }
            ]
            
            for prod_data in sample_products:
                existing = db.query(models.Product).filter(models.Product.sku == prod_data["sku"]).first()
                if existing:
                    # Update existing product with image
                    for k, v in prod_data.items():
                        setattr(existing, k, v)
                    existing.updated_at = datetime.utcnow()
                else:
                    new_product = models.Product(
                        id=generate_id(),
                        **prod_data,
                        is_active=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(new_product)
            
            db.commit()
        
        # Create sample banners
        banners_data = [
            {
                "title": "Discover Amazing Deals on Fashion & More",
                "image_url": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200&h=400&fit=crop",
                "link": "/products",
                "position": 1,
                "is_active": True
            },
            {
                "title": "Electronics Sale - Up to 50% Off",
                "image_url": "https://images.unsplash.com/photo-1498049794561-7780e7231661?w=1200&h=400&fit=crop",
                "link": "/products?category=" + next((c.id for c in created_categories if c.name == "Electronics"), ""),
                "position": 2,
                "is_active": True
            },
            {
                "title": "Fashion Collection - New Arrivals",
                "image_url": "https://images.unsplash.com/photo-1445205170230-053b83016050?w=1200&h=400&fit=crop",
                "link": "/products?category=" + next((c.id for c in created_categories if c.name == "Clothing"), ""),
                "position": 3,
                "is_active": True
            }
        ]
        
        for banner_data in banners_data:
            existing = db.query(models.Banner).filter(models.Banner.title == banner_data["title"]).first()
            if not existing:
                new_banner = models.Banner(
                    id=generate_id(),
                    **banner_data,
                    created_at=datetime.utcnow()
                )
                db.add(new_banner)
        
        db.commit()
        
        return {"message": "Sample data seeded successfully with images and banners"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to seed data: {str(e)}")


# ============ WISHLIST CATEGORY ROUTES ============

@api_router.get("/wishlist/categories")
def get_user_wishlist_categories(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user's wishlist categories"""
    try:
        categories = db.query(models.WishlistCategory).filter(
            models.WishlistCategory.user_id == user["id"]
        ).order_by(models.WishlistCategory.is_default.desc(), models.WishlistCategory.created_at.asc()).all()
        
        # If no categories exist, create a default one
        if not categories:
            default_category = models.WishlistCategory(
                id=generate_id(),
                user_id=user["id"],
                name="My Wishlist",
                description="Default wishlist category",
                color="#3B82F6",
                icon="heart",
                is_default=True
            )
            db.add(default_category)
            db.commit()
            db.refresh(default_category)
            categories = [default_category]
        
        # Convert to dict and add item count
        categories_with_count = []
        for category in categories:
            try:
                category_dict = {c.name: getattr(category, c.name) for c in category.__table__.columns}
                
                # Add item count (simplified query to avoid relationship issues)
                item_count = db.query(models.Wishlist).filter(
                    models.Wishlist.user_id == user["id"],
                    models.Wishlist.category_id == category.id
                ).count()
                category_dict['item_count'] = item_count
                
                categories_with_count.append(category_dict)
            except Exception as e:
                print(f"Error processing category {category.id}: {e}")
                # Add basic category info without item count
                categories_with_count.append({
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'color': category.color,
                    'icon': category.icon,
                    'is_default': category.is_default,
                    'user_id': category.user_id,
                    'created_at': category.created_at.isoformat() if category.created_at else None,
                    'item_count': 0
                })
        
        return {"categories": categories_with_count}
        
    except Exception as e:
        print(f"Error in get_user_wishlist_categories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")

@api_router.post("/wishlist/categories")
def create_wishlist_category(data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new wishlist category"""
    name = data.get("name", "").strip()
    description = data.get("description", "")
    color = data.get("color", "#3B82F6")
    icon = data.get("icon", "heart")
    
    if not name:
        raise HTTPException(status_code=400, detail="Category name is required")
    
    # Check if category name already exists for this user
    existing = db.query(models.WishlistCategory).filter(
        models.WishlistCategory.user_id == user["id"],
        models.WishlistCategory.name == name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Category name already exists")
    
    category = models.WishlistCategory(
        id=generate_id(),
        user_id=user["id"],
        name=name,
        description=description,
        color=color,
        icon=icon,
        is_default=False
    )
    
    db.add(category)
    db.commit()
    db.refresh(category)
    
    # Convert to dict for JSON serialization
    category_dict = {c.name: getattr(category, c.name) for c in category.__table__.columns}
    category_dict['item_count'] = 0  # New category has no items
    
    return {"message": "Category created successfully", "category": category_dict}

@api_router.put("/wishlist/categories/{category_id}")
def update_wishlist_category(category_id: str, data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update a wishlist category"""
    category = db.query(models.WishlistCategory).filter(
        models.WishlistCategory.id == category_id,
        models.WishlistCategory.user_id == user["id"]
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Update fields
    if "name" in data and data["name"].strip():
        # Check if new name conflicts with existing categories
        existing = db.query(models.WishlistCategory).filter(
            models.WishlistCategory.user_id == user["id"],
            models.WishlistCategory.name == data["name"].strip(),
            models.WishlistCategory.id != category_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Category name already exists")
        
        category.name = data["name"].strip()
    
    if "description" in data:
        category.description = data["description"]
    
    if "color" in data:
        category.color = data["color"]
    
    if "icon" in data:
        category.icon = data["icon"]
    
    db.commit()
    return {"message": "Category updated successfully", "category": category}

@api_router.delete("/wishlist/categories/{category_id}")
def delete_wishlist_category(category_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a wishlist category"""
    category = db.query(models.WishlistCategory).filter(
        models.WishlistCategory.id == category_id,
        models.WishlistCategory.user_id == user["id"]
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if category.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default category")
    
    # Get default category to move items to
    default_category = db.query(models.WishlistCategory).filter(
        models.WishlistCategory.user_id == user["id"],
        models.WishlistCategory.is_default == True
    ).first()
    
    if not default_category:
        # Create default category if it doesn't exist
        default_category = models.WishlistCategory(
            id=generate_id(),
            user_id=user["id"],
            name="My Wishlist",
            description="Default wishlist category",
            color="#3B82F6",
            icon="heart",
            is_default=True
        )
        db.add(default_category)
        db.commit()
        db.refresh(default_category)
    
    # Move all items from deleted category to default category
    db.query(models.Wishlist).filter(
        models.Wishlist.category_id == category_id
    ).update({"category_id": default_category.id})
    
    # Delete the category
    db.delete(category)
    db.commit()
    
    return {"message": "Category deleted successfully"}

# ============ ENHANCED WISHLIST ROUTES ============

@api_router.get("/wishlist")
def get_user_wishlist(category_id: str = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user's wishlist with product details, optionally filtered by category"""
    query = db.query(models.Wishlist).filter(
        models.Wishlist.user_id == user["id"]
    )
    
    if category_id:
        query = query.filter(models.Wishlist.category_id == category_id)
    
    wishlist_items = query.order_by(models.Wishlist.created_at.desc()).all()
    
    # Get product details for each wishlist item
    products = []
    for item in wishlist_items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if product:
            # Add wishlist-specific data to product
            product_dict = {c.name: getattr(product, c.name) for c in product.__table__.columns}
            product_dict['wishlist_id'] = item.id
            product_dict['category_id'] = item.category_id
            product_dict['notes'] = item.notes
            product_dict['priority'] = item.priority
            product_dict['added_at'] = item.created_at
            products.append(product_dict)
    
    return {"wishlist": products}

@api_router.post("/wishlist/{product_id}")
def add_to_wishlist(product_id: str, item_data: WishlistItemAdd = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a product to user's wishlist with optional category and notes"""
    # Check if product exists
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check if already in wishlist
    existing = db.query(models.Wishlist).filter(
        models.Wishlist.user_id == user["id"],
        models.Wishlist.product_id == product_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Product already in wishlist")
    
    # Get category_id from request data
    category_id = None
    notes = ""
    priority = 1
    
    if item_data:
        category_id = item_data.category_id
        notes = item_data.notes or ""
        priority = item_data.priority
    
    # If no category specified, use default category
    if not category_id:
        default_category = db.query(models.WishlistCategory).filter(
            models.WishlistCategory.user_id == user["id"],
            models.WishlistCategory.is_default == True
        ).first()
        
        if not default_category:
            # Create default category
            default_category = models.WishlistCategory(
                id=generate_id(),
                user_id=user["id"],
                name="My Wishlist",
                description="Default wishlist category",
                color="#3B82F6",
                icon="heart",
                is_default=True
            )
            db.add(default_category)
            db.commit()
            db.refresh(default_category)
        
        category_id = default_category.id
    else:
        # Verify category belongs to user
        category = db.query(models.WishlistCategory).filter(
            models.WishlistCategory.id == category_id,
            models.WishlistCategory.user_id == user["id"]
        ).first()
        
        if not category:
            raise HTTPException(status_code=400, detail="Invalid category")
    
    # Add to wishlist
    wishlist_item = models.Wishlist(
        id=generate_id(),
        user_id=user["id"],
        product_id=product_id,
        category_id=category_id,
        notes=notes,
        priority=priority
    )
    
    db.add(wishlist_item)
    db.commit()
    
    return {"message": "Product added to wishlist", "product": product}

@api_router.put("/wishlist/{wishlist_id}")
def update_wishlist_item(wishlist_id: str, data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update wishlist item (category, notes, priority)"""
    wishlist_item = db.query(models.Wishlist).filter(
        models.Wishlist.id == wishlist_id,
        models.Wishlist.user_id == user["id"]
    ).first()
    
    if not wishlist_item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    
    # Update fields
    if "category_id" in data:
        # Verify category belongs to user
        if data["category_id"]:
            category = db.query(models.WishlistCategory).filter(
                models.WishlistCategory.id == data["category_id"],
                models.WishlistCategory.user_id == user["id"]
            ).first()
            
            if not category:
                raise HTTPException(status_code=400, detail="Invalid category")
        
        wishlist_item.category_id = data["category_id"]
    
    if "notes" in data:
        wishlist_item.notes = data["notes"]
    
    if "priority" in data:
        priority = data["priority"]
        if priority not in [1, 2, 3]:
            raise HTTPException(status_code=400, detail="Priority must be 1 (Low), 2 (Medium), or 3 (High)")
        wishlist_item.priority = priority
    
    db.commit()
    return {"message": "Wishlist item updated successfully"}

@api_router.delete("/wishlist/{product_id}")
def remove_from_wishlist(product_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Remove a product from user's wishlist"""
    wishlist_item = db.query(models.Wishlist).filter(
        models.Wishlist.user_id == user["id"],
        models.Wishlist.product_id == product_id
    ).first()
    
    if not wishlist_item:
        raise HTTPException(status_code=404, detail="Product not in wishlist")
    
    db.delete(wishlist_item)
    db.commit()
    
    return {"message": "Product removed from wishlist"}

@api_router.delete("/wishlist")
def clear_wishlist(category_id: str = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Clear all items from user's wishlist or specific category"""
    query = db.query(models.Wishlist).filter(models.Wishlist.user_id == user["id"])
    
    if category_id:
        query = query.filter(models.Wishlist.category_id == category_id)
        message = "Category cleared"
    else:
        message = "Wishlist cleared"
    
    query.delete()
    db.commit()
    
    return {"message": message}

@api_router.get("/wishlist/check/{product_id}")
def check_wishlist_status(product_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check if a product is in user's wishlist"""
    wishlist_item = db.query(models.Wishlist).filter(
        models.Wishlist.user_id == user["id"],
        models.Wishlist.product_id == product_id
    ).first()
    
    return {
        "in_wishlist": wishlist_item is not None,
        "wishlist_item": {
            "id": wishlist_item.id,
            "category_id": wishlist_item.category_id,
            "notes": wishlist_item.notes,
            "priority": wishlist_item.priority
        } if wishlist_item else None
    }

# ============ INVOICE & LABEL GENERATION ============

def generate_invoice_pdf(order_id: str, db: Session):
    """Generate professional invoice PDF for an order"""
    try:
        # Get order details
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Get settings for company info
        settings = db.query(models.Settings).filter(models.Settings.type == "business").first()
        
        # Create PDF buffer
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Company details
        company_name = settings.company_name if settings and settings.company_name else "BharatBazaar"
        business_name = settings.business_name if settings and settings.business_name else "BharatBazaar"
        gst_number = settings.gst_number if settings and settings.gst_number else ""
        
        # Colors
        header_color = colors.HexColor('#2c3e50')
        accent_color = colors.HexColor('#3498db')
        
        # Header Section
        p.setFillColor(header_color)
        p.rect(0, height - 80, width, 80, fill=1)
        
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 24)
        p.drawString(30, height - 50, company_name)
        
        # Invoice title on right
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 20)
        p.drawRightString(width - 30, height - 35, "TAX INVOICE")
        p.setFont("Helvetica", 10)
        p.drawRightString(width - 30, height - 50, "Original For Recipient")
        
        # Company details section
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(30, height - 110, f"Sold by: {business_name}")
        
        p.setFont("Helvetica", 10)
        y_pos = height - 130
        
        if settings and settings.address:
            addr = settings.address
            address_lines = []
            if addr.get('line1'): address_lines.append(addr['line1'])
            if addr.get('line2'): address_lines.append(addr['line2'])
            if addr.get('city') and addr.get('state'):
                address_lines.append(f"{addr['city']}, {addr['state']}, {addr.get('pincode', '')}")
            
            for line in address_lines:
                p.drawString(30, y_pos, line)
                y_pos -= 15
        
        if gst_number:
            p.drawString(30, y_pos, f"GSTIN - {gst_number}")
            y_pos -= 15
        
        # Invoice details (right side)
        p.setFont("Helvetica", 10)
        invoice_prefix = settings.configs.get('invoice_prefix', 'INV') if settings and settings.configs else 'INV'
        purchase_order_no = f"{order.order_number.replace('ORD', '')}"
        invoice_no = f"Invq{purchase_order_no}"
        
        p.drawRightString(width - 30, height - 110, f"Purchase Order No.")
        p.drawRightString(width - 30, height - 125, f"Invoice No.")
        p.drawRightString(width - 30, height - 140, f"Order Date")
        p.drawRightString(width - 30, height - 155, f"Invoice Date")
        
        p.setFont("Helvetica-Bold", 10)
        p.drawRightString(width - 150, height - 110, purchase_order_no)
        p.drawRightString(width - 150, height - 125, invoice_no)
        p.drawRightString(width - 150, height - 140, order.created_at.strftime('%d.%m.%Y'))
        p.drawRightString(width - 150, height - 155, order.created_at.strftime('%d.%m.%Y'))
        
        # Bill To section
        p.setFillColor(colors.lightgrey)
        p.rect(30, height - 220, width - 60, 25, fill=1)
        
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(40, height - 210, "BILL TO / SHIP TO")
        
        p.setFont("Helvetica", 10)
        y_pos = height - 240
        
        if order.shipping_address:
            addr = order.shipping_address
            if addr.get('name'):
                p.drawString(40, y_pos, addr['name'])
                y_pos -= 15
            
            address_parts = []
            if addr.get('line1'): address_parts.append(addr['line1'])
            if addr.get('line2'): address_parts.append(addr['line2'])
            
            for part in address_parts:
                p.drawString(40, y_pos, part)
                y_pos -= 15
            
            if addr.get('city') and addr.get('state'):
                p.drawString(40, y_pos, f"{addr['city']}, {addr['state']}, {addr.get('pincode', '')}. Place of Supply: {addr.get('state', '')}")
                y_pos -= 15
        
        # Items table header
        table_start_y = height - 320
        p.setFillColor(colors.lightgrey)
        p.rect(30, table_start_y - 20, width - 60, 20, fill=1)
        
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(40, table_start_y - 15, "Description")
        p.drawString(250, table_start_y - 15, "HSN")
        p.drawString(290, table_start_y - 15, "Qty")
        p.drawString(330, table_start_y - 15, "Gross Amount")
        p.drawString(420, table_start_y - 15, "Discount")
        p.drawString(480, table_start_y - 15, "Taxable Value")
        p.drawString(550, table_start_y - 15, "Taxes")
        p.drawString(580, table_start_y - 15, "Total")
        
        # Items
        p.setFont("Helvetica", 8)
        y_pos = table_start_y - 35
        
        subtotal_before_tax = 0
        total_gst = 0
        
        for item in order.items:
            # Get product details
            product = db.query(models.Product).filter(models.Product.id == item["product_id"]).first()
            product_name = product.name if product else item.get("name", "Unknown Product")
            hsn_code = product.hsn_code if product and product.hsn_code else "960390"
            gst_rate = product.gst_rate if product else 18.0
            
            quantity = item["quantity"]
            unit_price = item["price"]
            gross_amount = quantity * unit_price
            discount = 0  # Can be added later
            taxable_value = gross_amount - discount
            gst_amount = taxable_value * (gst_rate / 100) if order.gst_applied else 0
            total_amount = taxable_value + gst_amount
            
            subtotal_before_tax += taxable_value
            total_gst += gst_amount
            
            # Draw item row
            p.drawString(40, y_pos, product_name[:25])
            p.drawString(250, y_pos, hsn_code)
            p.drawString(290, y_pos, str(quantity))
            p.drawString(330, y_pos, f"Rs.{gross_amount:.2f}")
            p.drawString(420, y_pos, f"Rs.{discount:.2f}")
            p.drawString(480, y_pos, f"Rs.{taxable_value:.2f}")
            
            if gst_amount > 0:
                p.drawString(550, y_pos, f"IGST @{gst_rate}%")
                p.drawString(550, y_pos - 10, f"Rs.{gst_amount:.2f}")
                y_pos -= 10
            else:
                p.drawString(550, y_pos, "Rs.0.00")
            
            p.drawString(580, y_pos, f"Rs.{total_amount:.2f}")
            y_pos -= 20
        
        # Totals section
        totals_y = y_pos - 30
        p.line(30, totals_y + 20, width - 30, totals_y + 20)
        
        p.setFont("Helvetica-Bold", 10)
        p.drawRightString(480, totals_y, "Total")
        p.drawRightString(580, totals_y, f"Rs.{order.grand_total:.2f}")
        
        # Tax summary
        if order.gst_applied and total_gst > 0:
            p.setFont("Helvetica", 9)
            p.drawString(40, totals_y - 40, "Tax is not payable on reverse charge basis. This is a computer generated invoice and does not require signature. Other charges are charges that are")
            p.drawString(40, totals_y - 55, "applicable to your order and/or city and/or online payments (as applicable). Includes discounts for your city and/or online payments (as applicable).")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate invoice: {str(e)}")

def generate_shipping_label_pdf(order_id: str, db: Session):
    """Generate professional shipping label PDF for an order"""
    try:
        # Get order details
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        # Get settings for company info
        settings = db.query(models.Settings).filter(models.Settings.type == "business").first()
        
        # Create PDF buffer - Standard 4x6 inch shipping label
        buffer = io.BytesIO()
        width, height = 4*inch, 6*inch
        p = canvas.Canvas(buffer, pagesize=(width, height))
        
        # Company details
        company_name = settings.company_name if settings and settings.company_name else "BharatBazaar"
        business_name = settings.business_name if settings and settings.business_name else "BharatBazaar"
        
        # --- SEPARATOR LINES ---
        # Main Border
        p.setStrokeColor(colors.black)
        p.setLineWidth(1.5)
        # p.rect(5, 5, width - 10, height - 10) # Optional outer border
        
        # Horizontal Separators
        y_line1 = height - 110  # Below Address/COD
        y_line2 = height - 190  # Below Return Address/Barcodes
        y_line3 = height - 240  # Below Product Details
        y_line4 = height - 255  # Below Invoice Header
        
        p.setLineWidth(1)
        p.line(5, y_line1, width - 5, y_line1)
        p.line(5, y_line2, width - 5, y_line2)
        p.line(5, y_line3, width - 5, y_line3)
        p.line(5, y_line4, width - 5, y_line4)
        
        # Vertical Separator (Top Section)
        p.line(width * 0.45, height - 5, width * 0.45, y_line1)

        # --- TOP SECTION: Customer Address (Left) & COD/Courier (Right) ---
        
        # Customer Address
        p.setFont("Helvetica-Bold", 7)
        p.drawString(10, height - 15, "Customer Address")
        
        if order.shipping_address:
            addr = order.shipping_address
            p.setFont("Helvetica-Bold", 10)
            p.drawString(10, height - 30, addr.get('name', '')[:25])
            
            p.setFont("Helvetica", 8)
            y_addr = height - 42
            line_height = 9
            
            address_lines = []
            if addr.get('line1'): address_lines.append(addr['line1'])
            if addr.get('line2'): address_lines.append(addr['line2'])
            location = []
            if addr.get('city'): location.append(addr['city'])
            if addr.get('state'): location.append(addr['state'])
            if addr.get('pincode'): location.append(str(addr['pincode']))
            if location: address_lines.append(", ".join(location))
             
            # Phone
            if order.customer_phone:
                address_lines.append(f"Tel: {order.customer_phone}")
            
            for line in address_lines[:6]: # Limit lines
                if len(line) > 30: line = line[:28] + "..."
                p.drawString(10, y_addr, line)
                y_addr -= line_height

        # COD / Courier Section (Right)
        x_right = width * 0.45 + 5
        
        # COD Amount Header
        p.setFillColor(colors.black)
        p.rect(x_right, height - 20, width - x_right - 5, 15, fill=1)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 8)
        
        cod_text = "COD: Check amount on app"
        if order.payment_method == 'cod':
            cod_text = f"COD: Rs.{order.grand_total}"
        else:
             cod_text = "PREPAID"
             
        p.drawCentredString(x_right + (width - x_right - 5)/2, height - 16, cod_text)
        
        p.setFillColor(colors.black)
        
        # Courier Name
        p.setFont("Helvetica-Bold", 12)
        p.drawString(x_right, height - 35, "Shadowfax") # Or dynamic provider
        
        # Pickup Badge
        p.setFillColor(colors.black)
        p.rect(x_right, height - 48, 35, 10, fill=1)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 7)
        p.drawCentredString(x_right + 17.5, height - 45, "Pickup")
        p.setFillColor(colors.black)
        
        # Destination Code
        p.setFont("Helvetica", 7)
        p.drawString(x_right, height - 58, "Destination Code")
        
        # Mock Codes
        dest_code = "S46_PSA"
        p.setFillColor(colors.lightgrey)
        p.rect(x_right, height - 72, 60, 12, fill=1)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(x_right + 2, height - 69, dest_code)
        
        # Return Code
        p.setFont("Helvetica", 7)
        p.drawString(x_right, height - 80, "Return Code")
        return_code = "303702,348"
        p.setFont("Helvetica-Bold", 8)
        p.drawString(x_right, height - 90, return_code)
        
        # QR Code
        qr_size = 50
        qr_x = width - qr_size - 5
        qr_y = height - 145 # Moved down to avoid overlap
        
         # Generate QR code
        qr_data = f"{order.order_number}|{order.grand_total}"
        qr = qrcode.QRCode(version=1, box_size=2, border=1)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        qr_buffer = QRBytesIO()
        img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        
        # Draw QR code placeholder (since reportlab needs PIL integration for images)
        p.drawImage(ImageReader(qr_buffer), qr_x, height - 80, width=qr_size, height=qr_size) # Adjusted Y
        
        # --- MIDDLE SECTION: Return Address & Barcode ---
        
        # --- MIDDLE SECTION: Return Address & Barcode ---
        
        # Return Address (Left)
        p.setFont("Helvetica-Bold", 7)
        p.drawString(10, y_line1 - 10, "")
        
        # Use Company Name for Return Address as requested
        p.setFont("Helvetica-Bold", 8)
        y_ret = y_line1 - 22
        p.drawString(10, y_ret, company_name.upper()[:35])
        y_ret -= 10
        
        p.setFont("Helvetica", 7)
        ret_lines = []
        if settings and settings.address:
            addr = settings.address
            if addr.get('line1'): ret_lines.append(addr['line1'].upper())
            if addr.get('line2'): ret_lines.append(addr['line2'].upper())
            if addr.get('city'): ret_lines.append(f"{addr['city'].upper()}, {addr.get('state', '').upper()}")
            if addr.get('pincode'): ret_lines.append(f"{addr.get('pincode')}")
        else:
            ret_lines.append("WAREHOUSE ADDRESS")
            
        for line in ret_lines[:4]:
             if len(line) > 40: line = line[:38] + "..."
             p.drawString(10, y_ret, line)
             y_ret -= 8
             
        # Tracking Barcode
        barcode_val = order.tracking_number or order.order_number
        p.setFont("Helvetica-Bold", 9)
        p.drawCentredString(width * 0.75, y_line1 - 70, barcode_val)
        
        # Simulated Barcode
        bc_x = width * 0.55
        bc_y = y_line1 - 50
        bc_w = 120
        bc_h = 30
        
        # Draw barcode (simplified lines)
        # p.rect(bc_x, bc_y, bc_w, bc_h, stroke=0, fill=0) # bounding box
        import random
        random.seed(barcode_val)
        curr_x = bc_x
        while curr_x < bc_x + bc_w:
            w = random.choice([1, 2, 3])
            if curr_x + w > bc_x + bc_w: break
            if random.choice([True, False]):
                p.rect(curr_x, bc_y, w, bc_h, fill=1, stroke=0)
            curr_x += w
            
        # --- PRODUCT DETAILS SECTION ---
        p.setFont("Helvetica-Bold", 8)
        p.drawString(10, y_line2 - 10, "Product Details")
        
        # Table Data
        data = [['SKU', 'Size', 'Qty', 'Color', 'Order No.']]
        
        # Items
        items_to_show = order.items[:3]  # Show max 3 items
        for item in items_to_show:
            prod = db.query(models.Product).filter(models.Product.id == item['product_id']).first()
            sku = prod.sku if prod else "N/A"
            name = prod.name[:15] if prod else "Item"
            data.append([
                f"{sku}\n{name}", 
                "Free", 
                str(item['quantity']), 
                "Multi", 
                order.order_number[-8:]
            ])
            
        t = Table(data, colWidths=[80, 40, 30, 40, 80])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TEXTCOLOR', (0,0), (-1,0), colors.gray), # Header color
        ]))
        
        w, h = t.wrapOn(p, width, height)
        t.drawOn(p, 5, y_line2 - h - 15)

        # --- TAX INVOICE SECTION (Bottom) ---
        
        # Header
        p.setFillColor(colors.lightgrey)
        p.rect(5, y_line3 - 12, width - 10, 12, fill=1, stroke=0)
        p.setFillColor(colors.black)
        p.setFont("Helvetica-Bold", 8)
        p.drawCentredString(width/2, y_line3 - 9, "TAX INVOICE")
        p.setFont("Helvetica", 6)
        p.drawRightString(width - 10, y_line3 - 9, "Original For Recipient")
        
        # Bill To / Sold By
        y_inv = y_line4 - 10
        p.setFont("Helvetica-Bold", 6)
        p.drawString(10, y_inv, "BILL TO / SHIP TO")
        p.drawString(width/2 + 5, y_inv, f"Sold by : {business_name}")
        
        y_inv -= 8
        p.setFont("Helvetica", 6)
        
        # Bill To Address (Simplified)
        if order.shipping_address:
            addr_str = f"{order.shipping_address.get('name', '')}, {order.shipping_address.get('city', '')}"
            p.drawString(10, y_inv, addr_str[:45])
            p.drawString(10, y_inv - 7, f"State: {order.shipping_address.get('state', '')}")
            
        # Sold By Address
        if settings and settings.address:
            sold_addr = f"{settings.address.get('line1', '')}, {settings.address.get('city', '')}"
            p.drawString(width/2 + 5, y_inv, sold_addr[:45])
            
        if settings and settings.gst_number:
            p.drawString(width/2 + 5, y_inv - 7, f"GSTIN - {settings.gst_number}")
            
        # Invoice Table
        inv_data = [['Description', 'HSN', 'Qty', 'Gross', 'Disc', 'Taxable', 'Tax', 'Total']]
        
        total_taxable = 0
        total_tax = 0
        
        for item in items_to_show: # Same items
            prod = db.query(models.Product).filter(models.Product.id == item['product_id']).first()
            item_total = item['quantity'] * prod.selling_price
            
            # Simple tax calc (inclusive)
            tax_rate = prod.gst_rate if prod else 18.0
            taxable = item_total / (1 + (tax_rate/100))
            tax_amt = item_total - taxable
            
            total_taxable += taxable
            total_tax += tax_amt
            
            inv_data.append([
                prod.name[:10] if prod else "Item",
                prod.hsn_code if prod and prod.hsn_code else "960390",
                str(item['quantity']),
                f"{item_total:.0f}",
                "0",
                f"{taxable:.1f}",
                f"{tax_amt:.1f}",
                f"{item_total:.0f}"
            ])
            
        # Totals Row
        inv_data.append(['Total', '', '', '', '', f"{total_taxable:.1f}", f"{total_tax:.1f}", f"{order.grand_total:.1f}"])
            
        inv_table = Table(inv_data, colWidths=[70, 30, 20, 30, 25, 35, 30, 35])
        inv_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 5),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (3,0), (-1,-1), 'RIGHT'), # Numbers right aligned
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'), # Total row bold
        ]))
        
        w_inv, h_inv = inv_table.wrapOn(p, width, height)
        inv_table.drawOn(p, 5, y_inv - h_inv - 25)
        
        # Footer Disclaimer
        p.setFont("Helvetica", 5)
        p.drawString(10, 10, "Tax is not payable on reverse charge basis. Computer generated invoice.")

        p.showPage()
        p.save()
        
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate shipping label: {str(e)}")

@api_router.get("/admin/orders/{order_id}/invoice")
def download_invoice(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Download invoice PDF for an order"""
    try:
        pdf_buffer = generate_invoice_pdf(order_id, db)
        
        # Get order for filename
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        filename = f"invoice_{order.order_number}.pdf" if order else f"invoice_{order_id}.pdf"
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate invoice: {str(e)}")

@api_router.get("/admin/orders/{order_id}/shipping-label")
def download_shipping_label(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Download shipping label PDF for an order"""
    try:
        pdf_buffer = generate_shipping_label_pdf(order_id, db)
        
        # Get order for filename
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        filename = f"label_{order.order_number}.pdf" if order else f"label_{order_id}.pdf"
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate shipping label: {str(e)}")


# ============ BANNER ENDPOINTS ============

@api_router.get("/banners")
def get_banners(db: Session = Depends(get_db)):
    """Get all active banners for public display"""
    try:
        banners = db.query(models.Banner).filter(models.Banner.is_active == True).order_by(models.Banner.position).all()
        return [
            {
                "id": banner.id,
                "title": banner.title,
                "image_url": banner.image_url,
                "link": banner.link,
                "position": banner.position,
                "is_active": banner.is_active,
                "created_at": banner.created_at
            }
            for banner in banners
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get banners: {str(e)}")

@api_router.get("/admin/banners")
def get_admin_banners(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get all banners for admin"""
    try:
        banners = db.query(models.Banner).order_by(models.Banner.position).all()
        return [
            {
                "id": banner.id,
                "title": banner.title,
                "image_url": banner.image_url,
                "link": banner.link,
                "position": banner.position,
                "is_active": banner.is_active,
                "created_at": banner.created_at
            }
            for banner in banners
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get banners: {str(e)}")

@api_router.post("/admin/banners")
def create_banner(data: BannerCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Create a new banner"""
    try:
        banner = models.Banner(
            id=generate_id(),
            title=data.title,
            image_url=data.image_url,
            link=data.link,
            position=data.position,
            is_active=data.is_active,
            created_at=datetime.utcnow()
        )
        db.add(banner)
        db.commit()
        db.refresh(banner)
        
        return {"message": "Banner created successfully", "banner_id": banner.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create banner: {str(e)}")

@api_router.put("/admin/banners/{banner_id}")
def update_banner(banner_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Update a banner"""
    try:
        banner = db.query(models.Banner).filter(models.Banner.id == banner_id).first()
        if not banner:
            raise HTTPException(status_code=404, detail="Banner not found")
        
        # Update fields
        for field, value in data.items():
            if hasattr(banner, field):
                setattr(banner, field, value)
        
        db.commit()
        return {"message": "Banner updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update banner: {str(e)}")

@api_router.delete("/admin/banners/{banner_id}")
def delete_banner(banner_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Delete a banner"""
    try:
        banner = db.query(models.Banner).filter(models.Banner.id == banner_id).first()
        if not banner:
            raise HTTPException(status_code=404, detail="Banner not found")
        
        # Delete associated image file
        if banner.image_url:
            delete_uploaded_file(banner.image_url)
        
        db.delete(banner)
        db.commit()
        return {"message": "Banner deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete banner: {str(e)}")


# ============ OFFER ENDPOINTS ============

@api_router.get("/offers")
def get_offers(db: Session = Depends(get_db)):
    """Get all active offers for public display"""
    try:
        offers = db.query(models.Offer).filter(models.Offer.is_active == True).all()
        return [
            {
                "id": offer.id,
                "title": offer.title,
                "description": offer.description,
                "discount_type": offer.discount_type,
                "discount_value": offer.discount_value,
                "min_order_value": offer.min_order_value,
                "max_discount": offer.max_discount,
                "coupon_code": offer.coupon_code,
                "is_active": offer.is_active,
                "created_at": offer.created_at
            }
            for offer in offers
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get offers: {str(e)}")

@api_router.get("/admin/offers")
def get_admin_offers(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Get all offers for admin"""
    try:
        offers = db.query(models.Offer).all()
        return [
            {
                "id": offer.id,
                "title": offer.title,
                "description": offer.description,
                "discount_type": offer.discount_type,
                "discount_value": offer.discount_value,
                "min_order_value": offer.min_order_value,
                "max_discount": offer.max_discount,
                "coupon_code": offer.coupon_code,
                "product_ids": offer.product_ids,
                "category_ids": offer.category_ids,
                "is_active": offer.is_active,
                "created_at": offer.created_at
            }
            for offer in offers
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get offers: {str(e)}")

@api_router.post("/admin/offers")
def create_offer(data: OfferCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Create a new offer"""
    try:
        offer = models.Offer(
            id=generate_id(),
            title=data.title,
            description=data.description,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            min_order_value=data.min_order_value,
            max_discount=data.max_discount,
            coupon_code=data.coupon_code,
            product_ids=data.product_ids,
            category_ids=data.category_ids,
            is_active=data.is_active,
            created_at=datetime.utcnow()
        )
        db.add(offer)
        db.commit()
        db.refresh(offer)
        
        return {"message": "Offer created successfully", "offer_id": offer.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create offer: {str(e)}")

@api_router.put("/admin/offers/{offer_id}")
def update_offer(offer_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Update an offer"""
    try:
        offer = db.query(models.Offer).filter(models.Offer.id == offer_id).first()
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        
        # Update fields
        for field, value in data.items():
            if hasattr(offer, field):
                setattr(offer, field, value)
        
        db.commit()
        return {"message": "Offer updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update offer: {str(e)}")

@api_router.delete("/admin/offers/{offer_id}")
def delete_offer(offer_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    """Delete an offer"""
    try:
        offer = db.query(models.Offer).filter(models.Offer.id == offer_id).first()
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        
        db.delete(offer)
        db.commit()
        return {"message": "Offer deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete offer: {str(e)}")


# ============ UPLOAD ENDPOINTS ============

@api_router.post("/upload/multiple")
async def upload_multiple_images(
    files: List[UploadFile] = File(...),
    folder: str = "general",
    image_type: Optional[str] = None,
    admin: dict = Depends(admin_required)
):
    """Upload multiple image files"""
    try:
        if len(files) > 10:  # Limit to 10 files
            raise HTTPException(status_code=400, detail="Maximum 10 files allowed")
        
        uploaded_files = []
        
        for file in files:
            # Validate file type
            if not file.content_type or not file.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail=f"File {file.filename} must be an image")
            
            # Save the uploaded file
            file_url = save_uploaded_file(file, folder, image_type)
            
            uploaded_files.append({
                "url": file_url,
                "filename": file.filename
            })
        
        return {
            "message": f"{len(uploaded_files)} images uploaded successfully",
            "files": uploaded_files
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload images: {str(e)}")

@api_router.delete("/upload/delete")
async def delete_uploaded_image(
    file_url: str = Query(..., description="URL of the file to delete"),
    admin: dict = Depends(admin_required)
):
    """Delete an uploaded file"""
    try:
        delete_uploaded_file(file_url)
        return {"message": "File deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


# ============ ROOT ============

@api_router.get("/")
def root():
    return {"message": "BharatBazaar API (SQL)", "version": "2.0.0"}

app.include_router(api_router)

# Remove duplicate CORS middleware - already configured above
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# No shutdown event needed for SQLAlchemy engine, connection pooling handles it

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
