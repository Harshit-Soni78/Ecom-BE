from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import admin_required
from app.models.product import Product

router = APIRouter()

@router.get("/admin/inventory")
def get_inventory(low_stock_only: bool = False, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    query = db.query(Product)
    if low_stock_only:
        query = query.filter(Product.stock_qty <= Product.low_stock_threshold)
        
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
