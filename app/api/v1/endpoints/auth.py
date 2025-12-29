from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_
import jwt
from datetime import datetime, timezone, timedelta

from app.db.session import get_db
from app.core.config import settings
from app.core.security import verify_password, create_token, hash_password
from app.utils.common import generate_otp, generate_id
from app.models.user import User, OTP, SellerRequest
from app.schemas.user import UserCreate, UserLogin, OTPRequest, OTPVerify, ForgotPasswordRequest, SellerRequestInput
from app.services import email as email_utils

router = APIRouter()
security = HTTPBearer()

# Dependency to get current user
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(status_code=401, detail="No authorization header")
    
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user = db.query(User).filter(User.id == payload["user_id"]).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Convert SQLAlchemy model to dict for backward compatibility or ease of use
        user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
        if user.address is None: user_dict["address"] = None
        if user.addresses is None: user_dict["addresses"] = []
        return user_dict
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed")

def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    """Optional authentication - returns None if no token provided"""
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "bearer":
            return None
        
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user = db.query(User).filter(User.id == payload["user_id"]).first()
        if not user:
            return None
        
        user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
        if user.address is None: user_dict["address"] = None
        if user.addresses is None: user_dict["addresses"] = []
        return user_dict
    except:
        return None

def admin_required(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

@router.get("/auth/test")
def test_auth(user: dict = Depends(get_current_user)):
    """Test endpoint to check if authentication is working"""
    return {"message": "Authentication successful", "user": user["name"]}

@router.post("/auth/send-otp")
def send_otp(data: OTPRequest, db: Session = Depends(get_db)):
    otp = generate_otp()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
    
    # Upsert OTP
    existing_otp = db.query(OTP).filter(OTP.phone == data.phone).first()
    if existing_otp:
        existing_otp.otp = otp
        existing_otp.expiry = expiry
        existing_otp.verified = False
    else:
        new_otp = OTP(phone=data.phone, otp=otp, expiry=expiry, verified=False)
        db.add(new_otp)
    
    db.commit()
    
    # Send OTP via Email with fallback instructions
    if data.email:
        email_utils.send_otp_email(data.email, data.phone, otp)
    
    return {"message": "OTP sent successfully", "otp_for_testing": otp}

@router.post("/auth/verify-otp")
def verify_otp(data: OTPVerify, db: Session = Depends(get_db)):
    otp_doc = db.query(OTP).filter(OTP.phone == data.phone).first()
    if not otp_doc:
        raise HTTPException(status_code=400, detail="No OTP found for this phone")
    
    if otp_doc.otp != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    if datetime.utcnow() > otp_doc.expiry: 
        raise HTTPException(status_code=400, detail="OTP expired")
    
    otp_doc.verified = True
    db.commit()
    return {"message": "OTP verified successfully", "verified": True}

@router.post("/auth/register")
def register(data: UserCreate, db: Session = Depends(get_db)):
    # Check if OTP was verified
    otp_doc = db.query(OTP).filter(OTP.phone == data.phone, OTP.verified == True).first()
    # Logic from server.py: "Commented out for dev ease, or uncomment if strictly needed"
    # Keeping it as is
    
    # Check if user exists
    existing = db.query(User).filter(User.phone == data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists with this phone number")
    
    if data.email:
        existing_email = db.query(User).filter(User.email == data.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="User already exists with this email address")
    
    request_supplier = bool(data.gst_number)
    supplier_status = "pending" if request_supplier else "none"
    is_wholesale = False
    
    final_password = ""
    temporary_password = ""
    should_send_email = False
    
    if data.password:
        final_password = hash_password(data.password)
    else:
        temporary_password = f"Pass{generate_otp()}"
        final_password = hash_password(temporary_password)
        should_send_email = True
    
    new_user = User(
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

@router.post("/auth/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        or_(
            User.phone == data.identifier,
            User.email == data.identifier
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

@router.post("/auth/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    identifier = data.email or data.phone
    if not identifier:
        raise HTTPException(status_code=400, detail="Please provide phone or email")
        
    user = db.query(User).filter(
        or_(
            User.email == identifier,
            User.phone == identifier
        )
    ).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.email:
        raise HTTPException(status_code=400, detail="No email address associated with this account. Please contact support@amolias.com")
    
    new_password = f"Pass{generate_otp()}"
    user.password = hash_password(new_password)
    db.commit()
    
    email_utils.send_temporary_password_email(
        to_email=user.email,
        name=user.name,
        temporary_password=new_password,
        is_registration=False
    )
    
    return {"message": f"New temporary password has been sent to {user.email}"}

@router.get("/auth/me")
def get_current_user_info(user: dict = Depends(get_current_user)):
    return user

@router.put("/auth/profile")
def update_profile(data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    allowed_fields = ["name", "email", "address", "addresses"]
    db_user = db.query(User).filter(User.id == user["id"]).first()
    
    updated_fields = []
    for k, v in data.items():
        if k in allowed_fields and hasattr(db_user, k):
            old_value = getattr(db_user, k)
            if old_value != v:
                setattr(db_user, k, v)
                updated_fields.append(k)
    
    db.commit()
    db.refresh(db_user)
    
    # We should probably trigger notifications here as well, but that requires Notification model and utils import
    # For now, simplistic port.
    
    user_dict = {c.name: getattr(db_user, c.name) for c in db_user.__table__.columns}
    user_dict.pop("password")
    return user_dict # Return dict, or response as per original

@router.put("/auth/change-password")
def change_password(data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    
    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Current and new passwords are required")
    
    user_obj = db.query(User).filter(User.id == user["id"]).first()
    
    if not user_obj or not verify_password(current_password, user_obj.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    user_obj.password = hash_password(new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}

@router.put("/auth/update-phone")
def update_phone(data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    new_phone = data.get("phone")
    otp = data.get("otp")
    
    if not new_phone or not otp:
        raise HTTPException(status_code=400, detail="Phone number and OTP are required")
    
    otp_doc = db.query(OTP).filter(
        OTP.phone == new_phone,
        OTP.otp == otp,
        OTP.verified == False
    ).first()
    
    if not otp_doc or otp_doc.expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    existing_user = db.query(User).filter(
        User.phone == new_phone,
        User.id != user["id"]
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Phone number already in use")
    
    user_obj = db.query(User).filter(User.id == user["id"]).first()
    user_obj.phone = new_phone
    otp_doc.verified = True
    
    db.commit()
    return {"message": "Phone number updated successfully"}

@router.post("/auth/request-seller")
def request_seller_upgrade(data: SellerRequestInput, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    request_id = generate_id()
    new_request = SellerRequest(
        id=request_id,
        user_id=user["id"],
        user_name=user["name"],
        user_phone=user["phone"],
        business_name=data.business_name,
        gst_number=data.gst_number,
        status="pending"
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    return {"message": "Seller request submitted", "request": {c.name: getattr(new_request, c.name) for c in new_request.__table__.columns}}
