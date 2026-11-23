from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies.auth import require_roles

router = APIRouter(prefix="/vendor", tags=["Vendor Dashboard"])
vendor_user = require_roles("vendor")


@router.get("/profile", response_model=schemas.VendorProfileResponse)
def get_vendor_profile(
    vendor: models.User = Depends(vendor_user),
    db: Session = Depends(get_db),
):
    application = db.query(models.VendorApplication).filter(
        models.VendorApplication.user_id == vendor.id
    ).first()
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor profile not found")
    return application


@router.put("/profile", response_model=schemas.VendorProfileResponse)
def update_vendor_profile(
    profile: schemas.VendorProfileUpdate,
    vendor: models.User = Depends(vendor_user),
    db: Session = Depends(get_db),
):
    application = db.query(models.VendorApplication).filter(
        models.VendorApplication.user_id == vendor.id
    ).with_for_update().first()
    if application is None or application.status != "approved":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor profile not found")
    application.business_name = profile.business_name
    application.business_description = profile.business_description
    application.contact_phone = profile.contact_phone
    db.commit()
    db.refresh(application)
    return application


@router.get("/dashboard")
def vendor_dashboard(
    vendor: models.User = Depends(vendor_user),
    db: Session = Depends(get_db),
):
    products = db.query(models.Product).filter(models.Product.vendor_id == vendor.id)
    total_orders = (
        db.query(func.count(func.distinct(models.Order.id)))
        .join(models.OrderItem, models.OrderItem.order_id == models.Order.id)
        .join(models.Product, models.Product.id == models.OrderItem.product_id)
        .filter(models.Product.vendor_id == vendor.id)
        .scalar()
        or 0
    )
    incoming_orders = (
        db.query(func.count(func.distinct(models.Order.id)))
        .join(models.OrderItem, models.OrderItem.order_id == models.Order.id)
        .join(models.Product, models.Product.id == models.OrderItem.product_id)
        .filter(
            models.Product.vendor_id == vendor.id,
            models.OrderItem.status.in_(["pending", "confirmed", "processing"]),
        )
        .scalar()
        or 0
    )
    sales = (
        db.query(func.coalesce(func.sum(models.OrderItem.unit_price * models.OrderItem.quantity), 0))
        .join(models.Product, models.Product.id == models.OrderItem.product_id)
        .filter(
            models.Product.vendor_id == vendor.id,
            models.OrderItem.status == "delivered",
        )
        .scalar()
    )
    application = db.query(models.VendorApplication).filter(
        models.VendorApplication.user_id == vendor.id
    ).first()
    return {
        "business_name": application.business_name if application else vendor.full_name,
        "total_products": products.count(),
        "available_products": products.filter(
            models.Product.is_available.is_(True), models.Product.stock > 0
        ).count(),
        "out_of_stock_products": products.filter(models.Product.stock == 0).count(),
        "total_orders": total_orders,
        "incoming_orders": incoming_orders,
        "delivered_sales": sales,
    }
