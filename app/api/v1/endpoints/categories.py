from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import admin_required
from app.models.product import Category
from app.schemas.product import CategoryCreate
from app.utils.common import generate_id

router = APIRouter()

@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).filter(Category.is_active == True).all()
    return categories

@router.get("/categories/{category_id}")
def get_category(category_id: str, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category

@router.post("/admin/categories")
def create_category(data: CategoryCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    new_cat = Category(
        id=generate_id(),
        **data.model_dump(),
        created_at=datetime.utcnow()
    )
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat

@router.put("/admin/categories/{category_id}")
def update_category(category_id: str, data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if cat:
        for k, v in data.items():
            if hasattr(cat, k):
                setattr(cat, k, v)
        db.commit()
    return {"message": "Category updated"}

@router.delete("/admin/categories/{category_id}")
def delete_category(category_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    db.query(Category).filter(Category.id == category_id).delete()
    db.commit()
    return {"message": "Category deleted"}
