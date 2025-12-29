from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user, admin_required
from app.models.order import Order, ReturnRequest
from app.models.user import Notification
from app.models.product import Product
from app.schemas.order import ReturnRequestCreate, ReturnRequestUpdate
from app.utils.common import generate_id
from app.utils.image import save_uploaded_file

router = APIRouter()

def create_notification(db: Session, user_id: str = None, type: str = "", title: str = "", message: str = "", data: dict = None, for_admin: bool = False):
    notification = Notification(
        id=generate_id(),
        type=type,
        title=title,
        message=message,
        user_id=user_id,
        data=data or {},
        for_admin=for_admin,
        read=False
    )
    db.add(notification)
    return notification

def create_admin_notification(db: Session, type: str, title: str, message: str, data: dict = None):
    return create_notification(
        db=db,
        user_id=None,
        type=type,
        title=title,
        message=message,
        data=data,
        for_admin=True
    )

@router.post("/orders/{order_id}/return")
def create_return_request(order_id: str, data: ReturnRequestCreate, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if user["role"] != "admin" and order.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to return this order")
    
    if order.status not in ["delivered"]:
        raise HTTPException(status_code=400, detail=f"Cannot return order with status: {order.status}. Order must be delivered to initiate return.")
    
    if order.updated_at:
        days_since_delivery = (datetime.utcnow() - order.updated_at).days
        if days_since_delivery > 5:
            raise HTTPException(status_code=400, detail="Return window expired. Returns are only accepted within 5 days of delivery.")
    
    order_item_ids = {item.get("product_id") for item in order.items}
    return_item_ids = {item.get("product_id") for item in data.items}
    
    if not return_item_ids.issubset(order_item_ids):
        raise HTTPException(status_code=400, detail="Some items in return request were not part of the original order")
    
    refund_amount = 0
    for return_item in data.items:
        for order_item in order.items:
            if order_item.get("product_id") == return_item.get("product_id"):
                item_price = order_item.get("price", 0)
                return_qty = return_item.get("quantity", 1)
                order_qty = order_item.get("quantity", 1)
                
                if return_qty > order_qty:
                    raise HTTPException(status_code=400, detail=f"Cannot return more items than ordered for product {return_item.get('product_name', 'Unknown')}")
                
                refund_amount += item_price * return_qty
                break
    
    return_request = ReturnRequest(
        id=generate_id(),
        order_id=order.id,
        user_id=order.user_id,
        items=data.items,
        reason=f"{data.return_type}: {data.reason}",
        refund_method=data.refund_method,
        status="pending",
        refund_amount=refund_amount,
        notes=data.description,
        created_at=datetime.utcnow()
    )
    db.add(return_request)
    
    create_notification(
        db=db,
        user_id=order.user_id,
        type="return_request",
        title="Return Request Submitted",
        message=f"Your return request for order #{order.order_number} has been submitted. We'll review it within 24 hours.",
        data={
            "order_id": order.id,
            "return_id": return_request.id,
            "return_type": data.return_type,
            "refund_amount": refund_amount
        }
    )
    
    create_admin_notification(
        db=db,
        type="return_request",
        title="New Return Request",
        message=f"Return request submitted for order #{order.order_number}. Reason: {data.return_type} - {data.reason}",
        data={
            "order_id": order.id,
            "return_id": return_request.id,
            "customer_name": user["name"],
            "return_type": data.return_type,
            "reason": data.reason,
            "refund_amount": refund_amount,
            "evidence_images": len(data.images or []),
            "evidence_videos": len(data.videos or [])
        }
    )
    
    db.commit()
    
    return {
        "message": "Return request submitted successfully",
        "return_id": return_request.id,
        "order_number": order.order_number,
        "status": "pending",
        "refund_amount": refund_amount,
        "review_timeline": "24 hours",
        "next_steps": "Our team will review your return request and evidence. You'll receive a notification once approved."
    }

@router.get("/orders/{order_id}/returns")
def get_order_returns(order_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if user["role"] != "admin" and order.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    returns = db.query(ReturnRequest).filter(ReturnRequest.order_id == order_id).all()
    return returns

@router.get("/returns")
def get_user_returns(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    returns = db.query(ReturnRequest).filter(
        ReturnRequest.user_id == user["id"]
    ).order_by(ReturnRequest.created_at.desc()).all()
    
    enriched_returns = []
    for return_req in returns:
        order = db.query(Order).filter(Order.id == return_req.order_id).first()
        return_dict = {c.name: getattr(return_req, c.name) for c in return_req.__table__.columns}
        return_dict["order_number"] = order.order_number if order else "Unknown"
        return_dict["order_date"] = order.created_at.isoformat() if order and order.created_at else None
        enriched_returns.append(return_dict)
    
    return enriched_returns

@router.get("/admin/returns")
def get_all_returns(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    admin: dict = Depends(admin_required),
    db: Session = Depends(get_db)
):
    query = db.query(ReturnRequest)
    
    if status:
        query = query.filter(ReturnRequest.status == status)
    
    total = query.count()
    returns = query.order_by(ReturnRequest.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    enriched_returns = []
    for return_req in returns:
        order = db.query(Order).filter(Order.id == return_req.order_id).first()
        # Need user model for name, phone
        from app.models.user import User
        user_obj = db.query(User).filter(User.id == return_req.user_id).first()
        
        return_dict = {c.name: getattr(return_req, c.name) for c in return_req.__table__.columns}
        return_dict["order_number"] = order.order_number if order else "Unknown"
        return_dict["customer_name"] = user_obj.name if user_obj else "Unknown"
        return_dict["customer_phone"] = user_obj.phone if user_obj else "Unknown"
        enriched_returns.append(return_dict)
    
    return {
        "returns": enriched_returns,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }

@router.put("/admin/returns/{return_id}")
def update_return_request(return_id: str, data: ReturnRequestUpdate, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    return_request = db.query(ReturnRequest).filter(ReturnRequest.id == return_id).first()
    if not return_request:
        raise HTTPException(status_code=404, detail="Return request not found")
    
    try:
        order = db.query(Order).filter(Order.id == return_request.order_id).first()
        old_status = return_request.status
        
        return_request.status = data.status
        return_request.updated_at = datetime.utcnow()
        
        if data.admin_notes:
            return_request.notes = f"{return_request.notes or ''}\n\nAdmin Notes: {data.admin_notes}"
        
        if data.refund_amount is not None:
            return_request.refund_amount = data.refund_amount
        
        if data.return_awb:
            return_request.return_awb = data.return_awb
        
        if data.courier_provider:
            return_request.courier_provider = data.courier_provider
        
        if data.status == "approved" and old_status != "approved":
            # Schedule pickup logic omitted (Delhivery integration)
            # Just simple state change
            return_request.pickup_scheduled_date = datetime.utcnow() + timedelta(days=1)
            
            # Restore inventory
            if return_request.items:
                for item in return_request.items:
                    product = db.query(Product).filter(Product.id == item["product_id"]).first()
                    if product:
                        product.stock_qty += item.get("quantity", 1)
        
        if data.status == "picked_up":
            return_request.pickup_completed_date = datetime.utcnow()
        elif data.status == "received":
            return_request.received_date = datetime.utcnow()
        
        db.commit()
        
        if data.status == "approved" and old_status != "approved":
            create_notification(
                db=db,
                user_id=return_request.user_id,
                type="return_approved",
                title="Return Request Approved",
                message=f"Your return request for order #{order.order_number} has been approved.",
                data={"return_id": return_request.id}
            )
            
        db.commit()
        return return_request

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.post("/returns/{return_id}/evidence")
def upload_return_evidence(
    return_id: str,
    files: List[UploadFile] = File(...),
    evidence_type: str = "image",  # image or video
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return_request = db.query(ReturnRequest).filter(ReturnRequest.id == return_id).first()
    if not return_request:
        raise HTTPException(status_code=404, detail="Return request not found")
    
    if user["role"] != "admin" and return_request.user_id != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files allowed per upload")
    
    uploaded_files = []
    
    for file in files:
        if evidence_type == "image":
            if not file.content_type or not file.content_type.startswith('image/'):
                continue
            folder = "returns/images"
        elif evidence_type == "video":
            if not file.content_type or not file.content_type.startswith('video/'):
                continue
            folder = "returns/videos"
        else:
            raise HTTPException(status_code=400, detail="Invalid evidence type")
        
        try:
            file_url = save_uploaded_file(file, folder)
            uploaded_files.append({
                "url": file_url,
                "filename": file.filename,
                "type": evidence_type
            })
        except Exception:
            continue
    
    if evidence_type == "image":
        current_images = return_request.evidence_images or []
        new_images = [f["url"] for f in uploaded_files]
        return_request.evidence_images = current_images + new_images
    else:
        current_videos = return_request.evidence_videos or []
        new_videos = [f["url"] for f in uploaded_files]
        return_request.evidence_videos = current_videos + new_videos
    
    return_request.updated_at = datetime.utcnow()
    db.commit()
    
    create_admin_notification(
        db=db,
        type="return_evidence",
        title="New Return Evidence Uploaded",
        message=f"Customer uploaded {len(uploaded_files)} {evidence_type}(s) for return request {return_id}",
        data={
            "return_id": return_id,
            "evidence_type": evidence_type,
            "file_count": len(uploaded_files),
            "customer_name": user["name"]
        }
    )
    
    return {
        "message": f"Uploaded {len(uploaded_files)} {evidence_type}(s) successfully",
        "files": uploaded_files,
        "return_id": return_id
    }
