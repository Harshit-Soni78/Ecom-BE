from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import admin_required
from app.models.content import Page
from app.schemas.content import PageUpdate

router = APIRouter()

@router.get("/pages/{slug}")
def get_page(slug: str, db: Session = Depends(get_db)):
    page = db.query(Page).filter(Page.slug == slug).first()
    if not page:
        return {
            "slug": slug,
            "title": slug.replace("-", " ").title(),
            "content": f"Content for {slug} coming soon."
        }
    return page

@router.put("/admin/pages/{slug}")
def update_page(slug: str, data: PageUpdate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    page = db.query(Page).filter(Page.slug == slug).first()
    if not page:
        page = Page(slug=slug)
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
