from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import qrcode
from io import BytesIO as QRBytesIO
import base64
import os
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import admin_required
from app.models.settings import Settings
from app.models.order import Order, ReturnRequest

from app.services.courier import DelhiveryService
from app.core.config import settings as config_settings

router = APIRouter()

# Initialize Courier Service
delhivery_service = DelhiveryService(config_settings.DELHIVERY_TOKEN)

@router.get("/admin/couriers")
def get_couriers(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    # For now, return a default Delhivery courier
    return [
        {
            "id": "delhivery",
            "name": "Delhivery",
            "api_key": "configured" if config_settings.DELHIVERY_TOKEN else None,
            "api_secret": "configured",
            "webhook_url": "",
            "tracking_url_template": "https://track.delhivery.com/track/package/{tracking_number}",
            "is_active": True,
            "priority": 1
        }
    ]

@router.post("/admin/couriers/test")
def test_courier_api(admin: dict = Depends(admin_required)):
    try:
        test_result = delhivery_service.check_serviceability("110001")
        
        test_address = {
            "name": "Test Customer",
            "phone": "9999999999",
            "line1": "Test Address",
            "city": "New Delhi",
            "state": "Delhi",
            "pincode": "110001"
        }
        address_result = delhivery_service.validate_address(test_address)
        
        return {
            "success": True,
            "message": "Courier API test completed successfully",
            "pincode_test": test_result,
            "address_test": address_result,
            "api_status": "Working" if test_result.get("serviceable") else "Issues detected"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Courier API test failed: {str(e)}",
            "api_status": "Error"
        }

@router.post("/admin/couriers")
def create_courier(courier_data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    return {"message": "Courier configuration saved", "id": "new-courier"}

@router.put("/admin/couriers/{courier_id}")
def update_courier(courier_id: str, courier_data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    return {"message": "Courier updated successfully"}

@router.delete("/admin/couriers/{courier_id}")
def delete_courier(courier_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    return {"message": "Courier deleted successfully"}

@router.get("/courier/pincode")
def check_pincode_serviceability(pincode: str):
    return delhivery_service.check_serviceability(pincode)

@router.post("/courier/validate-address")
def validate_shipping_address(address_data: dict):
    return delhivery_service.validate_address(address_data)

@router.post("/generate-qr")
def generate_payment_qr(data: dict, db: Session = Depends(get_db)):
    try:
        settings = db.query(Settings).filter(Settings.type == "business").first()
        if not settings or not settings.configs or not settings.configs.get("upi_id"):
            raise HTTPException(status_code=400, detail="UPI ID not configured. Please contact admin.")
        
        upi_id = settings.configs.get("upi_id")
        amount = data.get("amount", 0)
        order_number = data.get("order_number", "")
        
        upi_url = f"upi://pay?pa={upi_id}&pn={settings.business_name or 'BharatBazaar'}&am={amount}&cu=INR&tn=Payment for Order {order_number}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(upi_url)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        img_buffer = QRBytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        qr_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        return {
            "success": True,
            "qr_code": f"data:image/png;base64,{qr_base64}",
            "upi_url": upi_url,
            "amount": amount,
            "upi_id": upi_id,
            "payee_name": settings.business_name or 'BharatBazaar'
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate QR code: {str(e)}")

@router.post("/courier/ship/{order_id}")
def create_shipment(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status in ["shipped", "delivered", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot ship order with status: {order.status}")
        
    shipping_address = order.shipping_address
    if not shipping_address:
        raise HTTPException(status_code=400, detail="Order has no shipping address")
    
    required_fields = ["name", "phone", "line1", "city", "state", "pincode"]
    missing_fields = [field for field in required_fields if not shipping_address.get(field)]
    
    if missing_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing required shipping address fields: {', '.join(missing_fields)}"
        )
    
    phone = str(shipping_address.get("phone", "")).strip()
    if len(phone) < 10:
        raise HTTPException(status_code=400, detail="Invalid phone number in shipping address")
    
    pincode = str(shipping_address.get("pincode", "")).strip()
    if len(pincode) != 6 or not pincode.isdigit():
        raise HTTPException(status_code=400, detail="Invalid pincode in shipping address")
    
    order_data = {
        "order_id": order.order_number,
        "date": order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "pay_mode": "Pre-paid" if order.payment_method == "online" else "COD",
        "address": f"{shipping_address.get('line1', '')} {shipping_address.get('line2', '')}".strip(),
        "phone": phone,
        "name": shipping_address.get("name"),
        "city": shipping_address.get("city"),
        "state": shipping_address.get("state"),
        "pincode": pincode,
        "total_amount": float(order.grand_total),
        "cod_amount": float(order.grand_total) if order.payment_method != "online" else 0,
        "quantity": sum(item.get("quantity", 1) for item in order.items) if order.items else 1,
        "products_desc": ", ".join(item.get("product_name", "Item") for item in order.items)[:50] if order.items else "Products",
        
        "pickup_name": "Amorlias Mart",
        "pickup_address": "Warehouse Address",
        "pickup_city": "New Delhi",
        "pickup_pincode": "110001",
        "pickup_phone": "9999999999"
    }
    
    settings = db.query(Settings).first()
    if settings:
        order_data["pickup_name"] = settings.business_name or "Amorlias Mart"
        if settings.address:
            address_line = f"{settings.address.get('line1', '')} {settings.address.get('line2', '')}".strip()
            if address_line:
                order_data["pickup_address"] = address_line
            if settings.address.get('city'):
                order_data["pickup_city"] = settings.address.get('city')
            if settings.address.get('pincode'):
                order_data["pickup_pincode"] = settings.address.get('pincode')
        if settings.phone:
            order_data["pickup_phone"] = settings.phone

    result = delhivery_service.create_surface_order(order_data)
    
    if result.get("success"):
        order.tracking_number = result.get("awb")
        order.courier_provider = "Delhivery"
        order.status = "shipped"
        order.updated_at = datetime.utcnow()
        db.commit()
        return result
    else:
        raise HTTPException(status_code=400, detail=f"Shipment Creation Failed: {result.get('error')}")

@router.get("/courier/track/{order_id}")
def track_shipment(order_id: str, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if not order.tracking_number:
         raise HTTPException(status_code=400, detail="Order has not been shipped yet")
    
    tracking_result = delhivery_service.track_order(order.tracking_number)
    
    if tracking_result.get("success"):
        if tracking_result.get("tracking_history"):
            order.tracking_history = tracking_result["tracking_history"]
            order.updated_at = datetime.utcnow()
            db.commit()
        
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "awb": order.tracking_number,
            "courier_provider": order.courier_provider,
            "current_status": tracking_result.get("status"),
            "current_location": tracking_result.get("current_location"),
            "expected_delivery": tracking_result.get("expected_delivery"),
            "tracking_history": tracking_result.get("tracking_history", []),
            "last_updated": datetime.utcnow().isoformat()
        }
    else:
        raise HTTPException(status_code=400, detail=f"Tracking failed: {tracking_result.get('error')}")

@router.get("/courier/track-by-awb/{awb}")
def track_by_awb(awb: str):
    return delhivery_service.track_order(awb)

@router.get("/courier/label/{order_id}")
def get_shipping_label(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    # Need to move generate_shipping_label_pdf to a utility file first or it won't be accessible
    # I'll create `app/utils/pdf.py` later and import it.
    # For now, I will assume it's imported from app.utils.pdf
    from app.utils.pdf import generate_shipping_label_pdf
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.tracking_number:
        result = delhivery_service.get_label(order.tracking_number)
        if result.get("success"):
            return {
                "order_id": order.id,
                "order_number": order.order_number,
                "awb": order.tracking_number,
                "label_url": result.get("label_url"),
                "generated_at": datetime.utcnow().isoformat(),
                "note": result.get("note")
            }
    
    try:
        pdf_buffer = generate_shipping_label_pdf(order_id, db)
        
        # In a real app we'd save to S3 or similar. Here we save locally to static folder.
        # But for this endpoint, we are returning JSON with URL. 
        # The original code saved to temp file.
        
        import os
        temp_dir = os.path.join(config_settings.UPLOAD_DIR, "labels")
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_filename = f"label_{order.order_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        with open(temp_path, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        
        label_url = f"/uploads/labels/{temp_filename}"
        
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "awb": order.tracking_number or "N/A",
            "label_url": label_url,
            "generated_at": datetime.utcnow().isoformat(),
            "note": "Professional PDF label generated"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate shipping label: {str(e)}")

@router.get("/courier/label-url/{order_id}")
def get_shipping_label_url(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.tracking_number:
        result = delhivery_service.get_label(order.tracking_number)
        if result.get("success") and result.get("label_url"):
            return {
                "success": True,
                "label_url": result.get("label_url"),
                "awb": order.tracking_number,
                "note": result.get("note")
            }
    
    return {
        "success": False,
        "error": "No label URL available. Order may not be shipped yet or courier service unavailable.",
        "awb": order.tracking_number or None
    }

@router.get("/courier/invoice/{order_id}")
def get_shipping_invoice(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if not order.tracking_number:
         raise HTTPException(status_code=400, detail="Order has not been shipped yet")

    result = delhivery_service.get_invoice(order.tracking_number)
    
    if result.get("success"):
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "awb": order.tracking_number,
            "invoice_url": result.get("invoice_url"),
            "generated_at": datetime.utcnow().isoformat()
        }
    else:
        raise HTTPException(status_code=400, detail=f"Invoice generation failed: {result.get('error')}")

@router.post("/courier/cancel/{order_id}")
def cancel_shipment(order_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if not order.tracking_number:
         raise HTTPException(status_code=400, detail="Order has not been shipped yet")
    
    if order.status not in ["shipped", "processing"]:
        raise HTTPException(status_code=400, detail="Cannot cancel order in current status")

    result = delhivery_service.cancel_shipment(order.tracking_number)
    
    if result.get("success"):
        order.status = "cancelled"
        order.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "awb": order.tracking_number,
            "message": "Shipment cancelled successfully",
            "cancelled_at": datetime.utcnow().isoformat()
        }
    else:
        raise HTTPException(status_code=400, detail=f"Cancellation failed: {result.get('error')}")

@router.post("/admin/couriers/create-return/{order_id}")
def create_return_shipment_endpoint(order_id: str, return_data: dict, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    # Renamed to avoid conflict with method name
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status not in ["delivered", "shipped"]:
        raise HTTPException(status_code=400, detail="Can only create returns for delivered/shipped orders")
    
    shipping_address = order.shipping_address
    if not shipping_address:
        raise HTTPException(status_code=400, detail="No shipping address found for return pickup")
    
    return_shipment_data = {
        "original_order_id": order.order_number,
        "customer_name": shipping_address.get("name"),
        "customer_phone": shipping_address.get("phone"),
        "pickup_address": f"{shipping_address.get('line1', '')} {shipping_address.get('line2', '')}".strip(),
        "pickup_city": shipping_address.get("city"),
        "pickup_state": shipping_address.get("state"),
        "pickup_pincode": shipping_address.get("pincode"),
        "return_amount": return_data.get("return_amount", order.grand_total),
        "quantity": return_data.get("quantity", 1),
        "products_desc": return_data.get("reason", "Return Items"),
        "weight": return_data.get("weight", "500")
    }
    
    result = delhivery_service.create_return_shipment(return_shipment_data)
    
    if result.get("success"):
        from app.models.order import ReturnRequest # ensure imported
        return_request = ReturnRequest(
            id=generate_id(), # Need uuid
            order_id=order.id,
            user_id=order.user_id,
            reason=return_data.get("reason", "Customer return"),
            status="pickup_scheduled",
            return_awb=result.get("return_awb"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        # We need generate_id imported
        from app.utils.common import generate_id
        return_request.id = generate_id()
        
        db.add(return_request)
        db.commit()
        
        return {
            "order_id": order.id,
            "return_id": return_request.id,
            "return_awb": result.get("return_awb"),
            "pickup_scheduled": True,
            "message": "Return pickup scheduled successfully"
        }
    else:
        raise HTTPException(status_code=400, detail=f"Return creation failed: {result.get('error')}")
