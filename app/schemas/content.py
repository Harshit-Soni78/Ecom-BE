from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class BannerCreate(BaseModel):
    title: str
    image_url: str
    link: Optional[str] = None
    position: int = 0
    is_active: bool = True

class OfferCreate(BaseModel):
    title: str
    description: Optional[str] = None
    discount_type: str = "percentage"
    discount_value: float
    min_order_value: float = 0
    max_discount: Optional[float] = None
    coupon_code: Optional[str] = None
    product_ids: Optional[List[str]] = []
    category_ids: Optional[List[str]] = []
    is_active: bool = True
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class PageUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_active: Optional[bool] = None
