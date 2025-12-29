from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class CartItem(BaseModel):
    product_id: str
    quantity: int

class OrderCreate(BaseModel):
    items: List[CartItem]
    shipping_address: Dict[str, str]
    payment_method: str = "cod"
    is_offline: bool = False
    customer_phone: Optional[str] = None
    apply_gst: bool = True
    discount_amount: float = 0
    discount_percentage: float = 0

class OrderStatusUpdate(BaseModel):
    status: str
    tracking_number: Optional[str] = None
    courier_provider: Optional[str] = None
    notes: Optional[str] = None

class ReturnRequest(BaseModel):
    order_id: str
    items: List[Dict[str, Any]]
    reason: str
    refund_method: str = "original"

class OrderCancellationRequest(BaseModel):
    order_id: str
    reason: str
    cancellation_type: str = "customer"  # customer, admin, system

class ReturnRequestCreate(BaseModel):
    order_id: str
    items: List[Dict[str, Any]]
    reason: str
    return_type: str = "defective"  # defective, wrong_item, not_satisfied, damaged
    refund_method: str = "original"
    images: Optional[List[str]] = []  # Evidence images
    videos: Optional[List[str]] = []  # Evidence videos
    description: Optional[str] = None

class ReturnRequestUpdate(BaseModel):
    status: str
    admin_notes: Optional[str] = None
    refund_amount: Optional[float] = None
    return_awb: Optional[str] = None
    courier_provider: Optional[str] = None
