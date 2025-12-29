from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import admin_required
from app.models.content import Banner
from app.schemas.content import BannerCreate
from app.utils.common import generate_id
from app.utils.image import delete_uploaded_file

router = APIRouter()

@router.get("/banners")
def get_banners(db: Session = Depends(get_db)):
    banners = db.query(Banner).filter(Banner.is_active == True).order_by(Banner.position).all()
    return banners

@router.get("/admin/banners")
def get_admin_banners(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    banners = db.query(Banner).order_by(Banner.position).all()
    return banners

@router.post("/admin/banners")
def create_banner(data: BannerCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    new_banner = Banner(
        id=generate_id(),
        **data.model_dump(),
        created_at=datetime.utcnow()
    )
    db.add(new_banner)
    db.commit()
    db.refresh(new_banner)
    return new_banner

@router.put("/admin/banners/{banner_id}")
def update_banner(banner_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if banner:
        for k, v in data.items():
            if hasattr(banner, k):
                setattr(banner, k, v)
        db.commit()
    return {"message": "Banner updated"}

@router.delete("/admin/banners/{banner_id}")
def delete_banner(banner_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
    
    if banner.image_url:
        delete_uploaded_file(banner.image_url)
        
    db.delete(banner)
    db.commit()
    return {"message": "Banner deleted"}
