from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.product import Wishlist, WishlistCategory, Product
from app.schemas.product import WishlistItemAdd
from app.utils.common import generate_id

router = APIRouter()

@router.get("/wishlist/categories")
def get_user_wishlist_categories(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        categories = db.query(WishlistCategory).filter(
            WishlistCategory.user_id == user["id"]
        ).order_by(WishlistCategory.is_default.desc(), WishlistCategory.created_at.asc()).all()
        
        if not categories:
            default_category = WishlistCategory(
                id=generate_id(),
                user_id=user["id"],
                name="My Wishlist",
                description="Default wishlist category",
                color="#3B82F6",
                icon="heart",
                is_default=True
            )
            db.add(default_category)
            db.commit()
            db.refresh(default_category)
            categories = [default_category]
        
        categories_with_count = []
        for category in categories:
            try:
                category_dict = {c.name: getattr(category, c.name) for c in category.__table__.columns}
                
                item_count = db.query(Wishlist).filter(
                    Wishlist.user_id == user["id"],
                    Wishlist.category_id == category.id
                ).count()
                category_dict['item_count'] = item_count
                
                categories_with_count.append(category_dict)
            except Exception as e:
                print(f"Error processing category {category.id}: {e}")
                categories_with_count.append({
                    'id': category.id,
                    'name': category.name,
                    'description': category.description,
                    'color': category.color,
                    'icon': category.icon,
                    'is_default': category.is_default,
                    'user_id': category.user_id,
                    'created_at': category.created_at.isoformat() if category.created_at else None,
                    'item_count': 0
                })
        
        return {"categories": categories_with_count}
        
    except Exception as e:
        print(f"Error in get_user_wishlist_categories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")

@router.post("/wishlist/categories")
def create_wishlist_category(data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    name = data.get("name", "").strip()
    description = data.get("description", "")
    color = data.get("color", "#3B82F6")
    icon = data.get("icon", "heart")
    
    if not name:
        raise HTTPException(status_code=400, detail="Category name is required")
    
    existing = db.query(WishlistCategory).filter(
        WishlistCategory.user_id == user["id"],
        WishlistCategory.name == name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Category name already exists")
    
    category = WishlistCategory(
        id=generate_id(),
        user_id=user["id"],
        name=name,
        description=description,
        color=color,
        icon=icon,
        is_default=False
    )
    
    db.add(category)
    db.commit()
    db.refresh(category)
    
    category_dict = {c.name: getattr(category, c.name) for c in category.__table__.columns}
    category_dict['item_count'] = 0
    
    return {"message": "Category created successfully", "category": category_dict}

@router.put("/wishlist/categories/{category_id}")
def update_wishlist_category(category_id: str, data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    category = db.query(WishlistCategory).filter(
        WishlistCategory.id == category_id,
        WishlistCategory.user_id == user["id"]
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if "name" in data and data["name"].strip():
        existing = db.query(WishlistCategory).filter(
            WishlistCategory.user_id == user["id"],
            WishlistCategory.name == data["name"].strip(),
            WishlistCategory.id != category_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Category name already exists")
        
        category.name = data["name"].strip()
    
    if "description" in data:
        category.description = data["description"]
    
    if "color" in data:
        category.color = data["color"]
    
    if "icon" in data:
        category.icon = data["icon"]
    
    db.commit()
    return {"message": "Category updated successfully", "category": category}

@router.delete("/wishlist/categories/{category_id}")
def delete_wishlist_category(category_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    category = db.query(WishlistCategory).filter(
        WishlistCategory.id == category_id,
        WishlistCategory.user_id == user["id"]
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    if category.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default category")
    
    default_category = db.query(WishlistCategory).filter(
        WishlistCategory.user_id == user["id"],
        WishlistCategory.is_default == True
    ).first()
    
    if not default_category:
        default_category = WishlistCategory(
            id=generate_id(),
            user_id=user["id"],
            name="My Wishlist",
            description="Default wishlist category",
            color="#3B82F6",
            icon="heart",
            is_default=True
        )
        db.add(default_category)
        db.commit()
        db.refresh(default_category)
    
    db.query(Wishlist).filter(
        Wishlist.category_id == category_id
    ).update({"category_id": default_category.id})
    
    db.delete(category)
    db.commit()
    
    return {"message": "Category deleted successfully"}

@router.get("/wishlist")
def get_user_wishlist(category_id: str = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Wishlist).filter(
        Wishlist.user_id == user["id"]
    )
    
    if category_id:
        query = query.filter(Wishlist.category_id == category_id)
    
    wishlist_items = query.order_by(Wishlist.created_at.desc()).all()
    
    products = []
    for item in wishlist_items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            product_dict = {c.name: getattr(product, c.name) for c in product.__table__.columns}
            product_dict['wishlist_id'] = item.id
            product_dict['category_id'] = item.category_id
            product_dict['notes'] = item.notes
            product_dict['priority'] = item.priority
            product_dict['added_at'] = item.created_at
            products.append(product_dict)
    
    return {"wishlist": products}

@router.post("/wishlist/{product_id}")
def add_to_wishlist(product_id: str, item_data: WishlistItemAdd = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    existing = db.query(Wishlist).filter(
        Wishlist.user_id == user["id"],
        Wishlist.product_id == product_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Product already in wishlist")
    
    category_id = None
    notes = ""
    priority = 1
    
    if item_data:
        category_id = item_data.category_id
        notes = item_data.notes or ""
        priority = item_data.priority
    
    if not category_id:
        default_category = db.query(WishlistCategory).filter(
            WishlistCategory.user_id == user["id"],
            WishlistCategory.is_default == True
        ).first()
        
        if not default_category:
            default_category = WishlistCategory(
                id=generate_id(),
                user_id=user["id"],
                name="My Wishlist",
                description="Default wishlist category",
                color="#3B82F6",
                icon="heart",
                is_default=True
            )
            db.add(default_category)
            db.commit()
            db.refresh(default_category)
        
        category_id = default_category.id
    else:
        category = db.query(WishlistCategory).filter(
            WishlistCategory.id == category_id,
            WishlistCategory.user_id == user["id"]
        ).first()
        
        if not category:
            raise HTTPException(status_code=400, detail="Invalid category")
    
    wishlist_item = Wishlist(
        id=generate_id(),
        user_id=user["id"],
        product_id=product_id,
        category_id=category_id,
        notes=notes,
        priority=priority
    )
    
    db.add(wishlist_item)
    db.commit()
    
    return {"message": "Product added to wishlist", "product": product}

@router.put("/wishlist/{wishlist_id}")
def update_wishlist_item(wishlist_id: str, data: dict, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    wishlist_item = db.query(Wishlist).filter(
        Wishlist.id == wishlist_id,
        Wishlist.user_id == user["id"]
    ).first()
    
    if not wishlist_item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    
    if "category_id" in data:
        if data["category_id"]:
            category = db.query(WishlistCategory).filter(
                WishlistCategory.id == data["category_id"],
                WishlistCategory.user_id == user["id"]
            ).first()
            
            if not category:
                raise HTTPException(status_code=400, detail="Invalid category")
        
        wishlist_item.category_id = data["category_id"]
    
    if "notes" in data:
        wishlist_item.notes = data["notes"]
    
    if "priority" in data:
        priority = data["priority"]
        if priority not in [1, 2, 3]:
            raise HTTPException(status_code=400, detail="Priority must be 1 (Low), 2 (Medium), or 3 (High)")
        wishlist_item.priority = priority
    
    db.commit()
    return {"message": "Wishlist item updated successfully"}

@router.delete("/wishlist/{product_id}")
def remove_from_wishlist(product_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    wishlist_item = db.query(Wishlist).filter(
        Wishlist.user_id == user["id"],
        Wishlist.product_id == product_id
    ).first()
    
    if not wishlist_item:
        raise HTTPException(status_code=404, detail="Product not in wishlist")
    
    db.delete(wishlist_item)
    db.commit()
    
    return {"message": "Product removed from wishlist"}

@router.delete("/wishlist")
def clear_wishlist(category_id: str = None, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Wishlist).filter(Wishlist.user_id == user["id"])
    
    if category_id:
        query = query.filter(Wishlist.category_id == category_id)
        message = "Category cleared"
    else:
        message = "Wishlist cleared"
    
    query.delete()
    db.commit()
    
    return {"message": message}

@router.get("/wishlist/check/{product_id}")
def check_wishlist_status(product_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    wishlist_item = db.query(Wishlist).filter(
        Wishlist.user_id == user["id"],
        Wishlist.product_id == product_id
    ).first()
    
    return {
        "in_wishlist": wishlist_item is not None,
        "wishlist_item": {
            "id": wishlist_item.id,
            "category_id": wishlist_item.category_id,
            "notes": wishlist_item.notes,
            "priority": wishlist_item.priority
        } if wishlist_item else None
    }
