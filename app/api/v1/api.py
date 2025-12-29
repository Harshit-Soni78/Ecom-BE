from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth, users, products, categories, inventory, orders, returns,
    banners, offers, upload, settings, courier, dashboard, pages,
    wishlist, notifications
)

api_router = APIRouter()

api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(products.router, tags=["products"])
api_router.include_router(categories.router, tags=["categories"])
api_router.include_router(inventory.router, tags=["inventory"])
api_router.include_router(orders.router, tags=["orders"])
api_router.include_router(returns.router, tags=["returns"])
api_router.include_router(banners.router, tags=["banners"])
api_router.include_router(offers.router, tags=["offers"])
api_router.include_router(upload.router, tags=["upload"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(courier.router, tags=["courier"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(pages.router, tags=["pages"])
api_router.include_router(wishlist.router, tags=["wishlist"])
api_router.include_router(notifications.router, tags=["notifications"])
