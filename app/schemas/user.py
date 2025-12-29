from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

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

class ContactMessage(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    subject: str
    message: str
