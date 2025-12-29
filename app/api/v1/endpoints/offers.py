from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import admin_required
from app.models.content import Offer
from app.schemas.content import OfferCreate
from app.utils.common import generate_id

router = APIRouter()

@router.get("/offers")
def get_offers(db: Session = Depends(get_db)):
    offers = db.query(Offer).filter(Offer.is_active == True).all()
    return offers

@router.get("/admin/offers")
def get_admin_offers(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    offers = db.query(Offer).all()
    return offers

@router.post("/admin/offers")
def create_offer(data: OfferCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    offer = Offer(
        id=generate_id(),
        **data.model_dump(),
        created_at=datetime.utcnow()
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return {"message": "Offer created successfully", "offer_id": offer.id}

@router.put("/admin/offers/{offer_id}")
def update_offer(offer_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    for k, v in data.items():
        if hasattr(offer, k):
            setattr(offer, k, v)
    
    db.commit()
    return {"message": "Offer updated successfully"}

@router.delete("/admin/offers/{offer_id}")
def delete_offer(offer_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    
    db.delete(offer)
    db.commit()
    return {"message": "Offer deleted successfully"}
