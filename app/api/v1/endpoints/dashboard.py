from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.db.session import get_db
from app.api.v1.endpoints.auth import admin_required
from app.models.product import Product
from app.models.order import Order, ReturnRequest
from app.models.user import User

router = APIRouter()

@router.get("/admin/dashboard")
def get_dashboard_stats(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    total_products = db.query(Product).count()
    total_orders = db.query(Order).count()
    total_customers = db.query(User).filter(User.role == "customer").count()
    
    pending_orders = db.query(Order).filter(Order.status == "pending").count()
    
    low_stock_products = db.query(Product).filter(
        Product.stock_qty <= Product.low_stock_threshold
    ).count()
    
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_orders = db.query(Order).filter(
        Order.created_at >= thirty_days_ago,
        Order.status.in_(["completed", "shipped", "delivered"])
    ).all()
    
    total_revenue = sum(order.grand_total for order in recent_orders)
    
    top_products = db.query(Product).filter(
        Product.is_active == True
    ).order_by(Product.created_at.desc()).limit(5).all()
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    today_orders = db.query(Order).filter(Order.created_at >= today_start).all()
    today_revenue = sum(o.grand_total for o in today_orders)
    today_order_count = len(today_orders)
    
    pending_returns = db.query(ReturnRequest).filter(ReturnRequest.status == "pending").count()
    
    return {
        "today": {
            "revenue": today_revenue,
            "orders": today_order_count
        },
        "totals": {
            "products": total_products,
            "customers": total_customers,
            "orders": total_orders
        },
        "pending": {
            "orders": pending_orders,
            "low_stock": low_stock_products,
            "returns": pending_returns
        },
        "stats": { 
            "total_revenue_30d": total_revenue
        },
        "top_products": top_products,
        "recent_orders": db.query(Order).order_by(Order.created_at.desc()).limit(10).all()
    }

@router.get("/admin/reports/sales")
def get_sales_report(
    date_from: str = None, 
    date_to: str = None,
    admin: dict = Depends(admin_required), 
    db: Session = Depends(get_db)
):
    query = db.query(Order).filter(Order.status != "cancelled")
    
    if date_from:
        try:
           dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
           query = query.filter(Order.created_at >= dt_from)
        except:
           pass

    orders = query.all()
    
    total_sales = sum(o.grand_total for o in orders)
    total_orders = len(orders)
    online_sales = sum(o.grand_total for o in orders if o.payment_method == "online")
    offline_sales = sum(o.grand_total for o in orders if o.payment_method != "online")
    
    daily_map = {}
    for o in orders:
        date_key = o.created_at.date().isoformat()
        if date_key not in daily_map:
            daily_map[date_key] = {"date": date_key, "sales": 0, "orders": 0}
        daily_map[date_key]["sales"] += o.grand_total
        daily_map[date_key]["orders"] += 1
        
    daily_breakdown = sorted(daily_map.values(), key=lambda x: x["date"])
    
    return {
        "summary": {
            "total_sales": total_sales,
            "total_orders": total_orders,
            "online_sales": online_sales,
            "offline_sales": offline_sales
        },
        "daily_breakdown": daily_breakdown
    }

@router.get("/admin/reports/inventory")
def get_inventory_report(
    admin: dict = Depends(admin_required), 
    db: Session = Depends(get_db)
):
    products = db.query(Product).all()
    
    total_products = len(products)
    total_stock_value = sum(p.stock_qty * p.cost_price for p in products)
    low_stock_products = [p for p in products if p.stock_qty <= p.low_stock_threshold]
    out_of_stock_products = [p for p in products if p.stock_qty == 0]
    
    return {
        "summary": {
            "total_products": total_products,
            "total_stock_value": total_stock_value,
            "low_stock_count": len(low_stock_products),
            "out_of_stock_count": len(out_of_stock_products)
        },
        "low_stock_products": low_stock_products,
        "out_of_stock_products": out_of_stock_products
    }

@router.get("/admin/reports/profit-loss")
def get_profit_loss_report(
    date_from: str = None,
    admin: dict = Depends(admin_required), 
    db: Session = Depends(get_db)
):
    orders_query = db.query(Order).filter(Order.status != "cancelled")
    returns_query = db.query(ReturnRequest).filter(ReturnRequest.status == "approved")
    
    if date_from:
        try:
           dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
           orders_query = orders_query.filter(Order.created_at >= dt_from)
           returns_query = returns_query.filter(ReturnRequest.created_at >= dt_from)
        except:
           pass
           
    orders = orders_query.all()
    returns = returns_query.all()
    
    total_revenue = sum(o.grand_total for o in orders)
    
    total_cost = 0
    for o in orders:
        for item in o.items:
            prod = db.query(Product).filter(Product.id == item["product_id"]).first()
            if prod:
                total_cost += prod.cost_price * item["quantity"]
            else:
                total_cost += item["price"] * 0.7 * item["quantity"]
                
    total_refunds = sum(r.refund_amount or 0 for r in returns)
    
    gross_profit = total_revenue - total_cost
    net_profit = gross_profit - total_refunds
    
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    return {
        "summary": {
            "total_revenue": total_revenue,
            "total_cost": total_cost,
            "total_refunds": total_refunds,
            "gross_profit": gross_profit,
            "net_profit": net_profit,
            "profit_margin": profit_margin
        },
        "orders_count": len(orders),
        "returns_count": len(returns)
    }

@router.get("/admin/reports/inventory-status")
def get_inventory_status_report(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    try:
        products = db.query(Product).filter(Product.is_active == True).all()
        
        inventory_report = []
        
        for product in products:
            pending_orders = db.query(Order).filter(
                Order.status.in_(["pending", "processing"])
            ).all()
            
            blocked_qty = 0
            for order in pending_orders:
                for item in order.items:
                    if item.get("product_id") == product.id:
                        blocked_qty += item.get("quantity", 0)
            
            available_qty = max(0, product.stock_qty - blocked_qty)
            
            if product.stock_qty <= 0:
                stock_status = "out_of_stock"
            elif product.stock_qty <= product.low_stock_threshold:
                stock_status = "low_stock"
            elif available_qty <= product.low_stock_threshold:
                stock_status = "reserved_low"
            else:
                stock_status = "in_stock"
            
            inventory_report.append({
                "product_id": product.id,
                "product_name": product.name,
                "sku": product.sku,
                "category_name": product.category.name if product.category else "Uncategorized",
                "total_stock": product.stock_qty,
                "blocked_qty": blocked_qty,
                "available_qty": available_qty,
                "low_stock_threshold": product.low_stock_threshold,
                "stock_status": stock_status,
                "selling_price": product.selling_price,
                "cost_price": product.cost_price,
                "stock_value": product.stock_qty * product.cost_price,
                "available_value": available_qty * product.cost_price
            })
        
        total_products = len(inventory_report)
        total_stock_value = sum(item["stock_value"] for item in inventory_report)
        total_available_value = sum(item["available_value"] for item in inventory_report)
        total_blocked_value = total_stock_value - total_available_value
        
        out_of_stock_count = len([item for item in inventory_report if item["stock_status"] == "out_of_stock"])
        low_stock_count = len([item for item in inventory_report if item["stock_status"] in ["low_stock", "reserved_low"]])
        in_stock_count = len([item for item in inventory_report if item["stock_status"] == "in_stock"])
        
        return {
            "summary": {
                "total_products": total_products,
                "total_stock_value": total_stock_value,
                "total_available_value": total_available_value,
                "total_blocked_value": total_blocked_value,
                "out_of_stock_count": out_of_stock_count,
                "low_stock_count": low_stock_count,
                "in_stock_count": in_stock_count
            },
            "products": inventory_report
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate inventory report: {str(e)}")
