from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.api.v1.endpoints.auth import get_current_user, admin_required
from app.models.user import Notification

router = APIRouter()

@router.get("/notifications")
def get_user_notifications(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    notifications = db.query(Notification).filter(
        Notification.user_id == user["id"],
        Notification.for_admin == False
    ).order_by(Notification.created_at.desc()).limit(50).all()
    
    unread_count = db.query(Notification).filter(
        Notification.user_id == user["id"],
        Notification.read == False,
        Notification.for_admin == False
    ).count()
    
    return {"notifications": notifications, "unread_count": unread_count}

@router.get("/notifications/unread-count")
def get_unread_notification_count(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    unread_count = db.query(Notification).filter(
        Notification.user_id == user["id"],
        Notification.read == False,
        Notification.for_admin == False
    ).count()
    
    return {"unread_count": unread_count}

@router.put("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    note = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user["id"]
    ).first()
    
    if note:
        note.read = True
        db.commit()
    return {"message": "Notification marked as read"}

@router.put("/notifications/mark-all-read")
def mark_all_read(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(
        Notification.user_id == user["id"],
        Notification.for_admin == False
    ).update({"read": True})
    db.commit()
    return {"message": "All notifications marked as read"}

@router.delete("/notifications/{notification_id}")
def delete_notification(notification_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    note = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user["id"]
    ).first()
    
    if note:
        db.delete(note)
        db.commit()
    return {"message": "Notification deleted"}

@router.delete("/notifications")
def clear_all_notifications(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter(
        Notification.user_id == user["id"],
        Notification.for_admin == False
    ).delete()
    db.commit()
    return {"message": "All notifications cleared"}

@router.get("/admin/notifications")
def get_admin_notifications(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    notifications = db.query(Notification).filter(
        Notification.for_admin == True
    ).order_by(Notification.created_at.desc()).limit(50).all()
    
    unread_count = db.query(Notification).filter(
        Notification.for_admin == True,
        Notification.read == False
    ).count()
    
    return {"notifications": notifications, "unread_count": unread_count}

@router.get("/admin/notifications/unread-count")
def get_admin_unread_count(admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    unread_count = db.query(Notification).filter(
        Notification.for_admin == True,
        Notification.read == False
    ).count()
    
    return {"unread_count": unread_count}

@router.put("/admin/notifications/{notification_id}/read")
def mark_admin_notification_read(notification_id: str, admin: dict = Depends(admin_required), db: Session = Depends(get_db)):
    note = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.for_admin == True
    ).first()
    
    if note:
        note.read = True
        db.commit()
    return {"message": "Notification marked as read"}
