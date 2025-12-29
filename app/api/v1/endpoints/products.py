from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc
from typing import Optional, List
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import admin_required
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.utils.common import generate_id

router = APIRouter()

@router.get("/products")
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
    query = db.query(Product).filter(Product.is_active == True)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Product.name.like(search_pattern),
                Product.description.like(search_pattern),
                Product.sku.like(search_pattern)
            )
        )
    if min_price:
        query = query.filter(Product.selling_price >= min_price)
    if max_price:
        query = query.filter(Product.selling_price <= max_price)
        
    sort_attr = getattr(Product, sort_by, Product.created_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_attr))
    else:
        query = query.order_by(asc(sort_attr))
        
    total = query.count()
    products = query.offset((page - 1) * limit).limit(limit).all()
    
    return {"products": products, "total": total, "page": page, "pages": (total + limit - 1) // limit}

@router.get("/products/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.post("/admin/products")
def create_product(data: ProductCreate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    existing = db.query(Product).filter(Product.sku == data.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="SKU already exists")
    
    new_product = Product(
        id=generate_id(),
        **data.model_dump(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return new_product

@router.put("/admin/products/{product_id}")
def update_product(product_id: str, data: ProductUpdate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        update_data = data.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(product, k, v)
        product.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(product)
    return product

@router.delete("/admin/products/{product_id}")
def delete_product(product_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    db.query(Product).filter(Product.id == product_id).delete()
    db.commit()
    return {"message": "Product deleted"}

@router.post("/admin/products/bulk-upload")
def bulk_upload_products(products: List[ProductCreate], admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    created = 0
    updated = 0
    errors = []
    
    for product_data in products:
        try:
            existing = db.query(Product).filter(Product.sku == product_data.sku).first()
            if existing:
                for k, v in product_data.model_dump().items():
                    setattr(existing, k, v)
                existing.updated_at = datetime.utcnow()
                updated += 1
            else:
                new_product = Product(
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
