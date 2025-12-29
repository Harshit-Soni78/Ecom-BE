from pydantic import BaseModel
from typing import List, Optional, Dict, Any

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

class WishlistItemAdd(BaseModel):
    category_id: Optional[str] = None
    notes: Optional[str] = None
    priority: int = 1
