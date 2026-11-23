from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.dependencies.auth import require_roles

router = APIRouter(prefix="/admin", tags=["Administration"])
admin_user = require_roles("admin")


@router.get("/dashboard")
def admin_dashboard(
    _admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    recent_orders = (
        db.query(models.Order)
        .order_by(models.Order.created_at.desc())
        .limit(5)
        .all()
    )
    return {
        "total_customers": db.query(models.User).filter(models.User.role == "customer").count(),
        "total_vendors": db.query(models.User).filter(models.User.role == "vendor").count(),
        "pending_vendor_applications": db.query(models.VendorApplication)
        .filter(models.VendorApplication.status == "pending")
        .count(),
        "total_products": db.query(models.Product).count(),
        "total_orders": db.query(models.Order).count(),
        "recent_orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "customer_id": order.customer_id,
                "total_amount": order.total_amount,
                "status": order.status,
                "created_at": order.created_at,
            }
            for order in recent_orders
        ],
    }


@router.get("/users", response_model=list[schemas.UserResponse])
def list_users(
    role: str | None = None,
    is_active: bool | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.User)
    if role is not None:
        if role not in {"customer", "vendor", "admin"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Role must be customer, vendor, or admin",
            )
        query = query.filter(models.User.role == role)
    if is_active is not None:
        query = query.filter(models.User.is_active.is_(is_active))
    return query.order_by(models.User.created_at.desc()).offset(offset).limit(limit).all()


@router.patch("/users/{user_id}/status", response_model=schemas.UserResponse)
def update_user_status(
    user_id: int,
    update: schemas.UserActiveUpdate,
    current_admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    if user_id == current_admin.id and not update.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot deactivate your own administrator account",
        )
    user = db.query(models.User).filter(models.User.id == user_id).with_for_update().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.is_active = update.is_active
    db.commit()
    db.refresh(user)
    return user


@router.get("/products", response_model=list[schemas.ProductResponse])
def list_all_products(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Product)
        .options(
            joinedload(models.Product.vendor).joinedload(models.User.vendor_application)
        )
        .order_by(models.Product.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.patch("/products/{product_id}/availability", response_model=schemas.ProductResponse)
def update_product_availability(
    product_id: int,
    update: schemas.ProductAvailabilityUpdate,
    _admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    product = db.query(models.Product).filter(
        models.Product.id == product_id
    ).with_for_update().first()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    product.is_available = update.is_available
    product_id = product.id
    db.commit()
    return (
        db.query(models.Product)
        .options(joinedload(models.Product.vendor).joinedload(models.User.vendor_application))
        .filter(models.Product.id == product_id)
        .one()
    )


@router.get("/orders", response_model=list[schemas.OrderResponse])
def list_all_orders(
    order_status: str | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    allowed_statuses = {"pending", "confirmed", "processing", "shipped", "delivered", "cancelled"}
    if order_status is not None and order_status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid order status",
        )
    query = db.query(models.Order).options(joinedload(models.Order.items))
    if order_status is not None:
        query = query.filter(models.Order.status == order_status)
    orders = query.order_by(models.Order.created_at.desc()).offset(offset).limit(limit).all()
    from app.orders import _order_response

    return [_order_response(order) for order in orders]


@router.patch("/orders/{order_id}/status", response_model=schemas.OrderResponse)
def update_order_status(
    order_id: int,
    update: schemas.OrderStatusUpdate,
    _admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id
    ).with_for_update().first()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    if order.status == "cancelled" and update.status != "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A cancelled order cannot be reopened",
        )

    items = db.query(models.OrderItem).filter(
        models.OrderItem.order_id == order.id
    ).with_for_update().all()
    if update.status == "cancelled":
        if order.payment_status == "paid" or any(
            item.status in {"shipped", "delivered"} for item in items
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Paid or shipped orders cannot be cancelled",
            )
        for item in items:
            if item.status != "cancelled":
                product = db.query(models.Product).filter(
                    models.Product.id == item.product_id
                ).with_for_update().first()
                product.stock += item.quantity
            item.status = "cancelled"
    else:
        for item in items:
            if item.status != "cancelled":
                item.status = update.status
    order.status = update.status
    order_id = order.id
    db.commit()
    from app.orders import _load_order, _order_response

    return _order_response(_load_order(order_id, db))


@router.patch("/orders/{order_id}/payment", response_model=schemas.OrderResponse)
def update_order_payment_status(
    order_id: int,
    update: schemas.PaymentStatusUpdate,
    _admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id
    ).with_for_update().first()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    if update.payment_status == "paid" and order.status != "delivered":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment on delivery can be marked paid after delivery",
        )
    order.payment_status = update.payment_status
    order_id = order.id
    db.commit()
    from app.orders import _load_order, _order_response

    return _order_response(_load_order(order_id, db))


@router.get(
    "/vendors/applications",
    response_model=list[schemas.VendorApplicationResponse],
)
def list_vendor_applications(
    application_status: str | None = Query(default="pending", alias="status"),
    _admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    allowed_statuses = {"pending", "approved", "rejected"}
    if application_status is not None and application_status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Status must be pending, approved, or rejected",
        )

    query = db.query(models.VendorApplication).options(
        joinedload(models.VendorApplication.user)
    )
    if application_status is not None:
        query = query.filter(models.VendorApplication.status == application_status)
    return query.order_by(models.VendorApplication.submitted_at.asc()).all()


@router.patch(
    "/vendors/{application_id}/approve",
    response_model=schemas.VendorApplicationResponse,
)
def approve_vendor_application(
    application_id: int,
    review: schemas.VendorApplicationReview | None = None,
    current_admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    application = db.query(models.VendorApplication).filter(
        models.VendorApplication.id == application_id
    ).with_for_update().first()
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor application not found",
        )
    if application.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Application has already been {application.status}",
        )

    applicant = db.query(models.User).filter(
        models.User.id == application.user_id
    ).with_for_update().first()
    if applicant is None or not applicant.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Applicant account is unavailable",
        )

    application.status = "approved"
    application.review_note = review.review_note if review else None
    application.reviewed_by_id = current_admin.id
    application.reviewed_at = datetime.now(timezone.utc)
    applicant.role = "vendor"
    db.commit()
    db.refresh(application)
    return application


@router.patch(
    "/vendors/{application_id}/reject",
    response_model=schemas.VendorApplicationResponse,
)
def reject_vendor_application(
    application_id: int,
    review: schemas.VendorApplicationReview | None = None,
    current_admin: models.User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    application = db.query(models.VendorApplication).filter(
        models.VendorApplication.id == application_id
    ).with_for_update().first()
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor application not found",
        )
    if application.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Application has already been {application.status}",
        )

    application.status = "rejected"
    application.review_note = review.review_note if review else None
    application.reviewed_by_id = current_admin.id
    application.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(application)
    return application
