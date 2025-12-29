from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import admin_required
from app.models.user import User, SellerRequest
from app.schemas.user import AdminCreate
from app.utils.common import generate_id, generate_otp
from app.core.security import hash_password
from app.services import email as email_utils

router = APIRouter()

@router.get("/admin/users")
def get_all_users(
    page: int = 1, 
    limit: int = 50, 
    search: str = None,
    role: str = None,
    admin: dict = Depends(admin_required), 
    db: Session = Depends(get_db)
):
    query = db.query(User)
    
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f"%{search}%"),
                User.phone.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    
    if role:
        query = query.filter(User.role == role)
    
    total = query.count()
    offset = (page - 1) * limit
    users = query.offset(offset).limit(limit).all()
    
    users_data = []
    for user in users:
        user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
        user_dict.pop("password", None)
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

@router.put("/admin/users/{user_id}")
def update_user(user_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    allowed_fields = ["name", "email", "role", "is_seller", "is_wholesale", "supplier_status"]
    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])
    
    user.updated_at = datetime.utcnow()
    db.commit()
    
    user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    user_dict.pop("password", None)
    
    return {"message": "User updated successfully", "user": user_dict}

@router.delete("/admin/users/{user_id}")
def delete_user(user_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin user")
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}

@router.put("/admin/users/{user_id}/role")
def update_user_role(user_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_role = data.get("role")
    if not new_role or new_role not in ["customer", "seller", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    user.role = new_role
    
    if new_role == "seller":
        user.is_seller = True
        user.is_wholesale = True
    elif new_role == "admin":
        user.is_seller = True
        user.is_wholesale = True
    else:  # customer
        user.is_seller = False
        user.is_wholesale = False
    
    db.commit()
    return {"message": "User role updated", "user": {"id": user.id, "name": user.name, "role": user.role}}

@router.get("/admin/seller-requests")
def get_seller_requests(status: Optional[str] = None, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    query = db.query(SellerRequest)
    if status:
        query = query.filter(SellerRequest.status == status)
    
    requests = query.order_by(SellerRequest.created_at.desc()).limit(100).all()
    return requests

@router.put("/admin/seller-requests/{request_id}")
def handle_seller_request(request_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    request = db.query(SellerRequest).filter(SellerRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    status = data.get("status", "approved")
    request.status = status
    
    if status == "approved":
        user = db.query(User).filter(User.id == request.user_id).first()
        if user:
            user.is_seller = True
            user.is_wholesale = True
            user.gst_number = request.gst_number or user.gst_number
    
    db.commit()
    return {"message": f"Request {status}"}

@router.get("/admin/team")
def get_team_members(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    user_list = []
    for user in users:
        user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
        user_dict.pop("password", None)
        user_list.append(user_dict)
    return {"users": user_list}

@router.post("/admin/team")
def create_admin_user(data: AdminCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        or_(
            User.phone == data.phone,
            User.email == data.email
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User with this phone or email already exists")
    
    temp_password = f"Pass{generate_otp()}"
    new_admin = User(
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

@router.put("/admin/team/{user_id}")
def update_team_member_role(user_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    # Reusing logic
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == admin["id"] and data.get("role") != "admin":
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    
    if "role" in data:
        user.role = data["role"]
    if "is_wholesale" in data:
        user.is_wholesale = data["is_wholesale"]
    if "is_seller" in data:
        user.is_seller = data["is_seller"]
    
    db.commit()
    db.refresh(user)
    
    user_dict = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    user_dict.pop("password")
    return {"message": "User role updated successfully", "user": user_dict}

@router.delete("/admin/team/{user_id}")
def remove_admin_access(user_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot remove your own admin access")
    
    user.role = "customer"
    db.commit()
    return {"message": "Admin access removed successfully"}
